"use client";

import { Check, X } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useState, type ReactNode } from "react";

import { Bezel } from "@/components/Bezel";
import { Eyebrow } from "@/components/Eyebrow";
import { PrimaryButton } from "@/components/PrimaryButton";
import { ApiError, submitProposal, type ProposalEvaluation } from "@/lib/api";

function rupees(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

const inputClass =
  "min-h-11 w-full rounded-[1.25rem] border border-hairline bg-raised px-4 text-base text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas";

type ManualProposalFormProps = {
  intentId: string;
  defaultCategory?: string | null;
  maxAmount?: number;
};

export function ManualProposalForm({
  intentId,
  defaultCategory,
  maxAmount,
}: ManualProposalFormProps) {
  const router = useRouter();
  const [amount, setAmount] = useState(maxAmount ? String(Math.max(maxAmount - 2000, 1)) : "58000");
  const [name, setName] = useState("Programming laptop");
  const [sku, setSku] = useState("sku_laptop");
  const [category, setCategory] = useState(defaultCategory ?? "laptop");
  const [merchant, setMerchant] = useState("demo_catalog");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [history, setHistory] = useState<ProposalEvaluation[]>([]);
  const [addAccessory, setAddAccessory] = useState(false);

  async function onSubmit() {
    setError(null);
    setSubmitting(true);
    try {
      const parsedAmount = Number(amount);
      if (!Number.isFinite(parsedAmount) || parsedAmount <= 0) {
        throw new ApiError("Amount must be a number.", 400);
      }
      const product = {
        id: sku.trim() || "sku_manual",
        name: name.trim() || "Proposed item",
        category: category.trim() || null,
      };
      const lineItems = addAccessory
        ? [
            { sku: product.id, name: product.name, amount: parsedAmount, quantity: 1 },
            {
              sku: "sku_warranty",
              name: "Premium extended warranty",
              amount: 10000,
              quantity: 1,
            },
          ]
        : undefined;
      const evaluation = await submitProposal(intentId, {
        amount: addAccessory ? parsedAmount + 10000 : parsedAmount,
        merchant,
        product,
        line_items: lineItems,
      });
      setHistory((current) => [evaluation, ...current]);
      router.push(`/intents/${intentId}/decision`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Proposal could not be checked.");
    } finally {
      setSubmitting(false);
    }
  }

  const latest = history[0] ?? null;
  const displayedAmount = latest ? latest.proposal.amount : Number(amount);
  const hardPassed = latest?.hard.passed;

  return (
    <div className="grid grid-cols-1 gap-8 md:grid-cols-[2fr_1fr] md:gap-10">
      <section className="flex flex-col gap-8">
        <div className="flex flex-col gap-3">
          <Eyebrow>Manual proposal</Eyebrow>
          <h1 className="max-w-[18ch] text-[clamp(1.75rem,3vw,2.75rem)] font-medium leading-none tracking-tight text-ink">
            Submit a transaction to IntentGuard
          </h1>
          <p className="max-w-[65ch] text-base leading-relaxed text-muted">
            The agent is not running yet. Enter a proposed purchase. Hard constraints are checked
            in code. The decision screen shows the verdict. This screen cannot pay.
          </p>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Field label="Amount" hint="INR numeral">
            <input
              value={amount}
              onChange={(event) => setAmount(event.target.value)}
              inputMode="numeric"
              className={`${inputClass} font-mono tracking-[0.04em]`}
            />
          </Field>
          <Field label="Merchant">
            <input
              value={merchant}
              onChange={(event) => setMerchant(event.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Product">
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="Category">
            <input
              value={category}
              onChange={(event) => setCategory(event.target.value)}
              className={inputClass}
            />
          </Field>
          <Field label="SKU">
            <input
              value={sku}
              onChange={(event) => setSku(event.target.value)}
              className={`${inputClass} font-mono tracking-[0.04em]`}
            />
          </Field>
        </div>
        <button
          type="button"
          onClick={() => setAddAccessory((value) => !value)}
          className={`inline-flex min-h-11 w-fit cursor-pointer items-center rounded-full border px-4 text-sm transition-[color,background-color,transform] duration-200 ease-intent active:scale-[0.98] ${
            addAccessory ? "border-teal/50 bg-teal/15 text-teal" : "border-hairline text-muted hover:text-ink"
          }`}
        >
          {addAccessory ? "Accessory line on" : "Add ₹10,000 accessory line"}
        </button>
        {error ? <p className="text-sm text-block">{error}</p> : null}
        <PrimaryButton onClick={onSubmit} disabled={submitting}>
          {submitting ? "Checking" : "Send to IntentGuard"}
        </PrimaryButton>
        {history.length > 0 ? (
          <ol className="relative flex flex-col border-l border-hairline pl-5">
            {history.map((item, index) => (
              <li key={item.proposal_id} className="relative py-3">
                <span
                  className={`absolute -left-[1.4rem] top-5 h-2.5 w-2.5 rounded-full ${
                    item.hard.passed ? "bg-approve" : "bg-block"
                  }`}
                />
                <p className="font-mono text-sm tracking-[0.04em] text-ink">
                  {rupees(item.proposal.amount)}
                </p>
                <p
                  className={`text-[11px] font-medium uppercase tracking-[0.16em] ${
                    item.hard.passed ? "text-approve" : "text-block"
                  }`}
                >
                  {item.hard.passed ? "Hard pass" : "Hard fail"}
                  {index === 0 ? " · latest" : ""}
                </p>
              </li>
            ))}
          </ol>
        ) : null}
      </section>
      <Bezel>
        <div className="flex flex-col gap-6 p-6 md:p-8">
          <Eyebrow>Proposed transaction</Eyebrow>
          <p className="font-mono text-[clamp(2rem,4vw,3rem)] leading-none tracking-tight text-ink">
            {Number.isFinite(displayedAmount) && displayedAmount > 0 ? rupees(displayedAmount) : "—"}
          </p>
          {maxAmount ? (
            <p className="font-mono text-sm tracking-[0.04em] text-faint">
              Max authorized {rupees(maxAmount)}
            </p>
          ) : null}
          {latest ? (
            <div className="flex flex-col gap-4">
              <p className="text-base leading-relaxed text-ink">{latest.proposal.product.name}</p>
              <div className="flex items-center justify-between border-t border-hairline py-3">
                <span className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
                  Hard constraints
                </span>
                <span
                  className={`inline-flex items-center gap-2 text-[11px] font-medium uppercase tracking-[0.16em] ${
                    hardPassed ? "text-approve" : "text-block"
                  }`}
                >
                  {hardPassed ? <Check size={14} weight="bold" /> : <X size={14} weight="bold" />}
                  {hardPassed ? "Pass" : "Fail"}
                </span>
              </div>
              {latest.hard.failures.map((failure) => (
                <p key={failure.code} className="text-sm leading-relaxed text-block">
                  {failure.message}
                </p>
              ))}
              <p className="font-mono text-[11px] tracking-[0.04em] text-faint">
                {latest.fingerprint.slice(0, 16)}
              </p>
              <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
                {hardPassed
                  ? "Hard constraints hold. Open Decision for the verdict. Payment was not initiated."
                  : "Payment was not initiated."}
              </p>
            </div>
          ) : (
            <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
              Submit a proposal to see the hard-constraint result.
            </p>
          )}
        </div>
      </Bezel>
    </div>
  );
}

function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: ReactNode;
}) {
  return (
    <div className="flex flex-col gap-2">
      <label className="text-sm text-ink">{label}</label>
      {hint ? <p className="text-sm text-muted">{hint}</p> : null}
      {children}
    </div>
  );
}
