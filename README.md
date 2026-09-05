# IntentGuard

**The authorization layer for AI agents.**

Agents may search, compare, and propose. They may not spend. IntentGuard checks that a proposed payment still matches the user’s original intent, then returns `APPROVE`, `PAUSE`, or `BLOCK`. Only an approved (or user-confirmed) grant can reach the payment layer.

Start here:

| Doc | Role |
| --- | --- |
| [PRD.md](./PRD.md) | What we are building and why |
| [Architecture.md](./Architecture.md) | Stack, folders, APIs, data, trust boundaries |
| [Rules.md](./Rules.md) | Hard constraints on how the AI (and we) may code |
| [Phases.md](./Phases.md) | Build order |
| [Design.md](./Design.md) | Visual system |
| [docs/DEMO.md](./docs/DEMO.md) | Eight-scenario walkthrough |

[Memory.md](./Memory.md) tracks what actually shipped.

## Run

Use Python 3.12+ (`brew install python@3.12`). From the repo root:

```text
/opt/homebrew/bin/python3.12 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

Then:

```text
.venv/bin/python -m uvicorn apps.api.main:app --reload --port 8000
.venv/bin/pytest
```

Web:

```text
cd apps/web && npm install && npm run dev
```

API: `http://127.0.0.1:8000/health`  
App: `http://localhost:3000`

Optional: set `GEMINI_API_KEY` in `.env`. Without it, compile still runs locally but will not invent a budget from words.

Core rule: **AI handles ambiguity. Deterministic systems enforce guarantees. The user owns authorization. IntentGuard protects the transaction.**
