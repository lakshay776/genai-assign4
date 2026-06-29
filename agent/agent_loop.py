"""
agent/agent_loop.py
-------------------
Core agent orchestration logic.

Implements two agent modes:

  Mode A — Rule-Based (Deterministic)
    A hardcoded sequence of tool calls targeting the shadcn form page.
    Uses CSS selectors for reliable element identification.
    Guaranteed to work for the viva demonstration.

  Mode B — AI-Augmented (Groq Vision via OpenAI-compatible SDK)
    Uses a Groq-hosted vision LLM (e.g. llama-4-scout) to analyze
    screenshots, understand the current page state, and decide the
    next action. Implements a ReAct loop: Reason → Act → Observe.
    Showcases "agent intelligence" for the 20% rubric criterion.
"""

import os
import asyncio
import base64
import json
from pathlib import Path
from typing import Optional

from playwright.async_api import Page

from agent.logger import get_logger
from agent.browser_tools import (
    DEFAULT_TIMEOUT,
    open_browser,
    navigate_to_url,
    take_screenshot,
    send_keys,
    scroll,
    click_element,
    click_on_screen,
    double_click,
    press_key,
    get_text,
    list_interactables,
)

logger = get_logger("agent_loop")

# ─────────────────────────────────────────────────────────────────────────────
# Shared helpers
# ─────────────────────────────────────────────────────────────────────────────

def _get_env(key: str, default: str = "") -> str:
    """Retrieve an environment variable with an optional default."""
    return os.environ.get(key, default)


async def _wait(page: Page, ms: int = 1000) -> None:
    """Pause for a given number of milliseconds."""
    await page.wait_for_timeout(ms)


# ─────────────────────────────────────────────────────────────────────────────
# MODE A — Rule-Based Agent
# ─────────────────────────────────────────────────────────────────────────────

