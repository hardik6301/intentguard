"use client";

import { Check, Minus, X } from "@phosphor-icons/react";
import { useEffect, useState } from "react";

import { Bezel } from "@/components/Bezel";
import { Eyebrow } from "@/components/Eyebrow";
import { PauseResolve } from "@/components/PauseResolve";
import { PaymentPanel } from "@/components/PaymentPanel";
import { Skeleton } from "@/components/Skeleton";
import { getLatestDecision, getRuntime, type ProposalEvaluation, type RuntimeInfo } from "@/lib/api";

function rupees(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

const VERDICT_LABEL: Record<string, string> = {
  APPROVE: "APPROVED",
  PAUSE: "PAUSED",
  BLOCK: "BLOCKED",
};

const VERDICT_COLOR: Record<string, string> = {
  APPROVE: "text-approve",
  PAUSE: "text-pause",
  BLOCK: "text-block",
};

type DecisionHeroProps = {
  intentId: string;
};

export function DecisionHero({ intentId }: DecisionHeroProps) {
  const [record, setRecord] = useState<ProposalEvaluation | null | undefined>(undefined);
  const [error, setError] = useState<string | null>(null);
  const [runtime, setRuntime] = useState<RuntimeInfo | null>(null);

  useEffect(() => {
    let cancelled = false;
    getLatestDecision(intentId)
      .then((value) => {
        if (!cancelled) {
          setRecord(value);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Decision could not be loaded.");
        }
      });
    getRuntime()
      .then((value) => {
        if (!cancelled) {
          setRuntime(value);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setRuntime(null);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [intentId]);

  if (error) {
    return <p className="text-sm text-block">{error}</p>;
  }

  if (record === undefined) {
    return (
      <main className="grid grid-cols-1 gap-10 md:grid-cols-12">
        <section className="flex flex-col gap-4 md:col-span-7">
          <Skeleton className="h-6 w-40" />
          <Skeleton className="h-16 w-64" />
          <Skeleton className="h-6 w-48" />
        </section>
        <Skeleton className="h-72 rounded-[1.75rem] md:col-span-5" />
      </main>
    );
  }

  if (record === null) {
    return (
      <main className="grid grid-cols-1 gap-10 md:grid-cols-12">
        <section className="flex flex-col gap-4 md:col-span-7">
          <Eyebrow>Proposed transaction</Eyebrow>
          <p className="font-mono text-[clamp(2.5rem,6vw,4.5rem)] leading-none tracking-tight text-faint">
            —
          </p>
          <p className="max-w-[65ch] text-base leading-[1.55] text-muted">
            No proposal yet. Run the agent to send a transaction to IntentGuard.
          </p>
        </section>
        <Bezel className="md:col-span-5">
          <div className="flex flex-col divide-y divide-hairline">
            {["Hard constraints", "Semantic match", "Risk"].map((label) => (
              <div key={label} className="flex items-center justify-between px-6 py-5 md:px-8">
                <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted">
                  {label}
                </span>
                <span className="font-mono text-sm tracking-[0.04em] text-faint">—</span>
              </div>
            ))}
            <div className="px-6 py-8 md:px-8">
              <p className="text-[clamp(1.75rem,3vw,2.5rem)] font-medium leading-none tracking-tight text-faint">
                PENDING
              </p>
            </div>
          </div>
        </Bezel>
      </main>
    );
  }

  const engineVerdict = record.decision.verdict;
  const stamp = stampVerdict(record);
  const pendingPause = engineVerdict === "PAUSE" && (record.resolution ?? "pending") === "pending";
  const showCompare = stamp === "BLOCK" || pendingPause;
  const score = record.semantic.semantic_match;
  const scoreLabel =
    record.semantic.error || score === null ? "unavailable" : `${Math.round(score * 100)}%`;

  return (
    <main className="grid grid-cols-1 gap-10 md:grid-cols-12">
      <section className="flex flex-col gap-6 md:col-span-7">
        <Eyebrow>Proposed transaction</Eyebrow>
        <p className="font-mono text-[clamp(2.5rem,6vw,4.5rem)] leading-none tracking-tight text-ink">
          {rupees(record.proposal.amount)}
        </p>
        <p className="text-base leading-relaxed text-ink">{record.proposal.product.name}</p>
        {showCompare ? <CompareColumns record={record} /> : null}
        {pendingPause ? (
          <div className="flex flex-col gap-4">
            <p className="max-w-[65ch] text-base leading-relaxed text-muted">
              Does this still match what you authorized?
            </p>
            {record.decision_id ? (
              <PauseResolve decisionId={record.decision_id} onResolved={setRecord} />
            ) : (
              <p className="text-sm text-block">This pause has no decision id.</p>
            )}
          </div>
        ) : null}
        {stamp === "BLOCK" ? (
          <p className="max-w-[65ch] text-base leading-relaxed text-block">
            Payment was not initiated.
          </p>
        ) : null}
        {stamp === "APPROVE" ? (
          <p className="max-w-[65ch] text-base leading-relaxed text-muted">
            Authorization holds. A single-use grant was minted. Payment stays grant-gated.
          </p>
        ) : null}
        <ul className="flex flex-col gap-2">
          {record.decision.reasons.map((reason) => (
            <li key={reason} className="max-w-[65ch] text-sm leading-relaxed text-muted">
              {reason}
            </li>
          ))}
        </ul>
        {stamp === "APPROVE" ? (
          <PaymentPanel grant={record.grant} payment={record.payment} />
        ) : null}
      </section>
      <Bezel className="md:col-span-5">
        <div className="flex flex-col divide-y divide-hairline">
          <CheckRow
            label="Hard constraints"
            value={record.hard.passed ? "Pass" : "Fail"}
            tone={record.hard.passed ? "approve" : "block"}
            glyph={record.hard.passed ? "check" : "x"}
          />
          <CheckRow
            label="Semantic match"
            value={scoreLabel}
            tone={semanticTone(record)}
            glyph={semanticGlyph(record)}
            detail={record.semantic.reason || undefined}
          />
          <CheckRow
            label="Risk"
            value={record.risk.risk_level.toUpperCase()}
            tone={record.risk.risk_level === "low" ? "approve" : record.risk.risk_level === "medium" ? "pause" : "block"}
            glyph={record.risk.risk_level === "low" ? "check" : "x"}
          />
          <div className="px-6 py-8 md:px-8">
            <p
              className={`inline-block rounded-sm px-2 py-1 text-[clamp(1.75rem,3vw,2.5rem)] font-medium leading-none tracking-[-0.04em] ring-1 ring-current/25 ${VERDICT_COLOR[stamp]}`}
            >
              {VERDICT_LABEL[stamp]}
            </p>
            <p className="mt-3 font-mono text-[11px] tracking-[0.04em] text-faint">
              {record.decision.policy_version}
              {runtime
                ? ` · assessment ${runtime.semantic === "gemini" ? "Gemini" : "local heuristic"}`
                : ""}
            </p>
          </div>
        </div>
      </Bezel>
    </main>
  );
}

function stampVerdict(record: ProposalEvaluation): "APPROVE" | "PAUSE" | "BLOCK" {
  if (record.resolution === "confirmed") {
    return "APPROVE";
  }
  if (record.resolution === "rejected") {
    return "BLOCK";
  }
  return record.decision.verdict;
}

function CompareColumns({ record }: { record: ProposalEvaluation }) {
  return (
    <div className="grid grid-cols-1 gap-6 border-t border-hairline pt-6 md:grid-cols-2">
      <div className="flex flex-col gap-2">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
          Original intent
        </p>
        <p className="max-w-[65ch] text-sm leading-relaxed text-ink">{record.goal}</p>
        <p className="font-mono text-sm tracking-[0.04em] text-faint">Max {rupees(record.max_amount)}</p>
      </div>
      <div className="flex flex-col gap-2">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
          Proposed action
        </p>
        <p className="max-w-[65ch] text-sm leading-relaxed text-ink">
          {record.proposal.product.name} · {record.proposal.merchant}
        </p>
        <p className="font-mono text-sm tracking-[0.04em] text-faint">{rupees(record.proposal.amount)}</p>
      </div>
    </div>
  );
}

function semanticTone(record: ProposalEvaluation): "approve" | "pause" | "block" {
  if (record.semantic.error || record.semantic.semantic_match === null) {
    return "pause";
  }
  if (record.semantic.semantic_match < 0.6) {
    return "block";
  }
  if (record.semantic.semantic_match < 0.85) {
    return "pause";
  }
  return "approve";
}

function semanticGlyph(record: ProposalEvaluation): "check" | "x" | "minus" {
  const tone = semanticTone(record);
  if (tone === "approve") {
    return "check";
  }
  if (tone === "block") {
    return "x";
  }
  return "minus";
}

function CheckRow({
  label,
  value,
  tone,
  glyph,
  detail,
}: {
  label: string;
  value: string;
  tone: "approve" | "pause" | "block";
  glyph: "check" | "x" | "minus";
  detail?: string;
}) {
  const color =
    tone === "approve" ? "text-approve" : tone === "pause" ? "text-pause" : "text-block";
  return (
    <div className="flex flex-col gap-2 px-6 py-5 md:px-8">
      <div className="flex items-center justify-between gap-4">
        <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted">{label}</span>
        <span className={`inline-flex items-center gap-2 font-mono text-sm tracking-[0.04em] ${color}`}>
          {glyph === "check" ? <Check size={14} weight="bold" /> : null}
          {glyph === "x" ? <X size={14} weight="bold" /> : null}
          {glyph === "minus" ? <Minus size={14} weight="bold" /> : null}
          {value}
        </span>
      </div>
      {detail ? <p className="max-w-[65ch] text-sm leading-relaxed text-muted">{detail}</p> : null}
    </div>
  );
}
