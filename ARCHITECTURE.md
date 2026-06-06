# Architecture Document — Website Automation Agent

## Overview

This document explains the design decisions, component architecture, and agent workflow for Assignment 04.

---

## 1. Technology Choices

### Python + Playwright (async)

**Why Python?**
- Excellent ecosystem for AI/ML integrations (Gemini, OpenAI SDKs)
- Clean async/await syntax via `asyncio`
- Strong tooling for scripting and automation

**Why Playwright over Puppeteer/Selenium?**

| Feature | Playwright | Puppeteer | Selenium |
|---------|-----------|-----------|---------|
| Language | Python / JS / Java | JavaScript only | Many |
| Auto-wait | ✅ Built-in | ❌ Manual | ❌ Manual |
| Network idle wait | ✅ `networkidle` | Limited | ❌ |
| React / SPA support | ✅ Excellent | Good | Mediocre |
| Speed | Fast | Fast | Slower |

The shadcn/ui page is a Next.js SSR + client hydration app. Playwright's `wait_until="networkidle"` ensures all React components are fully mounted before the agent tries to interact with them.

---

## 2. Component Architecture

```
main.py
  │
  ├─► agent/logger.py          ← Shared logging (all modules use this)
  │
  ├─► agent/browser_tools.py   ← Low-level tool layer (7 tools)
  │       open_browser()
  │       navigate_to_url()
  │       take_screenshot()
  │       click_on_screen()
  │       send_keys()
  │       scroll()
  │       double_click()
  │
  └─► agent/agent_loop.py      ← High-level orchestration
          run_rule_based_agent()   ← Mode A: deterministic
          run_ai_agent()           ← Mode B: Gemini Vision ReAct
```

### Separation of Concerns

- **`browser_tools.py`** knows nothing about the task — it only wraps Playwright primitives. This makes tools reusable for any future automation task.
- **`agent_loop.py`** contains all task-specific logic (what selectors to use, what order to fill fields). Changing the target website only requires editing this file.
- **`main.py`** handles I/O (args, env vars, startup banner) and lifecycle (browser open/close).

---

## 3. Tool Design

Each tool follows a consistent pattern:

```python
async def tool_name(page, ...args) -> result:
    logger.info("Starting: ...")      # Log intent
    try:
        # Playwright operation with await
        result = await page.some_action()
        logger.info("Success: ...")   # Log success
        return result
    except Exception as exc:
        logger.error("Failed: %s", exc)  # Log failure
        raise                            # Re-raise for caller to handle
```

**Retry Logic** (`_retry` helper): Critical operations (navigation, element interaction) are wrapped with up to 3 retries and a 1.5s back-off to handle transient network issues.

---

## 4. Element Detection Strategy

The agent uses a **priority cascade** of selectors from most-specific to most-generic:

```
Level 1: Attribute selectors with name attribute
         input[name="username"], textarea[name="bio"]

Level 2: Placeholder-based selectors
         input[placeholder*="shadcn"]

Level 3: ID-based selectors
         input[id*="username"]

Level 4: Structural selectors
         form input[type="text"]:first-of-type

Level 5: Generic fallback
         form input, textarea
```

If all selectors fail, the agent raises a descriptive `RuntimeError` rather than silently continuing with bad state.

---

## 5. Agent Modes

### Mode A — Rule-Based (Deterministic)

```
open_browser → navigate_to_url → take_screenshot
    → scroll (until form visible) → send_keys (name)
    → send_keys (description) → click_element (submit)
    → take_screenshot (result)
```

**Strengths**: Fast, reliable, no API calls required, always works for the specific target page.

**Limitations**: Brittle if the page structure changes significantly.

### Mode B — AI-Augmented (Gemini Vision ReAct)

```
open_browser → navigate_to_url
    ┌─────────────────────────────────┐
    │  1. take_screenshot             │
    │  2. encode screenshot to base64 │  (up to 20 iterations)
    │  3. send to Gemini Vision       │
    │  4. parse JSON action response  │
    │  5. execute action              │
    └────────────── repeat ───────────┘
    → until agent returns {"action": "done"}
```

**Strengths**: Self-directing, handles page layout changes, demonstrates true "agent intelligence" for the AI rubric criterion.

**Limitations**: Slower (API call per step), requires Gemini API key, non-deterministic.

---

## 6. Error Handling Strategy

| Error Type | Handling |
|-----------|---------|
| Network timeout | `PlaywrightTimeoutError` caught; logged; re-raised |
| Element not found | Fallback selector cascade; raises `RuntimeError` if all fail |
| Transient failures | `_retry()` helper: 3 attempts with 1.5s back-off |
| API errors (Gemini) | Caught per step; agent continues to next iteration |
| Fatal errors | Logged at ERROR level; browser closed in `finally` block |
| User interrupt | `KeyboardInterrupt` caught; graceful exit with code 0 |

---

## 7. Logging Architecture

```
Console output: INFO level (clean, readable for demo)
agent.log file: DEBUG level (full trace for post-run analysis)

Format: 2026-01-01 12:00:00 | INFO     | browser_tools | ✅ Navigation complete
```

Rotating file handler: max 5 MB per file, 3 backup files kept.

---

## 8. Configuration Management

All sensitive values (API keys) and tunable parameters are stored in `.env` and never hardcoded. The `.env.example` template documents every variable. `.env` should be added to `.gitignore` before sharing the project.

---

## 9. Extension Points

To adapt this agent to a different website:
1. Edit `agent/agent_loop.py` → update the selector lists in `run_rule_based_agent()`
2. Update the `SYSTEM_PROMPT` in `run_ai_agent()` to describe the new form

To add a new tool:
1. Add the function to `agent/browser_tools.py`
2. Import and call it in `agent_loop.py`
