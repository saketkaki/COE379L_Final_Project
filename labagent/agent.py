"""Turn one request into a tool call, check it with Lean, then do it or refuse."""

from pydantic import ValidationError

from .guard import lean_check
from .jobs import add_job, find_job, show_jobs
from .llm import StructuredLLM, ToolCallAdapter, build_messages

# Actions that change a job. These always go through the checker.
MUTATING_ACTIONS = {"submit", "approve", "start", "finish", "cancel"}

# Where each action goes if nothing stops it (used when use_guard=False).
NO_GUARD = {"submit": "proposed", "approve": "approved", "start": "running",
            "finish": "done", "cancel": "cancelled"}

def outcome(status, message, call=None, error_code=None):
    """Return a dict describing the outcome of a tool call."""
    return {"status": status, "message": message, "call": call, "error_code": error_code}

def _failed(message):
    """Return a dict describing a failed tool call."""
    return outcome("failed", message, None, "invalid_tool_call")

def handle(user, text, *, llm: StructuredLLM, jobs, users, use_guard=True):
    # 1. the role comes from users.json, not from the request
    role = users.get(user)
    if role is None:
        return outcome("blocked", f"{user} is not a lab user", None, "unknown_user")

    # 2. ask the model for one tool call
    messages = build_messages(text, jobs, {"user": user, "role": role})
    try:
        call = llm.generate(messages=messages, response_model=ToolCallAdapter)
    except (ValidationError, ValueError, TypeError, RuntimeError) as exc:
        return _failed(f"The model did not produce a valid tool call: {exc}")
    proposal = call.model_dump(exclude_none=True)

    # 3. actions that don't change anything
    if call.action == "list":
        return outcome("completed", show_jobs(jobs), proposal)
    if call.action not in MUTATING_ACTIONS:
        return outcome("blocked", "I can only help with jobs", proposal, "not_a_job_request")

    # 4. submit: the job doesn't exist yet, so its status is "unsubmitted"
    if call.action == "submit":
        job = None
        status = "unsubmitted"
    else:
        # 5. every other action needs a job that exists
        if call.job is None:
            return outcome("clarification_required", "Which job?", proposal, "job_not_specified")
        job = find_job(jobs, call.job)
        if job is None:
            return outcome("blocked", f"no job {call.job}", proposal, "unknown_job")
        status = job["status"]

    # 6. ask the checker, using the job's real status
    if use_guard:
        verdict = lean_check(user, role, status, proposal)
    else:
        verdict = {"allowed": True, "next": NO_GUARD[call.action]}

    if not verdict["allowed"]:
        return outcome("blocked", verdict["reason"], proposal, "action_gate_denied")

    if job is None:
        job = add_job(jobs, call.name or "untitled", user, verdict["next"])
    else:
        job["status"] = verdict["next"]
        job["history"].append({"user": user, "action": call.action})
    return outcome("completed", f"job {job['id']} is now {job['status']}", proposal)