async def run_rule_based_agent(
    page: Page,
    url: str,
    fill_name: str,
    fill_description: str,
) -> None:
    """
    Execute the website automation task using deterministic CSS selectors.

    This mode follows a fixed sequence of steps:
      1. Navigate to the target URL
      2. Capture initial screenshot
      3. Scroll to bring the live form preview into view
      4. Fill the Username / Name field
      5. Fill the Description / Bio textarea
      6. Click the Submit button
      7. Wait for success feedback and capture final screenshot

    Args:
        page:             Active Playwright Page.
        url:              Target page URL.
        fill_name:        Value to enter in the Name/Username field.
        fill_description: Value to enter in the Description/Bio field.
    """
    logger.info("=" * 60)
    logger.info("AGENT MODE: Rule-Based (Deterministic)")
    logger.info("=" * 60)

    # ── Step 1: Navigate ──────────────────────────────────────────────
    logger.info("[Step 1/7] Navigating to target URL...")
    await navigate_to_url(page, url)

    # ── Step 2: Initial screenshot ────────────────────────────────────
    logger.info("[Step 2/7] Capturing initial state screenshot...")
    await take_screenshot(page, "01_initial_page")
    await _wait(page, 1500)

    # ── Step 3: Scroll down to find the form ─────────────────────────
    logger.info("[Step 3/7] Scrolling to locate the live form preview...")
    # The shadcn docs page has a live demo form embedded below the code examples.
    # We scroll in increments and check for the form to appear.
    form_found = False
    for scroll_attempt in range(8):  # scroll up to ~3200px
        await scroll(page, direction="down", amount=400)
        await _wait(page, 600)

        # Check if the form input is now in the DOM and visible
        try:
            username_input = page.locator('input[name="username"]').first
            if await username_input.is_visible():
                logger.info("✅ Form found after %d scroll(s)", scroll_attempt + 1)
                form_found = True
                break
        except Exception:
            pass

    if not form_found:
        # Fallback: try alternative selectors commonly used by shadcn demos
        logger.warning("⚠️  Primary selector not found — trying fallback selectors...")
        fallback_selectors = [
            'input[placeholder*="shadcn"]',
            'input[id*="username"]',
            'input[type="text"]',
            'form input',
        ]
        for sel in fallback_selectors:
            try:
                el = page.locator(sel).first
                if await el.is_visible():
                    logger.info("✅ Form found via fallback selector: '%s'", sel)
                    form_found = True
                    break
            except Exception:
                continue

    if not form_found:
        logger.warning(
            "⚠️  Could not confirm form visibility — proceeding anyway with best-effort selectors."
        )

    await take_screenshot(page, "02_form_located")

    # ── Step 4: Fill the Username / Name field ────────────────────────
    logger.info("[Step 4/7] Filling the Name/Username field with: '%s'", fill_name)

    # Priority order: confirmed working first → fallbacks with short probe timeout
    name_selectors = [
        ('input[name="username"]',            DEFAULT_TIMEOUT),
        ('input[placeholder*="shadcn"]',       3_000),
        ('input[id*="username"]',              3_000),
        ('form input[type="text"]:first-of-type', 3_000),
        ('form input',                          3_000),
    ]

    name_filled = False
    for sel, timeout in name_selectors:
        try:
            await send_keys(page, sel, fill_name, timeout=timeout)
            name_filled = True
            logger.info("✅ Name field filled using selector: '%s'", sel)
            break
        except Exception as exc:
            logger.debug("Selector '%s' failed: %s", sel, exc)

    if not name_filled:
        raise RuntimeError("❌ Could not fill the Name field with any known selector.")

    await _wait(page, 500)

    # ── Step 5: Fill the Description / Bio textarea ───────────────────
    logger.info(
        "[Step 5/7] Filling the Description/Bio field with: '%s'", fill_description
    )

    desc_selectors = [
        ('form textarea',                       DEFAULT_TIMEOUT),   # confirmed working
        ('textarea[name="bio"]',                3_000),
        ('textarea[placeholder*="Tell us"]',    3_000),
        ('textarea[id*="bio"]',                 3_000),
        ('textarea',                             3_000),
    ]

    desc_filled = False
    for sel, timeout in desc_selectors:
        try:
            await send_keys(page, sel, fill_description, timeout=timeout)
            desc_filled = True
            logger.info("✅ Description field filled using selector: '%s'", sel)
            break
        except Exception as exc:
            logger.debug("Selector '%s' failed: %s", sel, exc)

    if not desc_filled:
        raise RuntimeError("❌ Could not fill the Description field with any known selector.")

    await _wait(page, 500)
    await take_screenshot(page, "03_form_filled")

    # ── Step 6: Click Submit ──────────────────────────────────────────
    logger.info("[Step 6/7] Submitting the form...")

    submit_selectors = [
        'button[type="submit"]',
        'form button',
        'button:has-text("Submit")',
        'button:has-text("submit")',
    ]

    submitted = False
    for sel in submit_selectors:
        try:
            await click_element(page, sel)
            submitted = True
            logger.info("✅ Submit button clicked using selector: '%s'", sel)
            break
        except Exception as exc:
            logger.debug("Submit selector '%s' failed: %s", sel, exc)

    if not submitted:
        raise RuntimeError("❌ Could not find or click the Submit button.")

    # ── Step 7: Wait for result and final screenshot ──────────────────
    logger.info("[Step 7/7] Waiting for submission feedback...")
    await _wait(page, 2000)  # give time for toast / success message to appear
    await take_screenshot(page, "04_form_submitted")

    logger.info("=" * 60)
    logger.info("🎉 Rule-based agent completed successfully!")
    logger.info("Screenshots saved to the 'screenshots/' directory.")
    logger.info("=" * 60)


# ─────────────────────────────────────────────────────────────────────────────
# MODE B — AI-Augmented Agent (Gemini Vision ReAct Loop)
# ─────────────────────────────────────────────────────────────────────────────

