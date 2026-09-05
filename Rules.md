# IntentGuard — Rules

Boundaries for anyone (human or AI) implementing this repo. If a request conflicts with this file, this file wins.

---

## 0. The non-negotiable sentence

**AI agents are allowed to think and propose. IntentGuard decides whether they are still authorized to act.**

The LLM never executes a payment, never mutates an Intent Contract, and never emits the final `APPROVE | PAUSE | BLOCK` enum as an unvalidated string that is trusted blindly.

---

## 1. Architecture rules

1. Keep the stack from `Architecture.md`. Do not introduce LangChain, LlamaIndex, Redis, Kafka, Prisma, MongoDB, or extra microservices.
2. One FastAPI app, one Next.js app, one PostgreSQL.
3. Put verification math in `packages/verification_engine`. Put Gemini calls only in `intent_compiler` and `semantic_verifier`.
4. `packages/commerce_agent` must not import `packages/payment_gateway` except via HTTP to `/v1/intents/{id}/proposals` if it is a separate worker — preferably it is an in-process service with **no payment import**.
5. Do not put Razorpay secrets in Next.js server actions that the agent route can reach. Payment stays in `apps/api` payment router + `payment_gateway`.

---

## 2. Authorization and payments

1. The agent **cannot** create Razorpay orders, open checkout, capture payments, or read `RAZORPAY_KEY_SECRET`.
2. Payment APIs require a single-use grant minted only after `APPROVE` or after an explicit user confirm on `PAUSE`.
3. Grant is locked to `intent_id + proposal_id + amount + currency`. Mismatch → reject.
4. Never retry a payment blindly after timeout. Load status by idempotency key / provider id first.
5. Never auto-retry a **succeeded** payment.
6. Simulated provider is the default. Razorpay Test Mode is optional and still grant-gated.
7. If unsure whether a payment happened, status is `UNKNOWN`, not `FAILED` and not `SUCCESS`.

---

## 3. Intent Contract

1. After user confirm, the contract JSON is immutable. No PATCH of budget, dates, or constraints by the agent or verifier.
2. User-requested changes create an amendment event or a new intent. Both are audited.
3. Do not store the contract only in chat history. Persist hashed JSON in PostgreSQL.
4. `max_amount` is a number. Reject `"around 5k"`, `"cheap"`, `"reasonable"`. Ask the user.
5. Do not "helpfully" raise the budget to make a proposal pass.

---

## 4. LLM usage

### Allowed

- Compile natural language → schema-constrained contract.
- Semantic assessment: score, reasons, substitution severity.
- Optional injection classification of **untrusted** product text (assessment only).

### Forbidden

- LLM chooses `verdict`.
- LLM writes SQL, payment payloads, or grant tokens.
- LLM output used without Pydantic/Zod validation.
- Chain-of-thought dumped into the audit UI as if it were a guarantee.
- Second "judge" LLM that can override hard constraint failures.

### Structured output

Always use schema / JSON mode. Parse with Pydantic. On failure: one retry with validator errors. Then fail safe (`CompileError` or semantic `error=true`). **Never guess financial constraints.**

---

## 5. Decision engine

1. Pure function. Unit-tested. Thresholds only in `packages/policy_engine/thresholds.py`.
2. Hard constraint failure → `BLOCK`. The semantic score cannot rescue it.
3. Default bands: `< 0.60` BLOCK, `0.60–0.85` PAUSE, `>= 0.85` eligible for APPROVE if risk is low.
4. Invalid or missing semantic score → cannot APPROVE.
5. High injection / untrusted-instruction flag → cannot APPROVE.
6. Do not bury new policy in Gemini prompts. Change `thresholds.py` and bump `POLICY_VERSION`.

---

## 6. Untrusted content

1. Authority order: **Intent Contract > user confirmation events > agent rationale > tool/page content**.
2. Product pages, search snippets, and tool dumps are data, not instructions.
3. Fixture pages for demo **must** include an injection sample. Eval must not `APPROVE` it.
4. Do not concatenate untrusted text into the compiler system prompt as if it were the user.

---

## 7. Libraries

### Use

- Next.js App Router, TypeScript, Tailwind, shadcn/ui **restyled per Design.md**
- Zod on the web
- FastAPI, Pydantic v2, SQLAlchemy 2, Alembic
- Official Google Gemini SDK
- `httpx` for tests
- Razorpay official SDK or REST only inside `payment_gateway`
- `@phosphor-icons/react` for icons (see Design.md)

### Do not use

- Inter font, generic Lucide-as-default look, stock shadcn violet theme
- LangChain / agent frameworks that give the model a `pay` tool
- `eval`, `exec`, or shelling out to run model-generated code
- Emojis in UI copy, code comments used as UX, or commit messages as product text
- `h-screen` for full-height sections (`min-h-[100dvh]` instead)

### Check before adding a dependency

Read `package.json` / `pyproject.toml`. If missing, add it explicitly. Do not assume `framer-motion` or `lucide-react` exist.

---

## 8. Frontend rules

1. Four screens as specified. Shared `intent_id` state must match across run / decision / audit.
2. Follow `Design.md`. No AI-purple glows, no Inter, no centered marketing hero on the app chrome.
3. Decision screen is the hero: amount, hard checks, semantic %, risk, verdict.
4. Blocked copy must state that payment was **not** initiated.
5. Loading: skeletons matching layout, not a generic centered spinner as the only state.
6. Empty and error states are required for compile failure, agent failure, and payment `UNKNOWN`.
7. No Gemini keys in the browser.
8. Client components only where interactivity or streaming requires it.

---

## 9. Testing rules

1. Constraint checker and decision engine tests: **no network, no API keys**.
2. Payment tests: fake provider + timeout + duplicate + missing grant.
3. Compiler tests: invalid JSON, non-numeric budget, valid laptop/flight/food examples (LLM mocked).
4. Do not snapshot-test huge LLM prose. Assert enums, amounts, hashes, verdicts.
5. Evaluation: primary metric **Unsafe Approval Rate**. Do not celebrate accuracy if UAR is high.

---

## 10. Errors and fail-closed behavior

| Situation | Do |
| --- | --- |
| Hard constraint fail | BLOCK, no grant |
| LLM invalid | retry once, then user/fail; never invent amounts |
| Semantic low / error | PAUSE or BLOCK per engine; never APPROVE |
| Payment timeout | UNKNOWN + reconcile |
| Missing grant | 403, no provider call |
| Ambiguous vegetarian / direct / only | compiler marks hard if language is exclusive |

Fail **open** only for availability of the *agent search*. Fail **closed** for money.

---

## 11. What the coding agent should not do

- Build a landing page instead of the four product screens.
- Fake the decision UI with hardcoded `94%` and `APPROVED` as the only path.
- Let "Run agent" call Razorpay.
- Store secrets in git.
- Rewrite PRD semantics ("we'll just use embeddings for budget").
- Add Memory.md lies about completed phases. Update Memory.md only with what was actually built.
- Implement all phases in one unreviewable dump. Follow `Phases.md` unless the user asks for a specific phase.

---

## 12. Code style

- TypeScript strict. Python type hints on public functions.
- Explicit names: `hard_constraints`, `semantic_match`, `unsafe_approval_rate`.
- No commented-out blocks. No `TODO: pay here`.
- Audit writes go through `audit_service.record(...)` — do not scatter raw inserts.
- Idempotency keys on payments are mandatory.

---

## 13. Demo integrity

Judges will try the budget-over case and the vegetarian/chicken case. Those must be real engine outcomes, not scripted animations that ignore the API.

If a catalog item would make the demo boring, **add catalog SKUs**, do not short-circuit the verifier.
