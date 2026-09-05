# Five-minute pitch

Record against the live app. Three scenes. Do not walk all eight operator paths.

Open Create. Say the invariant once: **agents propose; IntentGuard decides; payment requires a grant.**

## 0:00–0:40 — The problem

> A user says: buy a lightweight programming laptop under ₹60,000.
> A spending limit only checks the number.
> An agent can still buy a gaming laptop at ₹58,000.
> IntentGuard authorizes meaning, then money.

Show the empty Create screen. Compile is the only teal action.

## 0:40–2:10 — APPROVE

Compile: `Buy a programming laptop under 60000`  
Confirm contract → Run agent.

Decision: Dell Inspiron 15, ₹54,990.

Point at the three rows, then the stamp:

- Hard constraints: Pass
- Semantic match: high
- Risk: LOW
- **APPROVED**

Initiate payment → **SUCCEEDED**. Say: the agent never held a key. The grant is single-use and spent.

## 2:10–3:20 — PAUSE

New intent: `Buy wireless headphones under 5000, preferably Sony or JBL`  
Manual proposal: Bose QuietComfort, ₹4,500.

Decision: **PAUSED**. Original vs proposed. Confirm / Reject.

Say: budget passed. Brand substitution is not silent. Confirm mints a grant. Reject writes “Payment was not initiated.”

## 3:20–4:20 — BLOCK

Pick one. Poison is sharper for judges.

Same laptop intent. Failure injection → **Inject poison SKU** → Run.

Decision: Ultra Deal, risk HIGH, **BLOCKED**.  
Copy on screen: **Payment was not initiated.** No grant. No Razorpay order.

If time: open Audit. Oldest event at the top. Point at the unpaid row.

## 4:20–5:00 — The system, not the demo

Open `/eval`.

> Unsafe Approval Rate first. Ceiling zero.
> This suite measures the decision engine. The LLM does not emit APPROVE.
> Hard fail cannot be rescued by a 0.99 score.

Close on the grant rule: **no grant, no charge.**