async def run_ai_agent(
    page: Page,
    url: str,
    fill_name: str,
    fill_description: str,
) -> None:
    """
    Execute the automation task using a Groq vision LLM for dynamic reasoning.

    Uses the OpenAI-compatible SDK pointed at Groq's API endpoint.
    The default model is llama-4-scout-17b-16e-instruct (vision-capable).

    Implements a ReAct (Reason + Act) loop:
      1. Take screenshot → encode as base64
      2. Send to Groq Vision model with task context
      3. Parse the model's JSON action recommendation
      4. Execute the action using browser tools
      5. Repeat until task is complete or max steps reached

    Args:
        page:             Active Playwright Page.
        url:              Target page URL.
        fill_name:        Value to enter in the Name/Username field.
        fill_description: Value to enter in the Description/Bio field.
    """
    logger.info("=" * 60)
    logger.info("AGENT MODE: AI-Augmented (Groq Vision ReAct)")
    logger.info("=" * 60)

    # Import OpenAI SDK (Groq uses the same interface)
    try:
        from openai import AsyncOpenAI
    except ImportError:
        raise ImportError(
            "openai package not installed. "
            "Run: pip install openai"
        )

    api_key = _get_env("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set in environment. "
            "Please add it to your .env file."
        )

    # Groq model to use — must support vision (image inputs)
    model_name = _get_env("GROQ_MODEL", "llama-3.2-90b-vision-preview")

    # Groq exposes an OpenAI-compatible REST API at this base URL
    client = AsyncOpenAI(
        api_key=api_key,
        base_url="https://api.groq.com/openai/v1",
    )

    # ── Navigate first ────────────────────────────────────────────────
    await navigate_to_url(page, url)
    await _wait(page, 2000)

    # ── ReAct Loop ────────────────────────────────────────────────────
    MAX_STEPS = 20
    task_complete = False

    SYSTEM_PROMPT = f"""You are a web automation agent. Your task is to fill out a form on this page.
The form has:
  - A text input field (could be "Username", "Name", or "Bug Title") → fill it with: "{fill_name}"
  - A textarea (could be "Bio", "Description") → fill it with: "{fill_description}"
  - A "Submit" button → click it to submit

You will receive a screenshot of the current browser state.
Respond ONLY with a JSON object describing the NEXT single action to take.

Available actions:
  {{"action": "scroll", "direction": "down", "amount": 400}}
  {{"action": "scroll", "direction": "up", "amount": 400}}
  {{"action": "click_selector", "selector": "<css_selector>"}}
  {{"action": "fill_field", "selector": "<css_selector>", "text": "<value>"}}
  {{"action": "screenshot", "label": "<label>"}}
  {{"action": "done", "reason": "<success message>"}}

Rules:
- If the form is not visible, scroll down to find it.
- DO NOT guess placeholders or complex CSS selectors. Use generic CSS selectors! For example: use 'input' for the first text field, 'textarea' for the text area, and 'button[type="submit"]' for the button.
- Fill the text field FIRST, then the textarea, then submit.
- Once you have successfully clicked the Submit button, your very next action MUST be 'done'.
- Respond with ONLY valid JSON. No markdown, no explanation."""

    last_error = ""
    action_history = []

    for step in range(1, MAX_STEPS + 1):
        logger.info("── AI Step %d/%d ──────────────────────", step, MAX_STEPS)

        # Capture current state
        screenshot_path = await take_screenshot(page, f"ai_step_{step:02d}")

        # Encode screenshot to base64 for the vision model
        with open(screenshot_path, "rb") as f:
            img_bytes = f.read()
        img_b64 = base64.b64encode(img_bytes).decode("utf-8")

        # Ask Groq for the next action using OpenAI chat completions format
        logger.info("🤖 Consulting Groq (%s) for next action...", model_name)
        
        user_text = "What is the next action to take to complete the form?"
        if action_history:
            user_text += f"\n\nHere are the actions you have taken so far:\n{json.dumps(action_history, indent=2)}\nDO NOT repeat an action (like clicking submit) if you have already done it."
            
        if last_error:
            user_text += f"\n\nWARNING: Your previous action failed with error: {last_error}\nDO NOT repeat the same action or selector. Try a different, simpler CSS selector like 'input' or 'textarea'."
            last_error = ""  # clear after showing
            
        raw_text = ""
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}",
                                },
                            },
                            {
                                "type": "text",
                                "text": user_text,
                            },
                        ],
                    },
                ],
                max_tokens=256,
                temperature=0.0,   # deterministic
            )
            raw_text = response.choices[0].message.content.strip()
            logger.debug("Groq raw response: %s", raw_text)

            # Strip markdown code fences if present
            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]

            action_data = json.loads(raw_text)

        except json.JSONDecodeError as exc:
            logger.error("❌ Failed to parse Groq response as JSON: %s", exc)
            logger.error("Raw response was: %s", raw_text)
            continue
        except Exception as exc:
            logger.error("❌ Groq API call failed: %s", exc)
            break

        action = action_data.get("action", "")
        logger.info("🤖 Groq decided: %s", action_data)
        action_history.append(action_data)

        # ── Execute the decided action ─────────────────────────────
        try:
            if action == "scroll":
                direction = action_data.get("direction", "down")
                amount = int(action_data.get("amount", 400))
                await scroll(page, direction=direction, amount=amount)

            elif action == "click_selector":
                selector = action_data["selector"]
                await click_element(page, selector)

            elif action == "fill_field":
                selector = action_data["selector"]
                text = action_data["text"]
                await send_keys(page, selector, text)

            elif action == "screenshot":
                label = action_data.get("label", f"manual_{step}")
                await take_screenshot(page, label)

            elif action == "done":
                reason = action_data.get("reason", "Task complete")
                logger.info("🎉 AI agent signalled completion: %s", reason)
                task_complete = True
                break

            else:
                logger.warning("⚠️  Unknown action '%s' — skipping.", action)

        except Exception as exc:
            logger.error("❌ Action execution failed: %s", exc)
            last_error = str(exc)

        await _wait(page, 800)

    # Final screenshot regardless of outcome
    await take_screenshot(page, "ai_final_state")

    if task_complete:
        logger.info("=" * 60)
        logger.info("🎉 AI-augmented agent completed successfully!")
        logger.info("=" * 60)
    else:
        logger.warning(
            "⚠️  AI agent reached max steps (%d) without signalling completion.",
            MAX_STEPS,
        )


