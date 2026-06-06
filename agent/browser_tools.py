"""
agent/browser_tools.py
-----------------------
All browser automation tool functions required by the assignment.

Each tool is an async function that wraps Playwright primitives and
adds structured logging, error handling, and retry logic.

Required tools (as per assignment spec):
    ✅ open_browser      - Launch a browser instance
    ✅ navigate_to_url   - Navigate to a URL
    ✅ take_screenshot   - Capture the current browser state
    ✅ click_on_screen   - Click at (x, y) coordinates
    ✅ send_keys         - Type text into a form field
    ✅ scroll            - Scroll the page
    ✅ double_click      - Double-click at (x, y) coordinates
"""

import os
import asyncio
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from playwright.async_api import (
    async_playwright,
    Browser,
    BrowserContext,
    Page,
    Playwright,
    TimeoutError as PlaywrightTimeoutError,
)

from agent.logger import get_logger

logger = get_logger("browser_tools")

# Directory where screenshots are saved
SCREENSHOT_DIR = Path("screenshots")
SCREENSHOT_DIR.mkdir(exist_ok=True)

# Default timeout in milliseconds for element waits
DEFAULT_TIMEOUT = 15_000

# ─────────────────────────────────────────────────────────────────────────────
# Helper
# ─────────────────────────────────────────────────────────────────────────────

def _timestamp() -> str:
    """Return a sortable timestamp string for file names."""
    return datetime.now().strftime("%Y%m%d_%H%M%S_%f")[:-3]


async def _retry(coro_fn, retries: int = 3, delay: float = 1.5):
    """
    Execute an async callable up to `retries` times.

    Args:
        coro_fn: A zero-argument async callable to retry.
        retries: Maximum number of attempts (default 3).
        delay:   Seconds to wait between attempts (default 1.5).

    Returns:
        The result of the first successful call.

    Raises:
        The last exception if all attempts fail.
    """
    last_exc: Exception = RuntimeError("No attempts made")
    for attempt in range(1, retries + 1):
        try:
            return await coro_fn()
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Attempt %d/%d failed: %s — retrying in %.1fs",
                attempt, retries, exc, delay,
            )
            if attempt < retries:
                await asyncio.sleep(delay)
    raise last_exc


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1 — open_browser
# ─────────────────────────────────────────────────────────────────────────────

