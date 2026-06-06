# Website Automation Agent

An intelligent browser automation agent built with **Python + Playwright** that navigates to the [shadcn/ui React Hook Form demo](https://ui.shadcn.com/docs/forms/react-hook-form), automatically identifies the form, fills in the fields, and submits it — without any manual input.

---

## 🚀 Features

- **Two agent modes**: Rule-based (deterministic) and AI-augmented (Gemini Vision ReAct loop)
- **7 core automation tools**: `open_browser`, `navigate_to_url`, `take_screenshot`, `click_on_screen`, `send_keys`, `scroll`, `double_click`
- **Robust error handling**: Retry logic, timeout management, fallback selectors
- **Comprehensive logging**: Console output + rotating log file (`agent.log`)
- **Screenshot trail**: Captures browser state at each major step
- **Fully configurable**: `.env` file + CLI arguments

---

## 📁 Project Structure

```
genai-assign4/
├── agent/
│   ├── __init__.py         # Package init
│   ├── browser_tools.py    # All 7 automation tool functions
│   ├── agent_loop.py       # Mode A (rule) & Mode B (AI) orchestration
│   └── logger.py           # Centralized logging setup
├── screenshots/            # Auto-created; stores PNG screenshots
├── .env                    # Your config (copied from .env.example)
├── .env.example            # Config template
├── main.py                 # Entry point (run this!)
├── requirements.txt        # Python dependencies
├── README.md               # This file
└── ARCHITECTURE.md         # Design decisions document
```

---

## ⚙️ Setup Instructions

### Prerequisites

- Python 3.10 or higher
- pip

### 1. Clone / open the project

```bash
cd genai-assign4
```

### 2. Create a virtual environment (recommended)

```bash
python -m venv venv

# Windows
venv\Scripts\activate

# macOS/Linux
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
```

### 4. Install Playwright browsers

```bash
playwright install chromium
```

### 5. Configure environment

```bash
copy .env.example .env    # Windows
# or
cp .env.example .env      # macOS/Linux
```

Edit `.env` and fill in your values:

```env
GEMINI_API_KEY=your_api_key_here   # Only needed for --mode ai
FILL_NAME=John Doe
FILL_DESCRIPTION=This is an automated submission.
HEADLESS=false
```

---

## ▶️ Running the Agent

### Rule-Based Mode (Recommended for demo)

```bash
python main.py
```

The browser will open visibly, navigate to the shadcn form page, fill both fields, and submit.

### Rule-Based with Custom Values

```bash
python main.py --name "Alice Smith" --desc "Hello from my automation agent!"
```

### Headless Mode (No browser window)

```bash
python main.py --headless
```

### AI-Augmented Mode (Gemini Vision)

```bash
python main.py --mode ai
```

> Requires `GEMINI_API_KEY` in your `.env` file.

### All CLI Options

```
usage: main.py [-h] [--mode {rule,ai}] [--url URL] [--name NAME]
               [--desc DESC] [--headless] [--slow-mo SLOW_MO]

Options:
  --mode {rule,ai}   Agent mode (default: rule)
  --url URL          Target URL to automate
  --name NAME        Value for Name/Username field
  --desc DESC        Value for Description/Bio field
  --headless         Run without visible browser window
  --slow-mo N        Playwright slow-motion in ms (default: 50)
```

---

## 📸 Output

After each run, check:

- **`screenshots/`** — PNG files showing the browser state at each step:
  - `*_01_initial_page.png` — Page on first load
  - `*_02_form_located.png` — After scrolling to the form
  - `*_03_form_filled.png` — Both fields filled in
  - `*_04_form_submitted.png` — After clicking Submit

- **`agent.log`** — Full DEBUG-level log of every agent action

---

## 🛠️ Troubleshooting

| Problem | Solution |
|---------|----------|
| `playwright install` error | Run `playwright install-deps` first |
| Form not found | The page may have changed selectors; try `--slow-mo 200` |
| Gemini API error | Check `GEMINI_API_KEY` in `.env` |
| ModuleNotFoundError | Make sure `venv` is activated and `pip install -r requirements.txt` was run |

---

## 📦 Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| playwright | ≥1.44.0 | Browser automation |
| python-dotenv | ≥1.0.0 | `.env` file loading |
| google-generativeai | ≥0.7.0 | Gemini Vision API (ai mode) |
| Pillow | ≥10.0.0 | Image handling |
