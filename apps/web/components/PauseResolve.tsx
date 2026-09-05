"use client";

import { useState } from "react";

import { PrimaryButton } from "@/components/PrimaryButton";
import { SecondaryButton } from "@/components/SecondaryButton";
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
        <SecondaryButton
          tone="block"
          onClick={() => void onAction("reject")}
          disabled={busy !== null}
        >
          {busy === "reject" ? "Rejecting" : "Reject"}
        </SecondaryButton>
      </div>
      {error ? <p className="text-sm text-block">{error}</p> : null}
    </div>
  );
}