async def open_browser(
    headless: bool = False,
    slow_mo: int = 50,
) -> Tuple[Playwright, Browser, Page]:
    """
    Launch a Chromium browser instance and return a ready Page object.

    Args:
        headless: If True, browser runs without a visible window.
        slow_mo:  Milliseconds to slow down Playwright operations
                  (useful for demos and debugging).

    Returns:
        A tuple of (playwright_instance, browser, page).

    Raises:
        Exception: If the browser fails to launch.
    """
    logger.info("🚀 Opening browser (headless=%s, slow_mo=%dms)", headless, slow_mo)
    try:
        playwright = await async_playwright().start()
        browser = await playwright.chromium.launch(
            headless=headless,
            slow_mo=slow_mo,
            args=["--start-maximized"],
        )
        context: BrowserContext = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page: Page = await context.new_page()
        logger.info("✅ Browser launched successfully")
        return playwright, browser, page
    except Exception as exc:
        logger.error("❌ Failed to open browser: %s", exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2 — navigate_to_url
# ─────────────────────────────────────────────────────────────────────────────

async def navigate_to_url(page: Page, url: str) -> None:
    """
    Navigate the browser page to the specified URL.

    Waits until the network is idle (no pending requests for 500ms),
    which ensures dynamic content (React/Next.js) has fully rendered.

    Args:
        page: The active Playwright Page instance.
        url:  Full URL to navigate to (including scheme).

    Raises:
        PlaywrightTimeoutError: If navigation exceeds 30 seconds.
        Exception: For other navigation failures.
    """
    logger.info("🌐 Navigating to: %s", url)
    try:
        await _retry(
            lambda: page.goto(
                url,
                wait_until="networkidle",
                timeout=30_000,
            )
        )
        title = await page.title()
        logger.info("✅ Navigation complete — Page title: '%s'", title)
    except PlaywrightTimeoutError:
        logger.error("❌ Navigation timed out for URL: %s", url)
        raise
    except Exception as exc:
        logger.error("❌ Navigation failed: %s", exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3 — take_screenshot
# ─────────────────────────────────────────────────────────────────────────────

async def take_screenshot(page: Page, label: str = "screenshot") -> Path:
    """
    Capture a full-page PNG screenshot and save it to the screenshots/ folder.

    Args:
        page:  The active Playwright Page instance.
        label: A descriptive label appended to the file name
               (e.g., "initial_state", "form_filled").

    Returns:
        Path object pointing to the saved screenshot file.

    Raises:
        Exception: If the screenshot cannot be saved.
    """
    filename = SCREENSHOT_DIR / f"{_timestamp()}_{label}.png"
    logger.info("📸 Taking screenshot → %s", filename)
    try:
        await page.screenshot(path=str(filename), full_page=False)
        logger.info("✅ Screenshot saved: %s", filename)
        return filename
    except Exception as exc:
        logger.error("❌ Screenshot failed: %s", exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Tool 4 — click_on_screen
# ─────────────────────────────────────────────────────────────────────────────

async def click_on_screen(page: Page, x: int, y: int) -> None:
    """
    Perform a single left mouse click at absolute viewport coordinates.

    Args:
        page: The active Playwright Page instance.
        x:    Horizontal position in pixels from left edge of viewport.
        y:    Vertical position in pixels from top edge of viewport.

    Raises:
        Exception: If the click cannot be performed.
    """
    logger.info("🖱️  Clicking at coordinates (%d, %d)", x, y)
    try:
        await page.mouse.click(x, y)
        logger.debug("✅ Click performed at (%d, %d)", x, y)
    except Exception as exc:
        logger.error("❌ Click failed at (%d, %d): %s", x, y, exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Tool 5 — send_keys
# ─────────────────────────────────────────────────────────────────────────────

async def send_keys(
    page: Page,
    selector: str,
    text: str,
    clear_first: bool = True,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """
    Locate a form element by CSS selector and type text into it.

    Args:
        page:        The active Playwright Page instance.
        selector:    CSS selector (or XPath prefixed with 'xpath=')
                     identifying the target input element.
        text:        The text string to type.
        clear_first: If True, clears existing content before typing.
        timeout:     Maximum wait time in ms for the element to appear.

    Raises:
        PlaywrightTimeoutError: If element is not found within timeout.
        Exception: For other interaction failures.
    """
    logger.info("⌨️  Sending keys to '%s': '%s'", selector, text)
    try:
        element = page.locator(selector).first
        await element.wait_for(state="visible", timeout=timeout)

        if clear_first:
            await element.clear()

        await element.fill(text)
        logger.info("✅ Text entered successfully into '%s'", selector)
    except PlaywrightTimeoutError:
        logger.error("❌ Element not found within %dms: '%s'", timeout, selector)
        raise
    except Exception as exc:
        logger.error("❌ send_keys failed for '%s': %s", selector, exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Tool 6 — scroll
# ─────────────────────────────────────────────────────────────────────────────

async def scroll(
    page: Page,
    direction: str = "down",
    amount: int = 400,
) -> None:
    """
    Scroll the page in the specified direction by the given pixel amount.

    Args:
        page:      The active Playwright Page instance.
        direction: 'down' or 'up' (default 'down').
        amount:    Number of pixels to scroll (default 400).

    Raises:
        ValueError: If direction is not 'up' or 'down'.
        Exception:  For scroll execution failures.
    """
    if direction not in ("up", "down"):
        raise ValueError(f"Invalid scroll direction: '{direction}'. Use 'up' or 'down'.")

    delta_y = amount if direction == "down" else -amount
    logger.info("🔽 Scrolling %s by %d pixels", direction, amount)
    try:
        await page.mouse.wheel(0, delta_y)
        await page.wait_for_timeout(300)  # small pause for render
        logger.debug("✅ Scrolled %s by %dpx", direction, amount)
    except Exception as exc:
        logger.error("❌ Scroll failed: %s", exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Tool 7 — double_click
# ─────────────────────────────────────────────────────────────────────────────

async def double_click(page: Page, x: int, y: int) -> None:
    """
    Perform a double mouse click at absolute viewport coordinates.

    Useful for selecting text in fields, activating certain UI controls,
    or triggering double-click-specific event handlers.

    Args:
        page: The active Playwright Page instance.
        x:    Horizontal position in pixels from left edge of viewport.
        y:    Vertical position in pixels from top edge of viewport.

    Raises:
        Exception: If the double-click cannot be performed.
    """
    logger.info("🖱️  Double-clicking at coordinates (%d, %d)", x, y)
    try:
        await page.mouse.dblclick(x, y)
        logger.debug("✅ Double-click performed at (%d, %d)", x, y)
    except Exception as exc:
        logger.error("❌ Double-click failed at (%d, %d): %s", x, y, exc)
        raise


# ─────────────────────────────────────────────────────────────────────────────
# Bonus Tool — click_element (selector-based click for precise targeting)
# ─────────────────────────────────────────────────────────────────────────────

async def click_element(
    page: Page,
    selector: str,
    timeout: int = DEFAULT_TIMEOUT,
) -> None:
    """
    Click an element identified by a CSS/XPath selector.

    Preferred over click_on_screen when element identity is known,
    as it is resilient to page layout shifts.

    Args:
        page:     The active Playwright Page instance.
        selector: CSS selector or 'xpath=...' expression.
        timeout:  Max wait time in ms for the element (default 15s).

    Raises:
        PlaywrightTimeoutError: If element not found within timeout.
        Exception: For other click failures.
    """
    logger.info("🖱️  Clicking element: '%s'", selector)
    try:
        element = page.locator(selector).first
        await element.wait_for(state="visible", timeout=timeout)
        await element.scroll_into_view_if_needed()
        await element.click()
        logger.info("✅ Clicked element: '%s'", selector)
    except PlaywrightTimeoutError:
        logger.error("❌ Element not found within %dms: '%s'", timeout, selector)
        raise
    except Exception as exc:
        logger.error("❌ click_element failed for '%s': %s", selector, exc)
        raise
