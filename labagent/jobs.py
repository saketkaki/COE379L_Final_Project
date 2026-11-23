import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
USERS_FILE = ROOT / "users.json"
JOBS_FILE = ROOT / "jobs.json"


def load_users():
    return json.loads(USERS_FILE.read_text())


def load_jobs():
    if JOBS_FILE.exists():
        return json.loads(JOBS_FILE.read_text())
    return []


def save_jobs(jobs):
    JOBS_FILE.write_text(json.dumps(jobs, indent=2))


def add_job(jobs, name, user, status):
    """`status` is the one the Lean checker gave for submit (always 'proposed')."""
    job = {
        "id": len(jobs) + 1,
        "name": name,
        "status": status,
        "history": [{"user": user, "action": "submit"}],
    }
    jobs.append(job)
    return job


def find_job(jobs, job_id):
    for job in jobs:
        if job["id"] == job_id:
            return job
    return None


def show_jobs(jobs):
    if not jobs:
        return "There are no jobs that can be found right now."
    lines = []
    for job in jobs:
        history = ", ".join(f"{h['user']}: {h['action']}" for h in job["history"])
        lines.append(
            f"job {job['id']}  {job['name']:<12} {job['status']:<10} ({history})"
        )
    return "\n".join(lines)
