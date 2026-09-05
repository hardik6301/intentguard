# Memory

Living log of what actually exists. Do not treat planned phases as done.

## Current phase

Phase 11 complete. Judge surface shipped on top of phases 0–10.

## What shipped (Phase 0)

- Repo layout, FastAPI `/health`, Pydantic/Zod schemas, SQLAlchemy + Alembic, themed empty routes.

## What shipped (Phase 1)

- `IntentCompiler` with structured JSON, one validation retry, then fail-safe.
- Budgets must appear as explicit numerals (`₹5,000`, `5000`). Word amounts such as "five thousand" are rejected. The compiler will not invent a number.
- Canonical SHA-256 hash. Confirm compares hashes. `PATCH`/`PUT` return 409.
- `POST /v1/intents/compile` persists a draft + `intent_compiled` audit event.
- `POST /v1/intents/` activates + `intent_activated`.
- `GET /v1/intents/{id}`.
- Screen 1: compile, contract preview (hard vs preferences), confirm, then `/intents/{id}/run`.
- Gemini is used when `GEMINI_API_KEY` is set. Otherwise `HeuristicJsonClient` (same grounding rules) so local compile works.
- Local DB default is SQLite (`sqlite:///./intentguard.db`). `create_all` on API startup. Schema changes may require deleting that file.

## What shipped (Phase 2)

- Deterministic `check_constraints`. No LLM imports. Covers budget, currency, quantity, category, merchant allowlist, forbidden/must-include, location, time window, expiry, line-item sum, duplicate fingerprint.
- `POST /v1/intents/{id}/proposals` for manual proposals. Intent must be `active`.
- Screen 2: manual proposal form.

## What shipped (Phase 3)

- `semantic_verifier.py`: structured assessment only. Retry once on invalid JSON, then `error=true` and `semantic_match=null`. Timeout/exception fail closed the same way. The LLM schema has no verdict. Rejects output that includes `verdict`/`decision`.
- `heuristic_semantic.py` when Gemini is unset: Sony/JBL vs Bose → 0.61 + major substitution.
- `risk.py`: injection phrases (`ignore previous`, `proceed to payment`, …) and accessory stuffing (extra SKUs / accessory line items). High injection → `injection_high`.
- `decision_engine.py` + `packages/policy_engine/thresholds.py` (`POLICY_VERSION=2026.09.0`, block below 0.60, approve at/above 0.85). Pure function. Hard fail cannot be rescued by a high semantic score. Invalid/missing score cannot APPROVE.
- Persist `verifications` + `decisions`. Audit: `semantic_assessed`, `risk_assessed`, `decision_made`.
- `GET /v1/intents/{id}/decision` returns the latest evaluation.
- Screen 3: amount, hard/semantic/risk rows, verdict stamp `APPROVED`/`PAUSED`/`BLOCKED`. BLOCK compares original vs proposed and states payment was not initiated. PAUSE asks whether it still matches.
- Run submits a proposal then navigates to Decision.

## What shipped (Phase 4)

- Fixture catalog: laptops, headphones, food, flights, accessories, and one poisoned Ultra Deal page (`sku_poison_deal`).
- Deterministic `commerce_agent` tool loop (`search_catalog`, `get_product`, `read_page_fixture`). Max 8 tool calls. No Gemini. No payment import.
- Clean laptop queries skip poisoned pages and pick Dell Inspiron 15 (₹54,990). Naming the Ultra Deal SKU proposes the poisoned page so the engine can BLOCK.
- `POST /v1/intents/{id}/run` and `GET /v1/intents/{id}/activity`. Draft intents return 409. `would_charge` is always false.
- Screen 2: goal as title, Run agent, staggered activity rail, proposed-transaction bezel, then Decision. Manual proposal remains behind an eval-injection disclosure.
- Poisoned page: hard pass + high injection → BLOCKED. Payment was not initiated. No grant.

## What shipped (Phase 5)

- Mint a single-use HMAC grant on `APPROVE` only, locked to intent, proposal, amount, and currency. `PAUSE`/`BLOCK` never mint.
- Simulated ledger in `packages/payment_gateway/simulated.py`. `POST /v1/payments` and `GET /v1/payments/{id}`. Missing/invalid grant → 403, ledger unchanged.
- Grant is marked used in the same transaction as the payment row. Idempotency key is unique. One grant cannot produce two succeeded ledger charges.
- Timeout: `force_timeout` on simulated create returns `UNKNOWN`. GET reconciles (retry create only if the provider has no success). Committed-timeout path does not double-charge.
- Duplicate fingerprint after approval is a hard `BLOCK` (amount normalized to 2 decimal places).
- Decision screen: Initiate payment on APPROVE; SUCCEEDED after charge; UNKNOWN shows Reconcile status. BLOCK still says payment was not initiated and has no pay control.
- Agent still cannot import payment code. `would_charge` on `/run` stays false.

## What shipped (Phase 6)

