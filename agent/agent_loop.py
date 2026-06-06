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
    navigate_to_url,
    take_screenshot,
    send_keys,
    scroll,
    click_element,
    click_on_screen,
    double_click,
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
