import os, json, subprocess, sys
from pathlib import Path
from openai import OpenAI

GOAL = Path("GOAL.md").read_text()
AGENTS_DIR = Path("agents")
AGENT_FILES = ["bmad-orchestrator.md","pm.md","analyst.md","architect.md","dev.md","qa.md","sm.md"]
AGENTS = "\n\n".join(
    f"[{p.stem.upper()}]\n{(AGENTS_DIR/p).read_text()}"
    for p in map(Path, AGENT_FILES) if (AGENTS_DIR/p).exists()
)

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

SYSTEM = """
You are a BMAD-style autonomous software team (Orchestrator, PM, Analyst, Architect, Dev, QA, SM).
Act only via JSON tool calls—no prose. Valid shapes:
{"tool":"write_file","path":"rel/path","content":"..."}
{"tool":"bash","cmd":"safe shell command"}
{"tool":"done","notes":"summary"}
Rules: create a minimal web app, implement 12-question BCG case flow, global 35:00 timer that auto-submits, scoring + final review, unit tests, README, and deploy config.
"""

SEED = f"""
Operating instructions and product goal below.

{AGENTS}

GOAL:
{GOAL}

Start with a concrete plan, then begin scaffolding. Prefer Next.js or React+Express.
"""

def ask(messages):
    r = client.chat.completions.create(
        model="gpt-4o-mini",
        temperature=0.2,
        messages=messages
    )
    return r.choices[0].message.content.strip()

def run_bash(cmd):
    p = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    return p.returncode, (p.stdout + p.stderr)[:8000]

def write_file(path, content):
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    Path(path).write_text(content)
    return f"Wrote {path} ({len(content)} bytes)"

def main():
    msgs = [{"role":"system","content":SYSTEM},{"role":"user","content":SEED}]
    for _ in range(24):
        out = ask(msgs)
        try:
            obj = json.loads(out)
        except Exception:
            lines = [l for l in out.splitlines() if l.strip().startswith("{") and l.strip().endswith("}")]
            if not lines: 
                print("Non-JSON from model; stopping.\n", out[:800])
                sys.exit(0)
            obj = json.loads(lines[-1])

        tool = obj.get("tool")
        if tool == "bash":
            code, log = run_bash(obj["cmd"])
            msgs += [{"role":"assistant","content":out},
                     {"role":"user","content":f"exit={code}\nlog:\n{log}\nNext action?"}]
        elif tool == "write_file":
            msg = write_file(obj["path"], obj["content"])
            msgs += [{"role":"assistant","content":out},
                     {"role":"user","content":msg + "\nNext action?"}]
        elif tool == "done":
            print("DONE:", obj.get("notes",""))
            break
        else:
            print("Unknown tool:", obj); break

if __name__ == "__main__":
    main()