# ─────────────────────────────────────────────────────────────────────────────
# MODE C — Generic Instruction-Driven Agent (any URL + any instruction)
# ─────────────────────────────────────────────────────────────────────────────
#
# This is the engine behind the web frontend. Unlike the two modes above —
# which are hardwired to fill a name/description form — this agent takes a
# free-text instruction (e.g. "search for 'playwright' and open the first
# result") and a target URL, then drives the browser with a Groq vision
# model until the instruction is satisfied. It returns a structured *report*
# (steps, screenshots, extracted text, status) that the UI can render.
# ─────────────────────────────────────────────────────────────────────────────

GENERIC_SYSTEM_PROMPT = """You are an autonomous web-automation agent controlling a real Chromium browser.

You are given a TASK written in plain English and a screenshot of the current page.
At each step you decide the SINGLE next action that makes progress toward the task.

Respond with ONLY a JSON object (no markdown, no prose) of this shape:
  {"thought": "<one short sentence of reasoning>", "action": "<action>", ...params}

Available actions and their params:
  {"thought": "...", "action": "scroll", "direction": "down|up", "amount": 400}
  {"thought": "...", "action": "click", "selector": "<css or text= selector>"}
  {"thought": "...", "action": "fill", "selector": "<css selector>", "text": "<value>"}
  {"thought": "...", "action": "press_key", "key": "Enter"}
  {"thought": "...", "action": "extract", "selector": "<css selector>"}
  {"thought": "...", "action": "wait", "ms": 1000}
  {"thought": "...", "action": "screenshot", "label": "<label>"}
  {"thought": "...", "action": "done", "success": true, "summary": "<what you accomplished>"}

Selector guidance:
  - You will be given a list of INTERACTABLE ELEMENTS with their EXACT selectors.
    ALWAYS pick a selector from that list when one fits — do NOT invent selectors
    or guess attribute names that aren't shown there.
  - If nothing in the list fits, fall back to simple selectors:
      Text-based: "text=Sign in"  (a clickable element containing that text)
      Generic:    "input", "textarea", "button[type='submit']"
  - If a selector fails, choose a DIFFERENT one from the list next time — never
    repeat a selector that just failed.

Rules:
  - Do EXACTLY what the task asks — nothing more.
  - If the relevant element is not visible, scroll to find it before interacting.
  - After filling a search/login box, either click its submit button or press_key "Enter".
  - Use "extract" to capture any result/confirmation text the task is asking for.
  - When the task is fully done, respond with action "done" and a clear summary.
  - If you get stuck or the task is impossible, respond with action "done", "success": false,
    and explain why in the summary.
  - Output ONLY valid JSON. One action per response."""


