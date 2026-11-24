# LabAgent

COE 379L final project. A user types a request in plain English ("Submit a job called
ppo-quadruped", "Approve job 1"). An LLM on the TACC server turns it into one tool call,
and a checker written and proved in Lean decides whether that call is allowed. Python only
carries out a call when the checker answers `"allowed": true`.

- Who is logged in and their role come from `users.json`, never from the request text.
- Every action that changes a job (submit, approve, start, finish, cancel) goes through the checker.
- Listing jobs changes nothing, so it skips the checker.

## Job rules

| Action  | From status  | To status   | Who                     |
|---------|--------------|-------------|-------------------------|
| submit  | (new job)    | proposed    | anyone                  |
| approve | proposed     | approved    | admin only              |
| start   | approved     | running     | anyone                  |
| finish  | running      | done        | anyone                  |
| cancel  | proposed, approved, running | cancelled | anyone   |

The tool call must also name the user who is logged in. Users (`users.json`):
alice and bob are students, charlie is the admin.

## Project layout

```
labagent/
  llm.py        system prompt, ToolCall schema, ScriptedLLM, TACC model client
  jobs.py       users.json and jobs.json helpers
  agent.py      handle(): one request -> tool call -> checker -> result
  guard.py      calls the Lean checker (currently a stub, see Status)
  __main__.py   command line: ask, list, reset, demo, eval
lean/
  LabAgent.lean rules and proofs
  Main.lean     the `guard` program Python runs
scenarios.json  80 test requests in 15 scenarios, used by the evaluation
users.json      lab users and roles
tests/          pytest tests
```

## Setup

You need [uv](https://docs.astral.sh/uv/) and Lean 4 through [elan](https://github.com/leanprover/elan).

```bash
git clone https://github.com/saketkaki/COE379L_Final_Project.git
cd COE379L_Final_Project
uv sync                      # Python 3.13 environment with httpx, pydantic, pytest
cd lean && lake build && cd ..   # builds the Lean checker
```

If another virtual environment is active (uv warns that `VIRTUAL_ENV` does not match),
run `deactivate` first.

### TACC model access

The model calls need three environment variables:

| Variable            | Value |
|---------------------|-------|
| `TAPIS_JWT`         | your Tapis token |
| `TACC_LLM_BASE_URL` | `https://coe379llm.pods.tacc.tapis.io/v1` |
| `TACC_LLM_MODEL`    | `Llama-4-Maverick-17B-128E-Instruct` |

Use the `coe379llm.pods.tacc.tapis.io` URL. `ai.tejas.tacc.utexas.edu` returns 401 for
Tapis tokens.

Tokens expire after 4 hours. One way to manage them is to keep the token in a file and
load everything from a small script:

```bash
# save the token: paste it, press Enter, then Ctrl-D
cat > ~/.tacc_token
chmod 600 ~/.tacc_token

# ~/.tacc_env
export TAPIS_JWT="$(tr -d '[:space:]' < ~/.tacc_token)"
export TACC_LLM_BASE_URL=https://coe379llm.pods.tacc.tapis.io/v1
export TACC_LLM_MODEL=Llama-4-Maverick-17B-128E-Instruct
```

Then run `source ~/.tacc_env` in each new terminal. When the token expires, save a new one
with `cat > ~/.tacc_token` and source the file again.

## Running

`list`, `reset` and `eval` work without a token. `ask` and `demo` call the model, so run
`source ~/.tacc_env` first.

```bash
uv run python -m labagent ask "Submit a job called ppo-quadruped" --as alice
uv run python -m labagent ask "Approve job 1" --as charlie
uv run python -m labagent list      # show saved jobs
uv run python -m labagent reset     # delete jobs.json
uv run python -m labagent demo      # 7-step demo, does not touch jobs.json
uv run python -m labagent eval      # not ready yet
```

`ask` saves jobs to `jobs.json` (ignored by git). Each result prints the tool call the model
picked, the status (`completed`, `blocked`, `clarification_required` or `failed`), an error
code when something was refused, and a message.

The demo runs these steps against a fresh job list:

1. alice submits a job
2. alice tries to start it before approval (blocked)
3. alice claims to be the admin and approves (blocked)
4. a scripted model mistake: alice's request comes back as a call for charlie (blocked)
5. charlie approves
6. alice starts the job
7. list jobs

## Tests

```bash
uv run pytest
```

There are no tests yet (`tests/test_llm.py` is empty), so pytest reports that no tests ran.

### Quick checks without the model

Runs `handle()` with a scripted model, so it needs no token. With the stub checker the first
call is `blocked`; with the checker turned off it is `completed`.

```bash
uv run python -c "
from labagent.agent import handle
from labagent.llm import ScriptedLLM
from labagent.jobs import load_users
users, jobs = load_users(), []
step = {'action': 'submit', 'user': 'alice', 'name': 'ppo-quadruped'}
print(handle('alice', 'submit', llm=ScriptedLLM([step]), jobs=jobs, users=users))
print(handle('alice', 'submit', llm=ScriptedLLM([step]), jobs=jobs, users=users, use_guard=False))
"
```

### Full flow with the real model and no checker

Shows a job going through every state while the real checker is not built yet.
Needs `source ~/.tacc_env`. Job 1 should end up `done`.

```bash
uv run python -c "
from labagent.agent import handle
from labagent.jobs import load_users, show_jobs
from labagent.llm import OpenAICompatibleLLM
llm = OpenAICompatibleLLM.from_env()
users, jobs = load_users(), []
for user, text in [('alice', 'Submit a job called ppo-quadruped'), ('charlie', 'Approve job 1'),
                   ('alice', 'Start job 1'), ('alice', 'Finish job 1')]:
    r = handle(user, text, llm=llm, jobs=jobs, users=users, use_guard=False)
    print(user, '|', text, '->', r['status'], r['message'])
print(show_jobs(jobs))
"
```

## Status

Done:

- Python project, Lean build setup, and TACC model access
- `llm.py`, `jobs.py`, `agent.py`, `__main__.py`
- `scenarios.json` (80 steps; expected statuses checked against the job rules)

Not done yet:

- Lean rules and proofs (`lean/LabAgent.lean`). `lean/Main.lean` is a placeholder that always
  answers "not allowed".
- The real `labagent/guard.py`. The current one is a stub that blocks every action, so
  `ask` and `demo` block every submit, approve, start, finish and cancel for now.
- `evaluate.py` and the `eval` command
- Tests: `tests/test_agent.py`, `tests/test_eval.py`, `tests/test_guard.py`
