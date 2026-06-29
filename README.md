# Website Automation Agent

An AI agent that automates **any website** from a **plain-English instruction**.
Give it a URL and a task (e.g. *"search for 'playwright' and open the first result"*),
and it drives a real Chromium browser to completion using a Groq vision model — then
produces a full report of every step it took.

It can be run from the **command line** or from a **web frontend** where you type the
URL + instruction and watch a live report (reasoning, screenshots, extracted text, pass/fail).

## Modes

1. **Generic instruction mode** (`agent/agent_loop.py` → `run_instruction_agent`)
   Works on any URL with any instruction. This powers the web app.
2. **Rule-based mode** — deterministic CSS selectors for the shadcn demo form (kept for reference).
3. **AI form-fill mode** — the original name/description form-filler.

## Setup

1. Python 3.10+.
2. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```
3. Copy `.env.example` to `.env` and set your Groq API key:
   ```
   GROQ_API_KEY=your_key_here
   GROQ_MODEL=meta-llama/llama-4-scout-17b-16e-instruct
   ```

## Run the web app (recommended)

```bash
python -m webapp.app
```
Then open **http://127.0.0.1:5000**, enter a URL + an instruction, and hit **Run**.
The report page updates live and shows:
- each reasoning step and the action taken,
- a screenshot for every step,
- any text the agent extracted,
- a final pass/fail status and summary.

Reports and screenshots for each run are saved under `screenshots/<run_id>/`.

## Run from the command line

Generic instruction mode (any URL + any task):
```bash
python main.py --mode auto \
  --url "https://duckduckgo.com" \
  --instruction "Search for 'playwright python' and extract the first result title"
```

Legacy form-fill modes:
```bash
python main.py                 # rule-based shadcn form
python main.py --mode ai       # AI vision form-fill
```

### Options
- `--mode`   : `auto` (generic instruction), `rule`, or `ai`
- `--url`    : target URL
- `--instruction` : plain-English task (used by `auto` mode)
- `--name` / `--desc` : values for the legacy form-fill modes
- `--headless` : run the browser with no visible window
- `--slow-mo`  : delay between actions in ms (watch it work)
- `--max-steps`: max reasoning iterations for `auto` mode (default 15)

## Output

- **Web app**: live report at `/report/<run_id>`, screenshots in `screenshots/<run_id>/`.
- **CLI**: screenshots in `screenshots/`, detailed logs in `agent.log`.
