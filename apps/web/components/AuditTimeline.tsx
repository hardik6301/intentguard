"use client";

import { useEffect, useState } from "react";

import { Eyebrow } from "@/components/Eyebrow";
import { LiveClock } from "@/components/LiveClock";
import { Skeleton } from "@/components/Skeleton";
import { getAudit, type AuditEvent } from "@/lib/api";

function clock(ts: string | null): string {
  if (!ts) {
    return "--:--:--";
  }
  const date = new Date(ts);
  if (Number.isNaN(date.getTime())) {
    return ts.slice(11, 19) || "--:--:--";
  }
  return date.toLocaleTimeString("en-GB", { hour12: false });
}

function summary(event: AuditEvent): string {
  const payload = event.payload;
  if (event.event_type === "decision_made" && typeof payload.verdict === "string") {
    return String(payload.verdict);
  }
  if (event.event_type === "hard_constraints_checked") {
    return payload.passed === true ? "Pass" : "Fail";
  }
  if (event.event_type === "semantic_assessed" && typeof payload.semantic_match === "number") {
    return `${Math.round(payload.semantic_match * 100)}%`;
  }
  if (event.event_type === "risk_assessed" && typeof payload.risk_level === "string") {
    return String(payload.risk_level).toUpperCase();
  }
  if (event.event_type === "agent_step" && typeof payload.detail === "string") {
    return payload.detail;
  }
  if (typeof payload.amount === "number") {
    return `₹${payload.amount.toLocaleString("en-IN")}`;
  }
  if (typeof payload.goal === "string") {
    return payload.goal;
  }
  return "";
}

function titleColor(tone: string): string {
  if (tone === "block") {
    return "text-block";
  }
  if (tone === "approve") {
    return "text-approve";
  }
  if (tone === "pause") {
    return "text-pause";
  }
  return "text-ink";
}

type AuditTimelineProps = {
  intentId: string;
};

export function AuditTimeline({ intentId }: AuditTimelineProps) {
  const [events, setEvents] = useState<AuditEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getAudit(intentId)
      .then((value) => {
        if (!cancelled) {
          setEvents(value);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setError("Audit trail could not be loaded.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, [intentId]);

  if (error) {
    return <p className="text-sm text-block">{error}</p>;
  }

  if (events === null) {
    return (
      <ol className="flex flex-col">
        {[0, 1, 2, 3].map((index) => (
          <li key={index} className="grid grid-cols-[7rem_1fr] gap-6 border-l border-hairline py-5 pl-6">
            <Skeleton className="h-4 w-16" />
            <Skeleton className="h-4 w-48" />
          </li>
        ))}
      </ol>
    );
  }

  if (events.length === 0) {
    return (
      <ol className="flex flex-col">
        <li className="grid grid-cols-[7rem_1fr] gap-6 border-l border-hairline py-5 pl-6">
          <span className="font-mono text-sm tracking-[0.04em] text-faint">--:--:--</span>
          <div className="flex flex-col gap-1">
            <p className="text-sm leading-relaxed text-ink">Waiting for the first event</p>
            <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
              Compile an intent on Create. The trail starts when the contract is hashed.
            </p>
          </div>
        </li>
      </ol>
    );
  }

  return (
    <ol className="flex flex-col">
      {events.map((event, index) => (
        <li
          key={event.id}
          className="animate-fade-up grid grid-cols-[7rem_1fr] gap-6 border-l border-hairline py-5 pl-6"
          style={{ animationDelay: `${index * 70}ms` }}
        >
          <span className="font-mono text-sm tracking-[0.04em] text-faint">{clock(event.ts)}</span>
          <div className="flex flex-col gap-1">
            <p className={`text-sm leading-relaxed ${titleColor(event.tone)}`}>{event.title}</p>
            {summary(event) ? (
              <p className="font-mono text-[11px] tracking-[0.04em] text-faint">{summary(event)}</p>
            ) : null}
          </div>
        </li>
      ))}
    </ol>
  );
}

export function AuditPageBody({ intentId }: { intentId: string }) {
  return (
    <main className="flex flex-col gap-8">
      <div className="flex flex-col gap-3">
        <Eyebrow>Audit trail</Eyebrow>
        <h1 className="text-[clamp(1.75rem,3vw,2.75rem)] font-medium leading-none tracking-[-0.04em]">
          Authorization log
        </h1>
        <p className="max-w-[65ch] text-base leading-[1.55] text-muted">
          Oldest event at the top. Amounts, scores, and timestamps stay in mono.
        </p>
        <div className="flex flex-wrap items-center gap-4">
          <p className="font-mono text-sm tracking-[0.04em] text-faint">{intentId}</p>
          <LiveClock />
        </div>
      </div>
      <AuditTimeline intentId={intentId} />
    </main>
  );
}
