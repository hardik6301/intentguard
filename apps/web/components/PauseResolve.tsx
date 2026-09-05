"use client";

import { useState } from "react";

import { PrimaryButton } from "@/components/PrimaryButton";
import { ApiError, resolvePause, type ProposalEvaluation } from "@/lib/api";

type PauseResolveProps = {
  decisionId: string;
  onResolved: (record: ProposalEvaluation) => void;
};

export function PauseResolve({ decisionId, onResolved }: PauseResolveProps) {
  const [busy, setBusy] = useState<"confirm" | "reject" | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function onAction(action: "confirm" | "reject") {
    setBusy(action);
    setError(null);
    try {
      onResolved(await resolvePause(decisionId, action));
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "The pause could not be resolved.");
    } finally {
      setBusy(null);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-3">
        <PrimaryButton onClick={() => void onAction("confirm")} disabled={busy !== null}>
          {busy === "confirm" ? "Confirming" : "Confirm"}
        </PrimaryButton>
        <button
          type="button"
          onClick={() => void onAction("reject")}
          disabled={busy !== null}
          className="inline-flex min-h-11 items-center rounded-full border border-hairline px-6 py-3 text-sm text-block transition-transform duration-500 ease-intent active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40"
        >
          {busy === "reject" ? "Rejecting" : "Reject"}
        </button>
      </div>
      {error ? <p className="text-sm text-block">{error}</p> : null}
    </div>
  );
}
