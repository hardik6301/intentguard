# IntentGuard — Phases

Build in order. Do not start Phase N+1 until Phase N acceptance is met, unless a later phase only needs a stub that the current phase already defined.

Each phase lists: goal, deliverables, acceptance, and what not to do yet.

---

## Phase 0 — Repository and contracts

**Goal:** Empty app that already encodes the architecture.

**Deliverables**

- Repo layout from `Architecture.md` (folders + stub modules).
- FastAPI hello + health.
- Next.js app with four empty routes and Design.md tokens wired (CSS variables).
- Pydantic + Zod schemas for Intent Contract, Proposed Action, Semantic Assessment, Decision.
- `.env.example` with `DATABASE_URL`, `GEMINI_API_KEY`, Razorpay placeholders.
- Postgres models + Alembic initial migration (tables may be empty of features but exist).

**Acceptance**

- `uvicorn` and `next dev` start.
- Schemas reject a contract with `max_amount` as a string.

**Do not:** Gemini calls, UI polish, Razorpay, agent loop.

---

## Phase 1 — Intent Compiler + persist

**Goal:** Language in, immutable contract out.

**Deliverables**

- `packages/intent_compiler` with Gemini structured output.
- `POST /v1/intents/compile` and `POST /v1/intents` (confirm).
- Screen 1: textarea, compile, contract review (hard vs preferences), confirm.
- Hash + `audit_events` for `intent_compiled`, `intent_activated`.
- Retry-once on invalid JSON; then error UI asking for a numeric budget.

**Acceptance**

- "Buy wireless headphones under ₹5000, preferably Sony or JBL" produces numeric `max_amount=5000` and preferred brands.
- `"probably around five thousand"` does not become a silent 5000 after failed validation.
- Agent cannot update the stored contract (no endpoint, or endpoint returns 409).

**Do not:** agent search, payments, decision hero.

---

## Phase 2 — Hard Constraint Engine

**Goal:** Deterministic money rules with tests.

**Deliverables**

- `constraint_checker.py` covering amount, currency, quantity, category, merchant, time window, expiry, duplicate fingerprint.
- Pytest table tests for approve-budget vs over-budget.
- Wire checker to a `POST /v1/proposals` that accepts a **manual** proposal (no agent yet).

**Acceptance**

- ₹58k vs max ₹60k → hard pass.
- ₹85k vs max ₹60k → hard fail, no LLM involved (`GEMINI` unused in these tests).

**Do not:** semantic LLM, Razorpay.

---

## Phase 3 — Semantic verifier + decision engine

**Goal:** LLM assesses; code decides.

**Deliverables**

- `semantic_verifier.py` structured assessment.
- `risk.py` heuristics for injection phrases and accessory stuffing.
- `decision_engine.py` + `thresholds.py`.
- Persist verification + decision rows.
- Screen 3 minimal: verdict, scores, reasons (can use manual proposal from Phase 2).

**Acceptance**

- Decision unit tests with **stubbed** assessments cover BLOCK / PAUSE / APPROVE matrix.
- Hard fail + semantic 0.99 still BLOCK.
- Semantic 0.61 + hard pass → PAUSE.
- Verifier timeout/invalid → no APPROVE.

**Do not:** live catalog agent, checkout.

---

## Phase 4 — Commerce agent + catalog

**Goal:** A real proposer, not hand-typed JSON (except eval injection).

**Deliverables**

- Fixture catalog: laptops, headphones, food, flights, accessories, one poisoned product page.
- `commerce_agent` tool loop, max steps, emits proposal.
- Screen 2 live activity (poll or SSE).
- `POST /v1/intents/{id}/run`.

**Acceptance**

- End-to-end: confirm intent → agent proposes → engine decides.
- Agent module has no payment import (grep-enforced in review).
- Poisoned page cannot mint a grant.

**Do not:** Razorpay yet. Simulated "would charge" flag is enough.

---

## Phase 5 — Grants + simulated payment + timeout recovery

**Goal:** Money movement is capability-gated.

**Deliverables**

- Grant mint on APPROVE.
- `payment_gateway/simulated.py` ledger.
- `POST /v1/payments`, `GET /v1/payments/{id}`.
- Idempotency keys.
- Forced timeout test + UNKNOWN reconcile.
- Duplicate fingerprint BLOCK.

**Acceptance**

- Call payment without grant → 403, ledger unchanged.
- Timeout path never creates two successes for one grant.
- BLOCKED decision never creates a payment row.

**Do not:** production Razorpay. Test Mode is Phase 6.

---

## Phase 6 — Razorpay Test Mode (optional path)

