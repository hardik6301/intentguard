"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";

import { Bezel } from "@/components/Bezel";
import { ContractPreview } from "@/components/ContractPreview";
import { Eyebrow } from "@/components/Eyebrow";
import { FailureInject, InjectChip } from "@/components/FailureInject";
import { PrimaryButton } from "@/components/PrimaryButton";
import { SecondaryButton } from "@/components/SecondaryButton";
import { ApiError, compileIntent, confirmIntent } from "@/lib/api";
import type { IntentContract } from "@/lib/schemas";

export function CreateIntentForm() {
  const router = useRouter();
  const [rawRequest, setRawRequest] = useState("");
  const [compiling, setCompiling] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [intentId, setIntentId] = useState<string | null>(null);
  const [contract, setContract] = useState<IntentContract | null>(null);
  const [status, setStatus] = useState<"draft" | "active">("draft");
  const [forceInvalidJson, setForceInvalidJson] = useState(false);
  const [errorDetails, setErrorDetails] = useState<string[]>([]);

  async function onCompile() {
    setError(null);
    setErrorDetails([]);
    setCompiling(true);
    try {
      const result = await compileIntent(rawRequest, { force_invalid_json: forceInvalidJson });
      setIntentId(result.intent_id);
      setContract(result.contract);
      setStatus("draft");
    } catch (caught) {
      setContract(null);
      setIntentId(null);
      setError(
        caught instanceof ApiError
          ? caught.message
          : "Compile failed. Enter a numeric budget. IntentGuard will not invent one.",
      );
      setErrorDetails(caught instanceof ApiError ? caught.details : []);
    } finally {
      setCompiling(false);
    }
  }

  async function onConfirm() {
    if (!intentId) {
      return;
    }
    setError(null);
    setConfirming(true);
    try {
      const result = await confirmIntent(intentId);
      setStatus("active");
      setContract(result.contract);
      router.push(`/intents/${result.intent_id}/run`);
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Could not confirm this contract.");
    } finally {
      setConfirming(false);
    }
  }

  const canCompile = rawRequest.trim().length > 0 && !compiling && !confirming;
  const hasDraft = Boolean(intentId && contract);

  return (
    <main className="grid grid-cols-1 gap-8 md:grid-cols-12 md:gap-10">
      <section className="flex flex-col gap-6 md:col-span-7">
        <div className="flex flex-col gap-3">
          <Eyebrow>New authorization</Eyebrow>
          <h1 className="max-w-[18ch] text-[clamp(1.75rem,3vw,2.75rem)] font-medium leading-none tracking-[-0.04em] text-ink">
            What should the agent be allowed to do?
          </h1>
          <p className="max-w-[65ch] text-base leading-[1.55] text-muted">
            Write the task in plain language. IntentGuard will compile it into an immutable
            contract before anything can be purchased.
          </p>
        </div>
        <div className="flex flex-col gap-2">
          <label htmlFor="intent" className="text-sm text-ink">
            Task
          </label>
          <p className="text-sm text-muted">
            Include a numeric budget. IntentGuard will not invent one.
          </p>
          <textarea
            id="intent"
            name="intent"
            value={rawRequest}
            onChange={(event) => setRawRequest(event.target.value)}
            rows={10}
            placeholder="Buy me a lightweight programming laptop under ₹60,000"
            className="min-h-[10rem] w-full resize-y rounded-[1.25rem] border border-hairline bg-raised px-4 py-3 text-base leading-relaxed text-ink outline-none placeholder:text-muted focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
          />
          {error ? <p className="text-sm text-block">{error}</p> : null}
          {errorDetails.length > 0 ? (
            <ul className="flex flex-col gap-1">
              {errorDetails.map((detail) => (
                <li key={detail} className="font-mono text-[11px] tracking-[0.04em] text-faint">
                  {detail}
                </li>
              ))}
            </ul>
          ) : null}
        </div>
        <div className="flex flex-wrap gap-3">
          {hasDraft ? (
            <>
              <PrimaryButton onClick={onConfirm} disabled={confirming || compiling}>
                {confirming ? "Confirming" : "Confirm contract"}
              </PrimaryButton>
              <SecondaryButton onClick={onCompile} disabled={!canCompile}>
                {compiling ? "Compiling" : "Compile again"}
              </SecondaryButton>
            </>
          ) : (
            <>
              <PrimaryButton onClick={onCompile} disabled={!canCompile}>
                {compiling ? "Compiling" : "Compile intent"}
              </PrimaryButton>
              <SecondaryButton onClick={onConfirm} disabled>
                Confirm contract
              </SecondaryButton>
            </>
          )}
        </div>
        <FailureInject>
          <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
            Invalid compiler JSON is retried once, then fail-safe. IntentGuard will not invent a
            budget.
          </p>
          <div className="flex flex-wrap gap-2">
            <InjectChip
              active={forceInvalidJson}
              onClick={() => setForceInvalidJson((value) => !value)}
            >
              Force invalid compiler JSON
            </InjectChip>
            <InjectChip
              onClick={() =>
                setRawRequest("Buy a programming laptop, probably around five thousand")
              }
            >
              Word-amount prompt
            </InjectChip>
          </div>
        </FailureInject>
      </section>

      <aside className="md:col-span-5">
        <Bezel>
          <ContractPreview
            contract={contract}
            status={status}
            loading={compiling}
            error={error}
          />
        </Bezel>
      </aside>
    </main>
  );
}
