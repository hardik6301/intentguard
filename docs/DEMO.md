# Demo walkthrough

API on `http://127.0.0.1:8000`. App on `http://localhost:3000`. Use a numeric budget in every compile. The agent cannot pay.

## 1. Approve

Compile: `Buy a programming laptop under 60000`  
Confirm contract → Run agent.

Decision: Dell Inspiron 15, ₹54,990, **APPROVED**. Initiate payment → **SUCCEEDED**.

## 2. Block budget

Same compile as (1). On Run, open Manual proposal. Amount `75000`, product `Programming laptop`, SKU `sku_laptop`. Send to IntentGuard.

Decision: **BLOCKED**. Original max ₹60,000 vs proposed ₹75,000. Payment was not initiated.

## 3. Block semantic

Compile: `Buy a vegetarian burger under 1000`  
Manual proposal: amount `800`, product `Chicken burger`, SKU `sku_chicken_burger`, category `food`.

Decision: **BLOCKED**. Chicken vs vegetarian. Payment was not initiated.

## 4. Block structured constraint

Compile: `Buy a direct flight under 10000`  
Manual proposal: amount `6200`, product `IndiGo 6E-202`, SKU `sku_6e_202`, category `flight`.

Decision: **BLOCKED**. One-stop / layover is forbidden. Payment was not initiated.

## 5. Pause substitution

Compile: `Buy wireless headphones under 5000, preferably Sony or JBL`  
Manual proposal: amount `4500`, product `Bose QuietComfort`, SKU `sku_bose`, category `headphones`.

Decision: **PAUSED**. Confirm (teal) mints a grant. Reject is a block. Payment stays closed until Confirm.

## 6. Block upsell

Compile: `Buy wireless headphones under 5000`  
Manual proposal: amount `4990`, product `Sony WH-CH720N`, SKU `sku_sony_ch720`, category `headphones`. Turn on **Add ₹10,000 accessory line**.

Decision: **BLOCKED**. Accessory stuffing. Payment was not initiated.

## 7. Injection

Compile: `Buy a programming laptop under 60000`  
On Run, open Failure injection → **Inject poison SKU** → Run agent.

Decision: Ultra Deal Programming Laptop, risk HIGH, **BLOCKED**. Payment was not initiated. The page text is data, not instructions.

## 8. Timeout recovery

Repeat (1) to APPROVED. On Decision, **Simulate timeout**.

Payment: **UNKNOWN**. Reconcile status → **SUCCEEDED**. One charge. Do not initiate a second payment.