**Goal:** Judges can complete a test checkout only after APPROVE.

**Deliverables**

- `razorpay_client.py` create order in test mode.
- Web: Razorpay.js with order id from API.
- Webhook or poll to mark `succeeded`.
- Same grant rules as simulated.

**Acceptance**

- Agent still cannot call Razorpay.
- Failed/blocked sessions never show checkout.

If keys are missing, UI uses simulated provider without crashing.

---

## Phase 7 — PAUSE confirmation + audit UI

**Goal:** Human authorization and the timeline judges will screenshot.

**Deliverables**

- Screen 3 PAUSE: original vs proposed, confirm/reject.
- Confirm writes authorization event, then grant, then payment allowed.
- Screen 4 full timeline: compile → contract → search → proposal → hard → semantic → risk → decision → payment/recovery.
- BLOCK copy: "Payment was not initiated."

**Acceptance**

- Sony/JBL vs Bose path pauses and requires a click.
- Audit is complete for a BLOCK budget case.

---

## Phase 8 — Failure injection polish

**Goal:** Designed failures, not accidental ones.

**Deliverables**

- Dev/demo toggles or eval flags: payment timeout, invalid compiler JSON, low semantic, injection SKU.
- UI states for UNKNOWN payment, compile error, agent failure.
- Prompt-injection scenario in catalog + eval.

**Acceptance**

- All four failure types in PRD §12 have a reproducible path.

---

## Phase 9 — Evaluation harness

**Goal:** The thing that separates a demo from a system.

**Deliverables**

- `evaluation/scenarios/scenarios.jsonl` — start ≥ 40, target 100–200.
  Must include: budget pass/fail, vegetarian/chicken, direct vs one-stop, brand substitution pause, accessory stuffing, injection, expiry, duplicate.
- `runner.py`, `metrics.py`.
- CI mode with semantic stubs; live mode with Gemini.
- Report prints **Unsafe Approval Rate** first.

**Acceptance**

- `pytest evaluation` or `python -m evaluation.runner` exits non-zero if UAR exceeds a configured ceiling (set a strict ceiling, e.g. 0 on stubbed hard-constraint cases).

**Do not:** tune prompts only to inflate accuracy while leaving UAR unreported.

---

## Phase 10 — Design pass + demo script

**Goal:** Product looks like an authorization control room, not a template.

**Deliverables**

- Apply `Design.md` fully: type, color, decision hero, timeline, no emoji, no Inter.
- Four-screen walkthrough polish, empty/error/loading.
- Short `docs/DEMO.md` script for the eight PRD demo scenarios (optional file; only if useful).
- Create `Memory.md` with what actually shipped.

**Acceptance**

- Walkthrough of approve, block budget, block semantic, pause substitution, injection, timeout — all against the real API.

---

## Suggested vertical slices (if implementing fast)

If time-boxed for a hackathon, still do **0 → 1 → 2 → 3** before any checkout widget. A beautiful Razorpay popup that the agent can trigger is a failed project.

Minimum judgeable slice:

1. Compile + immutable contract  
2. Hard BLOCK on budget  
3. Semantic BLOCK on vegetarian/chicken  
4. Decision UI + audit  
5. Grant-gated simulated pay  
6. One eval file with UAR  

Razorpay Test Mode is additive after that slice is honest.

---

## Phase completion log

Leave this table empty until work starts. Coding agents copy rows into `Memory.md`.

| Phase | Status | Date | Notes |
| --- | --- | --- | --- |
| 0 | complete | 2026-09-04 | Layout, schemas, health, themed empty routes |
| 1 | complete | 2026-09-04 | Compiler, hash, confirm, Screen 1, immutability |
| 2 | complete | 2026-09-04 | Hard constraints, manual proposals, ₹58k pass / ₹85k fail |
| 3 | complete | 2026-09-04 | Semantic + risk + decision engine; hard fail still BLOCK |
| 4 | complete | 2026-09-04 | Catalog agent, /run, live activity; poison BLOCK, would_charge false |
| 5 | complete | 2026-09-04 | Grant-gated simulated pay; timeout reconcile; missing grant 403 |
| 6 | complete | 2026-09-04 | Razorpay Test Mode after grant; missing keys fall back to simulated |
| 7 | complete | 2026-09-04 | PAUSE confirm/reject; audit spine; unpaid row on BLOCK |
| 8 | complete | 2026-09-04 | Demo flags for JSON fail, low semantic, poison, timeout |
| 9 | complete | 2026-09-04 | 52 scenarios; UAR printed first; ceiling 0 |
| 10 | complete | 2026-09-04 | Design pass, DEMO.md, eight live walkthroughs |
