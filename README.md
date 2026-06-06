# Website Automation Agent

This is a Python script that automates filling out a form on a website using Playwright. 

It has two modes:
1. **Rule-based mode**: A standard script that uses CSS selectors to find and fill out the form.
2. **AI-augmented mode**: Uses a vision language model (via Groq) to look at screenshots of the page and figure out what to click and type on its own.

## Setup

1. Make sure you have Python 3.10+ installed.
2. Install the required packages:
```bash
pip install -r requirements.txt
playwright install chromium
```
3. Copy the `.env.example` file to `.env` and add your Groq API key if you plan to use the AI mode.

## How to run

To run the standard rule-based automation:
```bash
python main.py
```

To run the AI-augmented automation:
```bash
python main.py --mode ai
```

### Options

You can customize the script using command line arguments:
- `--url`: The target URL to automate
- `--name`: The text to type into the first name/title field
- `--desc`: The text to type into the description field
- `--headless`: Run the browser in the background without a window
- `--slow-mo`: Add a delay (in milliseconds) between browser actions to watch it work

Example:
```bash
python main.py --name "Alice" --desc "Test submission" --slow-mo 500
```

## Output

When the script runs, it will save screenshots of its progress in the `screenshots/` folder and write detailed logs to `agent.log`.