- `razorpay_client.py`: Test Mode order create/fetch, checkout signature, webhook signature. Live REST only when both keys are set. Tests use `FakeRazorpay`.
- Same grant rules as simulated. Missing grant → 403 and no Razorpay order. BLOCK never mints a grant or returns checkout.
- `POST /v1/payments` with `PAYMENT_PROVIDER=razorpay` and keys creates a pending order + checkout payload (`key_id`, `order_id`, amount in paise). Confirm via `POST /v1/payments/{id}/confirm` or `POST /v1/payments/webhook`. GET payment polls order status and will not create a second paid order.
- If keys are missing, provider falls back to the simulated ledger. UI does not load Razorpay.js. `GET /v1/payments/config` reports the effective provider.
- Decision: APPROVE can open Razorpay Checkout.js after the grant. BLOCK still says payment was not initiated and has no checkout control.
- Agent source still cannot mention or import Razorpay.

## What shipped (Phase 7)

- Engine verdict stays `PAUSE` on the decision row. Resolution is inferred: grant → `confirmed`, intent blocked → `rejected`, else `pending`.
- `POST /v1/decisions/{id}/confirm` with `{ "action": "confirm" | "reject" }`. Confirm mints a grant and allows payment. Reject is `user_rejected` BLOCK: no grant, `pause_rejected` + `payment_not_initiated`. Confirm twice / confirm on BLOCK → 409.
- Screen 3 PAUSE pending: original vs proposed, “Does this still match what you authorized?”, Confirm (teal) / Reject (hairline + block text). Confirmed shows APPROVED + payment. Rejected shows BLOCKED and “Payment was not initiated.”
- `GET /v1/intents/{id}/audit` returns oldest-first timeline with titles and tone. BLOCK (and pause reject) write `payment_not_initiated`.
- Screen 4: time rail + hairline spine. Block-colored title on “Payment was not initiated.”
- Sony/JBL vs Bose QuietComfort pauses until a click. Budget ₹85k vs ₹60k audit is complete through the unpaid row.

## What shipped (Phase 8)

- Designed failure flags, not accidents. `GET /v1/eval/failures` lists the four PRD §12 paths. Phase 9 harness stays unimplemented.
- Invalid compiler JSON: `force_invalid_json` uses `BrokenJsonClient`, retries once, then 422. Never invents a budget. Create screen has the toggle plus a word-amount prompt. Contract preview shows the fail-safe copy.
- Low semantic: `POST /run` with `inject=low_semantic` forces 0.61 → PAUSE, no grant.
- Prompt injection: `inject=poison` makes the agent propose `sku_poison_deal`. Risk is high. BLOCK. No pay. Evaluated against the contract, not the page.
- Payment timeout: Decision has Simulate timeout (`force_timeout`). UNKNOWN, then Reconcile. GET does not double-charge.
- Force agent failure: 422, `agent_failed` audit, no proposal. Run screen stays put and says payment was not initiated.

## What shipped (Phase 9)

- `evaluation/scenarios/scenarios.jsonl`: 52 labeled rows. Tags include budget, food, flight, substitution, injection, accessory, expiry, duplicate, semantic.
- `evaluation/runner.py` + `metrics.py`. CI default `EVAL_MODE=deterministic` uses `semantic_stub` (no Gemini). `EVAL_MODE=live` uses Gemini when the key is set.
- Report prints **Unsafe Approval Rate** first. Ceiling is 0. Hard-constraint subset UAR is also 0. `python -m evaluation.runner` and `make eval` exit non-zero if UAR exceeds the ceiling.
- `POST /v1/eval/run` returns the deterministic report. Agent still cannot pay.

## What shipped (Phase 10)

- Design tokens applied: Geist + Geist Mono, Signal Teal, verdict stamps with a thin ring, double-bezel panels, shimmer skeletons, staggered contract rows, audit live clock.
- Empty Decision copy points at Run. Compile fail still asks for a numeric budget.
- Manual proposal can add a ₹10,000 accessory line for the upsell demo.
- `docs/DEMO.md` walks all eight PRD scenarios against the real API: approve, budget, vegetarian/chicken, direct/one-stop, Bose pause, accessory upsell, poison injection, timeout reconcile.

## What shipped (Phase 11)

- `/eval` dashboard: Unsafe Approval Rate as the hero numeral, engine metrics in a bezel, mismatches, labeled case spine.
- `POST /v1/eval/run` returns UAR, mismatches, and cases. Note states this is policy-engine UAR on stubbed scores.
- `GET /v1/eval/runtime` reports compiler/semantic source, payment provider, SQLite vs Postgres.
- Decision stamp line shows `assessment Gemini` or `assessment local heuristic`.
- GitHub Actions: Python 3.12, pytest, `evaluation.runner` (fails if UAR > 0).
- README is the submission surface. `docs/PITCH.md` is the three-scene, five-minute script.
- UI polish from the design pass: secondary Confirm, truncated session id, structured empty wells, `prefers-reduced-motion`.

## How to run

```text
PYTHONPATH=. .venv/bin/python -m uvicorn apps.api.main:app --reload --port 8000
cd apps/web && npm run dev
PYTHONPATH=. .venv/bin/pytest
PYTHONPATH=. .venv/bin/python -m evaluation.runner
```

Walkthrough: `docs/DEMO.md`.

Watchfiles often does not reload in this folder (em dash in the path). Restart uvicorn after backend changes.

## Do not invent

- Extra catalog SKUs, production Postgres, public deploy.
