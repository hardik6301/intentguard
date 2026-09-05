"use client";

import { Check } from "@phosphor-icons/react";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";

import { Bezel } from "@/components/Bezel";
import { Eyebrow } from "@/components/Eyebrow";
import { FailureInject, InjectChip } from "@/components/FailureInject";
import { ManualProposalForm } from "@/components/ManualProposalForm";
import { PrimaryButton } from "@/components/PrimaryButton";
import {
  ApiError,
  getActivity,
  getIntent,
  runAgent,
  type ActivityEvent,
  type AgentRun,
  type IntentRecord,
} from "@/lib/api";

function rupees(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

type AgentRunSessionProps = {
  intentId: string;
};

export function AgentRunSession({ intentId }: AgentRunSessionProps) {
  const router = useRouter();
  const [record, setRecord] = useState<IntentRecord | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);
  const [visibleCount, setVisibleCount] = useState(0);
  const [result, setResult] = useState<AgentRun | null>(null);
  const [events, setEvents] = useState<ActivityEvent[]>([]);
  const [showManual, setShowManual] = useState(false);
  const [inject, setInject] = useState<"poison" | "low_semantic" | null>(null);
  const [forceAgentFail, setForceAgentFail] = useState(false);
  const [agentFailed, setAgentFailed] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getIntent(intentId)
      .then((value) => {
        if (!cancelled) {
          setRecord(value);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Intent not found.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [intentId]);

  useEffect(() => {
    if (!result || agentFailed) {
      return;
    }
    if (visibleCount >= result.steps.length) {
      const timer = window.setTimeout(() => {
        router.push(`/intents/${intentId}/decision`);
      }, 700);
      return () => window.clearTimeout(timer);
    }
    const timer = window.setTimeout(() => {
      setVisibleCount((count) => count + 1);
    }, 80);
    return () => window.clearTimeout(timer);
  }, [result, visibleCount, intentId, router, agentFailed]);

  async function onRun() {
    setError(null);
    setRunning(true);
    setResult(null);
    setVisibleCount(0);
    setAgentFailed(false);
    try {
      const run = await runAgent(intentId, {
        inject: inject ?? undefined,
        force_agent_fail: forceAgentFail,
      });
      setResult(run);
      const activity = await getActivity(intentId);
      setEvents(activity);
    } catch (caught) {
      setAgentFailed(true);
      setError(caught instanceof ApiError ? caught.message : "The agent could not propose a purchase.");
      try {
        setEvents(await getActivity(intentId));
      } catch {
        setEvents([]);
      }
    } finally {
      setRunning(false);
    }
  }

  if (!record && !error) {
    return (
      <div className="grid grid-cols-1 gap-8 md:grid-cols-[2fr_1fr]">
        <div className="flex flex-col gap-4">
          <div className="h-10 w-48 rounded-lg bg-raised" />
          <div className="h-16 w-full max-w-md rounded-lg bg-raised" />
        </div>
        <div className="h-64 rounded-[1.75rem] bg-raised" />
      </div>
    );
  }

  if (error && !record) {
    return <p className="text-sm text-block">{error}</p>;
  }

  const proposal = result?.evaluation?.proposal;
  const steps = result?.steps ?? [];
  const shown = steps.slice(0, visibleCount);

  return (
    <div className="flex flex-col gap-10">
      <div className="grid grid-cols-1 gap-8 md:grid-cols-[2fr_1fr] md:gap-10">
        <section className="flex flex-col gap-6">
          <div className="flex flex-col gap-3">
            <Eyebrow>Live agent execution</Eyebrow>
            <h1 className="max-w-[22ch] text-[clamp(1.75rem,3vw,2.75rem)] font-medium leading-none tracking-[-0.04em] text-ink">
              {record?.contract.goal ?? "Run the agent"}
            </h1>
            <p className="max-w-[65ch] text-base leading-[1.55] text-muted">
              The agent may search the demo catalog and propose a purchase. It cannot pay.
              IntentGuard decides after the proposal.
            </p>
          </div>
          <PrimaryButton onClick={onRun} disabled={running || Boolean(result)}>
            {running ? "Searching catalog" : result ? "Agent finished" : "Run agent"}
          </PrimaryButton>
          {error ? (
            <div className="flex flex-col gap-2">
              <p className="text-sm text-block">{error}</p>
              {agentFailed ? (
                <p className="max-w-[65ch] text-sm leading-relaxed text-block">
                  Payment was not initiated.
                </p>
              ) : null}
            </div>
          ) : null}
          <ol className="relative flex flex-col border-l border-hairline pl-5">
            {shown.map((step, index) => {
              const current = index === shown.length - 1 && visibleCount < steps.length;
              return (
                <li
                  key={`${step.tool}-${index}`}
                  className="relative py-3"
                  style={{ animationDelay: `${index * 80}ms` }}
                >
                  <span
                    className={`absolute -left-[1.45rem] top-5 flex h-3 w-3 items-center justify-center rounded-full ${
                      current ? "bg-teal animate-pulse" : "bg-teal"
                    }`}
                  >
                    {current ? null : <Check size={8} weight="bold" className="text-ink" />}
                  </span>
                  <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-faint">
                    {step.tool.replaceAll("_", " ")}
                  </p>
                  <p className="text-sm leading-relaxed text-ink">{step.detail}</p>
                </li>
              );
            })}
            {agentFailed && events.length > 0 ? (
              events
                .filter((event) => event.event_type.startsWith("agent_"))
                .map((event) => (
                  <li key={event.id} className="relative py-3">
                    <span className="absolute -left-[1.45rem] top-5 h-3 w-3 rounded-full bg-block" />
                    <p className="text-[11px] font-medium uppercase tracking-[0.16em] text-faint">
                      {event.event_type.replaceAll("_", " ")}
                    </p>
                    <p className="text-sm leading-relaxed text-ink">
                      {typeof event.payload.message === "string"
                        ? event.payload.message
                        : typeof event.payload.detail === "string"
                          ? event.payload.detail
                          : event.event_type}
                    </p>
                  </li>
                ))
            ) : null}
            {!result && !running && !agentFailed ? (
              <li className="py-3">
                <p className="text-sm leading-relaxed text-muted">
                  Activity appears here after you run the agent.
                </p>
              </li>
            ) : null}
          </ol>
        </section>
        <Bezel>
          <div className="flex flex-col gap-5 p-6 md:p-8">
            <Eyebrow>Proposed transaction</Eyebrow>
            {proposal ? (
              <>
                <p className="font-mono text-[clamp(2rem,4vw,3rem)] leading-none tracking-tight text-ink">
                  {rupees(proposal.amount)}
                </p>
                <p className="text-base leading-relaxed text-ink">{proposal.product.name}</p>
                <p className="font-mono text-sm tracking-[0.04em] text-faint">{proposal.merchant}</p>
                <p className="font-mono text-[11px] tracking-[0.04em] text-faint">
                  {proposal.product.id}
                </p>
                <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
                  {result?.would_charge
                    ? "A charge would be attempted after approval."
                    : "Would not charge. Payment was not initiated."}
                </p>
              </>
            ) : (
                <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
                {agentFailed
                  ? "The agent did not propose a purchase. Payment was not initiated."
                  : "SKU, amount, and merchant appear when the agent proposes."}
              </p>
            )}
          </div>
        </Bezel>
      </div>
      <FailureInject>
        <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
          Designed failures. The agent still cannot pay. Injection is evaluated against the
          contract, not the product page.
        </p>
        <div className="flex flex-wrap gap-2">
          <InjectChip
            active={inject === "poison"}
            onClick={() => setInject((current) => (current === "poison" ? null : "poison"))}
          >
            Inject poison SKU
          </InjectChip>
          <InjectChip
            active={inject === "low_semantic"}
            onClick={() =>
              setInject((current) => (current === "low_semantic" ? null : "low_semantic"))
            }
          >
            Force low semantic
          </InjectChip>
          <InjectChip
            active={forceAgentFail}
            onClick={() => setForceAgentFail((value) => !value)}
          >
            Force agent failure
          </InjectChip>
        </div>
      </FailureInject>
      <div>
        <button
          type="button"
          onClick={() => setShowManual((open) => !open)}
          className="min-h-11 text-sm text-muted underline decoration-hairline underline-offset-4 hover:text-ink"
        >
          {showManual ? "Hide manual proposal" : "Manual proposal"}
        </button>
        {showManual && record ? (
          <div className="mt-8">
            <ManualProposalForm
              intentId={intentId}
              defaultCategory={record.contract.hard_constraints.category}
              maxAmount={record.contract.hard_constraints.max_amount}
            />
          </div>
        ) : null}
      </div>
      {events.length > 0 ? (
        <p className="font-mono text-[11px] tracking-[0.04em] text-faint">
          {events.length} audit events recorded
        </p>
      ) : null}
    </div>
  );
}
