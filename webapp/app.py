"""
webapp/app.py
-------------
Flask frontend for the Website Automation Agent.

Lets you enter ANY URL + ANY plain-English instruction, runs the
generic instruction-driven agent against it, and shows a live report
(reasoning steps, screenshots, extracted text, pass/fail status).

Run:
    python -m webapp.app
then open http://127.0.0.1:5000
"""

import os
import sys
import asyncio
import threading
from datetime import datetime
from pathlib import Path

# Windows consoles default to cp1252 and choke on emoji in the agent's logs.
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv

# Load .env before importing the agent (it reads GROQ_API_KEY at call time,
# but loading early keeps everything consistent).
load_dotenv()

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    jsonify,
    send_from_directory,
    abort,
)

from agent.logger import get_logger
from agent.agent_loop import execute_task

logger = get_logger("webapp")

# On Windows, Playwright launches the browser as a subprocess, which requires
# the Proactor event loop. asyncio.run() inside a worker thread must use it too.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

BASE_DIR = Path(__file__).resolve().parent.parent
RUNS_DIR = BASE_DIR / "screenshots"
RUNS_DIR.mkdir(exist_ok=True)

app = Flask(__name__)

# In-memory store of runs (fine for a single-user local demo).
RUNS: dict = {}
RUNS_LOCK = threading.Lock()


def _new_run_id() -> str:
    return datetime.now().strftime("run_%Y%m%d_%H%M%S_%f")[:-3]


def _run_task_in_thread(run_id: str, url: str, instruction: str,
                        headless: bool, slow_mo: int, max_steps: int) -> None:
    """Worker: execute the agent and stream results into RUNS[run_id]."""
    run = RUNS[run_id]
    shot_dir = RUNS_DIR / run_id
    shot_dir.mkdir(parents=True, exist_ok=True)

    def on_step(step: dict) -> None:
        with RUNS_LOCK:
            run["steps"].append(step)
            if step.get("screenshot") and step["screenshot"] not in run["screenshots"]:
                run["screenshots"].append(step["screenshot"])

    try:
        report = asyncio.run(execute_task(
            url=url,
            instruction=instruction,
            headless=headless,
            slow_mo=slow_mo,
            max_steps=max_steps,
            screenshot_dir=shot_dir,
            on_step=on_step,
        ))
        with RUNS_LOCK:
            run["status"] = report.get("status", "incomplete")
            run["summary"] = report.get("summary", "")
            run["extracted"] = report.get("extracted", [])
            run["model"] = report.get("model", run.get("model", ""))
            # Reconcile screenshots (e.g. final_state added at the very end).
            for s in report.get("screenshots", []):
                if s not in run["screenshots"]:
                    run["screenshots"].append(s)
            run["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    except Exception as exc:  # belt-and-suspenders; execute_task already guards
        logger.exception("Run %s crashed: %s", run_id, exc)
        with RUNS_LOCK:
            run["status"] = "error"
            run["summary"] = f"Run crashed: {exc}"
            run["finished_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")


@app.route("/")
def index():
    with RUNS_LOCK:
        history = sorted(RUNS.values(), key=lambda r: r["id"], reverse=True)[:10]
    has_key = bool(os.getenv("GROQ_API_KEY"))
    return render_template("index.html", history=history, has_key=has_key)


@app.route("/run", methods=["POST"])
def run():
    url = (request.form.get("url") or "").strip()
    instruction = (request.form.get("instruction") or "").strip()
    headless = request.form.get("headless") == "on"
    try:
        max_steps = max(1, min(40, int(request.form.get("max_steps", 15))))
    except ValueError:
        max_steps = 15
    try:
        slow_mo = max(0, min(2000, int(request.form.get("slow_mo", 50))))
    except ValueError:
        slow_mo = 50

    if not url or not instruction:
        with RUNS_LOCK:
            history = sorted(RUNS.values(), key=lambda r: r["id"], reverse=True)[:10]
        return render_template(
            "index.html",
            history=history,
            has_key=bool(os.getenv("GROQ_API_KEY")),
            error="Both a URL and an instruction are required.",
            url=url,
            instruction=instruction,
        ), 400

    if not url.startswith(("http://", "https://")):
        url = "https://" + url

    run_id = _new_run_id()
    with RUNS_LOCK:
        RUNS[run_id] = {
            "id": run_id,
            "url": url,
            "instruction": instruction,
            "status": "running",
            "summary": "",
            "model": os.getenv("GROQ_MODEL", ""),
            "headless": headless,
            "max_steps": max_steps,
            "steps": [],
            "screenshots": [],
            "extracted": [],
            "started_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "finished_at": None,
        }

    thread = threading.Thread(
        target=_run_task_in_thread,
        args=(run_id, url, instruction, headless, slow_mo, max_steps),
        daemon=True,
    )
    thread.start()

    return redirect(url_for("report", run_id=run_id))


@app.route("/report/<run_id>")
def report(run_id: str):
    run = RUNS.get(run_id)
    if not run:
        abort(404)
    return render_template("report.html", run=run)


@app.route("/status/<run_id>")
def status(run_id: str):
    """JSON snapshot used by the report page to poll for live progress."""
    run = RUNS.get(run_id)
    if not run:
        return jsonify({"error": "not found"}), 404
    with RUNS_LOCK:
        return jsonify(run)


@app.route("/shot/<run_id>/<path:filename>")
def shot(run_id: str, filename: str):
    """Serve a screenshot image for a given run."""
    directory = RUNS_DIR / run_id
    if not directory.exists():
        abort(404)
    return send_from_directory(directory, filename)


if __name__ == "__main__":
    port = int(os.getenv("PORT", "5000"))
    logger.info("Starting web UI at http://127.0.0.1:%d", port)
    # threaded=True so a run in a worker thread doesn't block status polling.
    app.run(host="127.0.0.1", port=port, debug=False, threaded=True)