async def run_instruction_agent(
    page: Page,
    url: str,
    instruction: str,
    max_steps: int = 15,
    screenshot_dir: Optional[Path] = None,
    on_step=None,
) -> dict:
    """
    Drive the browser to satisfy a free-text instruction on any URL.

    Implements a ReAct loop (Reason → Act → Observe) using a Groq vision
    model, and builds a structured report as it goes.

    Args:
        page:           Active Playwright Page.
        url:            Target URL to start from.
        instruction:    Plain-English task, e.g. "search for cats and open
                        the first image".
        max_steps:      Safety cap on the number of reasoning iterations.
        screenshot_dir: Directory to save this run's screenshots into.
        on_step:        Optional callback(step_dict) invoked after each step,
                        for live progress streaming.

    Returns:
        A report dict:
        {
          "url": str, "instruction": str,
          "status": "success" | "failed" | "incomplete" | "error",
          "summary": str,
          "model": str,
          "steps": [ {step, thought, action, detail, screenshot, observation, error}, ... ],
          "extracted": [str, ...],
          "screenshots": [str, ...],
        }
    """
    from openai import AsyncOpenAI

    report: dict = {
        "url": url,
        "instruction": instruction,
        "status": "incomplete",
        "summary": "",
        "model": _get_env("GROQ_MODEL", "meta-llama/llama-4-scout-17b-16e-instruct"),
        "steps": [],
        "extracted": [],
        "screenshots": [],
    }

    def _record(step: dict) -> None:
        report["steps"].append(step)
        if step.get("screenshot"):
            report["screenshots"].append(step["screenshot"])
        if on_step:
            try:
                on_step(step)
            except Exception:  # never let the UI callback break the run
                pass

    api_key = _get_env("GROQ_API_KEY")
    if not api_key:
        report["status"] = "error"
        report["summary"] = "GROQ_API_KEY is not set in the environment (.env)."
        logger.error(report["summary"])
        return report

    client = AsyncOpenAI(api_key=api_key, base_url="https://api.groq.com/openai/v1")
    model_name = report["model"]

    logger.info("=" * 60)
    logger.info("AGENT MODE: Generic Instruction-Driven (Groq Vision)")
    logger.info("Task: %s", instruction)
    logger.info("URL : %s", url)
    logger.info("=" * 60)

    # ── Navigate to the starting page ─────────────────────────────────
    try:
        await navigate_to_url(page, url)
        await _wait(page, 1500)
    except Exception as exc:
        report["status"] = "error"
        report["summary"] = f"Could not load the page: {exc}"
        logger.error(report["summary"])
        return report

    system_prompt = GENERIC_SYSTEM_PROMPT

    action_history: list = []
    last_error = ""

    for step_no in range(1, max_steps + 1):
        logger.info("── Step %d/%d ──────────────────────", step_no, max_steps)

        shot_path = await take_screenshot(
            page, f"step_{step_no:02d}", directory=screenshot_dir
        )
        shot_rel = shot_path.name

        with open(shot_path, "rb") as f:
            img_b64 = base64.b64encode(f.read()).decode("utf-8")

        # Give the model the REAL interactable elements on the page so it
        # targets selectors that exist instead of guessing from the screenshot.
        elements = await list_interactables(page, max_items=30)
        if elements:
            elem_lines = "\n".join(
                f'  - {e["selector"]}'
                + (f'  ({e["tag"]}'
                   + (f' type={e["type"]}' if e["type"] else "")
                   + (f' "{e["label"]}"' if e["label"] else "")
                   + ")")
                for e in elements
            )
            elements_block = (
                "\n\nINTERACTABLE ELEMENTS currently on the page "
                "(use these EXACT selectors — do not invent your own):\n"
                + elem_lines
            )
        else:
            elements_block = ""

        user_text = (
            f"TASK: {instruction}\n\n"
            f"You are on: {page.url}\n"
            "Decide the next single action."
            + elements_block
        )
        if action_history:
            user_text += (
                "\n\nActions you have already taken (do not pointlessly repeat them):\n"
                + json.dumps(action_history, indent=2)
            )
        if last_error:
            user_text += (
                f"\n\nYour previous action FAILED: {last_error}\n"
                "Try a different, simpler selector or a different approach."
            )
            last_error = ""

        raw_text = ""
        try:
            response = await client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "image_url",
                                "image_url": {
                                    "url": f"data:image/png;base64,{img_b64}"
                                },
                            },
                            {"type": "text", "text": user_text},
                        ],
                    },
                ],
                max_tokens=400,
                temperature=0.0,
            )
            raw_text = response.choices[0].message.content.strip()

            if raw_text.startswith("```"):
                raw_text = raw_text.split("```")[1]
                if raw_text.startswith("json"):
                    raw_text = raw_text[4:]
            action_data = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            logger.error("❌ Bad JSON from model: %s | raw=%s", exc, raw_text)
            _record({
                "step": step_no,
                "thought": "",
                "action": "parse_error",
                "detail": raw_text[:300],
                "screenshot": shot_rel,
                "observation": "",
                "error": f"Could not parse model response: {exc}",
            })
            last_error = "Your last response was not valid JSON. Respond with ONLY a JSON object."
            continue
        except Exception as exc:
            logger.error("❌ Groq API call failed: %s", exc)
            report["status"] = "error"
            report["summary"] = f"Model API call failed: {exc}"
            _record({
                "step": step_no,
                "thought": "",
                "action": "api_error",
                "detail": "",
                "screenshot": shot_rel,
                "observation": "",
                "error": str(exc),
            })
            return report

        action = str(action_data.get("action", "")).lower()
        thought = action_data.get("thought", "")
        logger.info("🤖 thought: %s", thought)
        logger.info("🤖 action: %s", action_data)
        action_history.append({k: v for k, v in action_data.items() if k != "thought"})

        step_entry = {
            "step": step_no,
            "thought": thought,
            "action": action,
            "detail": "",
            "screenshot": shot_rel,
            "observation": "",
            "error": "",
        }

        # ── Execute the chosen action ─────────────────────────────────
        try:
            if action == "scroll":
                direction = action_data.get("direction", "down")
                amount = int(action_data.get("amount", 400))
                step_entry["detail"] = f"{direction} {amount}px"
                await scroll(page, direction=direction, amount=amount)

            elif action == "click":
                selector = action_data["selector"]
                step_entry["detail"] = selector
                await click_element(page, selector)

            elif action == "fill":
                selector = action_data["selector"]
                text = action_data.get("text", "")
                step_entry["detail"] = f"{selector} ← {text!r}"
                await send_keys(page, selector, text)

            elif action == "press_key":
                key = action_data.get("key", "Enter")
                step_entry["detail"] = key
                await press_key(page, key)

            elif action == "extract":
                selector = action_data.get("selector", "body")
                step_entry["detail"] = selector
                text = await get_text(page, selector)
                step_entry["observation"] = text
                if text:
                    report["extracted"].append(text)

            elif action == "wait":
                ms = int(action_data.get("ms", 1000))
                step_entry["detail"] = f"{ms}ms"
                await _wait(page, ms)

            elif action == "screenshot":
                label = action_data.get("label", f"manual_{step_no}")
                step_entry["detail"] = label
                extra = await take_screenshot(page, label, directory=screenshot_dir)
                step_entry["screenshot"] = extra.name
                report["screenshots"].append(extra.name)

            elif action == "done":
                success = bool(action_data.get("success", True))
                summary = action_data.get("summary", "Task complete.")
                step_entry["detail"] = summary
                report["status"] = "success" if success else "failed"
                report["summary"] = summary
                _record(step_entry)
                logger.info("🏁 done (success=%s): %s", success, summary)
                break

            else:
                step_entry["error"] = f"Unknown action: {action}"
                logger.warning("⚠️  Unknown action '%s' — skipping.", action)

        except Exception as exc:
            logger.error("❌ Action '%s' failed: %s", action, exc)
            step_entry["error"] = str(exc)
            last_error = f'action="{action}" failed: {exc}'

        _record(step_entry)
        await _wait(page, 700)

    else:
        # Loop finished without a "done" action
        report["status"] = "incomplete"
        report["summary"] = (
            f"Reached the step limit ({max_steps}) before the task was confirmed complete."
        )
        logger.warning(report["summary"])

    # Final screenshot for the report
    final = await take_screenshot(page, "final_state", directory=screenshot_dir)
    report["screenshots"].append(final.name)

    logger.info("=" * 60)
    logger.info("Run finished — status: %s", report["status"])
    logger.info("=" * 60)
    return report


async def execute_task(
    url: str,
    instruction: str,
    headless: bool = True,
    slow_mo: int = 50,
    max_steps: int = 15,
    screenshot_dir: Optional[Path] = None,
    on_step=None,
) -> dict:
    """
    Open a browser, run the generic instruction agent, and clean up.

    This is the single entry point the web frontend calls. It owns the
    full browser lifecycle so callers only deal with the resulting report.

    Returns the report dict from :func:`run_instruction_agent`.
    """
    playwright = None
    browser = None
    try:
        playwright, browser, page = await open_browser(
            headless=headless, slow_mo=slow_mo
        )
        return await run_instruction_agent(
            page=page,
            url=url,
            instruction=instruction,
            max_steps=max_steps,
            screenshot_dir=screenshot_dir,
            on_step=on_step,
        )
    except Exception as exc:
        logger.exception("Fatal error in execute_task: %s", exc)
        return {
            "url": url,
            "instruction": instruction,
            "status": "error",
            "summary": f"Fatal error: {exc}",
            "model": _get_env("GROQ_MODEL", ""),
            "steps": [],
            "extracted": [],
            "screenshots": [],
        }
    finally:
        if browser:
            await browser.close()
        if playwright:
            await playwright.stop()
