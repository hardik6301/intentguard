# IntentGuard

**The authorization layer for AI agents.**

Agents may search, compare, and propose. They may not spend. IntentGuard checks that a proposed payment still matches what the user originally authorized, then returns `APPROVE`, `PAUSE`, or `BLOCK`. Only an approved (or user-confirmed) grant can reach the payment layer.

A normal spending limit asks: *is this under ₹60,000?*  
IntentGuard also asks: *is this still the lightweight programming laptop the user authorized?*

```text
User → Intent Contract (immutable)
         ↓
Commerce agent (search / propose, never pay)
         ↓
Hard constraints (code) + semantic assessment (LLM) + risk (code)
         ↓
Decision engine (code) → APPROVE | PAUSE | BLOCK
         ↓
HMAC grant → simulated ledger or Razorpay Test Mode
```

**AI handles ambiguity. Deterministic systems enforce guarantees. The user owns authorization.**

The LLM never emits the verdict, never mutates the contract, and never calls Razorpay.

## Why this exists

An agent given *“Buy a lightweight programming laptop under ₹60,000”* can propose a gaming laptop at ₹58,000. Budget passes. Intent does not. Payment APIs are good at amounts. They are not good at authorized meaning.

IntentGuard sits between the agent and the rail. The agent package cannot import the payment package. Missing grant → 403. BLOCK never creates an order.

## Unsafe Approval Rate

Primary eval metric: share of labeled `BLOCK` cases the engine approved.

```text
make eval
```

The report prints **UNSAFE APPROVAL RATE** first. Ceiling is 0. Deterministic mode stubs semantic scores and measures the **decision engine**, not Gemini quality. That is intentional. Live Gemini is `EVAL_MODE=live`.

UI: [http://localhost:3000/eval](http://localhost:3000/eval)

## Screens

| Route | Job |
| --- | --- |
| `/` | Compile language into a hashed contract |
| `/intents/{id}/run` | Catalog agent proposes. It cannot charge. |
| `/intents/{id}/decision` | Hard / semantic / risk → verdict stamp |
| `/intents/{id}/audit` | Oldest-first authorization log |
| `/eval` | UAR first, then mismatches |

## Run

Python 3.12+. Local database is SQLite (`sqlite:///./intentguard.db`). Architecture targets Postgres in production; do not treat the local file as that.

```text
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -m uvicorn apps.api.main:app --reload --port 8000
```

```text
cd apps/web && npm install && npm run dev
```

API: `http://127.0.0.1:8000/health`  
App: `http://localhost:3000`

Optional `.env`: `GEMINI_API_KEY` (compiler + semantic). Without it, local heuristics still refuse to invent a budget from words. Razorpay Test Mode is grant-gated and optional; missing keys stay on the simulated ledger.

```text
.venv/bin/pytest
make eval
```

The folder name contains an em dash; uvicorn `--reload` often misses file changes. Restart the API after backend edits.

## Docs

| File | Role |
| --- | --- |
| [PRD.md](./PRD.md) | Product contract |
| [Architecture.md](./Architecture.md) | Trust boundaries |
| [Rules.md](./Rules.md) | What the LLM may not do |
| [Design.md](./Design.md) | Control-room visual system |
| [docs/DEMO.md](./docs/DEMO.md) | Eight operator walkthroughs |
| [docs/PITCH.md](./docs/PITCH.md) | Five-minute judge script |

[Memory.md](./Memory.md) is what actually shipped.
