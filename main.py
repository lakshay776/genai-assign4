"""
main.py
-------
Entry point for the Website Automation Agent.

Usage:
    python main.py
    python main.py --mode ai
    python main.py --mode rule --headless
    python main.py --url https://ui.shadcn.com/docs/forms/react-hook-form

Environment variables (set in .env file):
    GEMINI_API_KEY    - Google Gemini API key (required for ai mode)
    TARGET_URL        - URL to automate
    FILL_NAME         - Value for the Name/Username field
    FILL_DESCRIPTION  - Value for the Description/Bio field
    HEADLESS          - 'true' or 'false' (default: false)
    SLOW_MO           - Playwright slow-mo delay in ms (default: 50)
    AGENT_MODE        - 'rule' or 'ai' (default: rule)
"""

import asyncio
import argparse
import os
import sys
from dotenv import load_dotenv

# Load environment variables from .env file BEFORE importing agent modules
load_dotenv()

from agent.logger import get_logger
from agent.browser_tools import open_browser
from agent.agent_loop import run_rule_based_agent, run_ai_agent

logger = get_logger("main")


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments, falling back to .env values."""
    parser = argparse.ArgumentParser(
        description="Website Automation Agent — fills a shadcn form autonomously.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python main.py                         # Rule-based, headed browser
  python main.py --headless              # Rule-based, headless browser
  python main.py --mode ai               # Gemini Vision AI agent
  python main.py --name "Jane" --desc "Hello world"
        """,
    )

    parser.add_argument(
        "--mode",
        choices=["rule", "ai"],
        default=os.getenv("AGENT_MODE", "rule"),
        help="Agent mode: 'rule' (deterministic) or 'ai' (Gemini Vision). Default: rule",
    )
    parser.add_argument(
        "--url",
        default=os.getenv(
            "TARGET_URL",
            "https://ui.shadcn.com/docs/forms/react-hook-form",
        ),
        help="Target URL to automate",
    )
    parser.add_argument(
        "--name",
        default=os.getenv("FILL_NAME", "John Doe"),
        help="Value to fill in the Name/Username field",
    )
    parser.add_argument(
        "--desc",
        default=os.getenv(
            "FILL_DESCRIPTION",
            "This is an automated form submission by my AI agent.",
        ),
        help="Value to fill in the Description/Bio field",
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        default=os.getenv("HEADLESS", "false").lower() == "true",
        help="Run browser in headless mode (no visible window)",
    )
    parser.add_argument(
        "--slow-mo",
        type=int,
        default=int(os.getenv("SLOW_MO", "50")),
        dest="slow_mo",
        help="Playwright slow-motion delay in milliseconds (default: 50)",
    )

    return parser.parse_args()


async def main() -> None:
    """Main async entry point: initializes the browser and runs the agent."""
    args = parse_args()

    # ── Print startup banner ──────────────────────────────────────────
    logger.info("╔══════════════════════════════════════════════╗")
    logger.info("║      WEBSITE AUTOMATION AGENT v1.0           ║")
    logger.info("╠══════════════════════════════════════════════╣")
    logger.info("║  Mode     : %-32s║", args.mode)
    logger.info("║  URL      : %-32s║", args.url[:32])
    logger.info("║  Name     : %-32s║", args.name[:32])
    logger.info("║  Headless : %-32s║", str(args.headless))
    logger.info("╚══════════════════════════════════════════════╝")

    playwright = None
    browser = None

    try:
        # ── Launch browser ────────────────────────────────────────────
        logger.info("Initializing browser...")
        playwright, browser, page = await open_browser(
            headless=args.headless,
            slow_mo=args.slow_mo,
        )

        # ── Run the selected agent mode ───────────────────────────────
        if args.mode == "rule":
            await run_rule_based_agent(
                page=page,
                url=args.url,
                fill_name=args.name,
                fill_description=args.desc,
            )
        elif args.mode == "ai":
            await run_ai_agent(
                page=page,
                url=args.url,
                fill_name=args.name,
                fill_description=args.desc,
            )

        logger.info("Agent run finished. Check the 'screenshots/' folder for results.")

    except KeyboardInterrupt:
        logger.info("⚠️  Agent interrupted by user (Ctrl+C)")
        sys.exit(0)

    except Exception as exc:
        logger.exception("❌ Fatal error during agent execution: %s", exc)
        sys.exit(1)

    finally:
        # ── Always clean up the browser ───────────────────────────────
        if browser:
            logger.info("Closing browser...")
            await browser.close()
        if playwright:
            await playwright.stop()
        logger.info("Cleanup complete.")


if __name__ == "__main__":
    asyncio.run(main())
