"use client";

import { useEffect, useState } from "react";

import { Bezel } from "@/components/Bezel";
import { Eyebrow } from "@/components/Eyebrow";
import { PrimaryButton } from "@/components/PrimaryButton";
import { Skeleton } from "@/components/Skeleton";
import { ApiError, runEvalSuite, type EvalReport } from "@/lib/api";

function rate(value: number): string {
  return value.toFixed(3);
}

function verdictTone(verdict: string): string {
  if (verdict === "APPROVE") {
    return "text-approve";
  }
  if (verdict === "PAUSE") {
    return "text-pause";
  }
  if (verdict === "BLOCK") {
    return "text-block";
  }
  return "text-ink";
}

export function EvalDashboard() {
  const [report, setReport] = useState<EvalReport | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [running, setRunning] = useState(false);

  async function runSuite() {
    setRunning(true);
    setError(null);
    try {
      setReport(await runEvalSuite());
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Eval suite could not run.");
    } finally {
      setRunning(false);
    }
  }

  useEffect(() => {
    void runSuite();
  }, []);

  return (
    <main className="grid grid-cols-1 gap-10 md:grid-cols-12">
      <section className="flex flex-col gap-6 md:col-span-7">
        <div className="flex flex-col gap-3">
          <Eyebrow>Evaluation harness</Eyebrow>
          <h1 className="max-w-[16ch] text-[clamp(1.75rem,3vw,2.75rem)] font-medium leading-none tracking-[-0.04em] text-ink">
            Unsafe Approval Rate
          </h1>
          <p className="max-w-[65ch] text-base leading-[1.55] text-muted">
            Share of labeled BLOCK cases the engine approved. Ceiling is zero. This suite stubs
            semantic scores and measures the decision engine, not model quality.
          </p>
        </div>
        {error ? <p className="text-sm text-block">{error}</p> : null}
        {running && !report ? (
          <Skeleton className="h-20 w-56" />
        ) : report ? (
          <div className="flex flex-col gap-3">
            <p
              className={`font-mono text-[clamp(2.5rem,6vw,4.5rem)] leading-none tracking-tight ${
                report.unsafe_approval_rate === 0 ? "text-ink" : "text-block"
              }`}
            >
              {rate(report.unsafe_approval_rate)}
            </p>
            <p className="font-mono text-sm tracking-[0.04em] text-faint">
              {report.unsafe_approvals}/{report.expected_blocks} expected BLOCK approved
            </p>
          </div>
        ) : null}
        <PrimaryButton onClick={() => void runSuite()} disabled={running}>
          {running ? "Running suite" : "Run deterministic suite"}
        </PrimaryButton>
        {report ? (
          <p className="font-mono text-[11px] tracking-[0.04em] text-faint">
            {report.total} cases · {report.mode} · ceiling 0
          </p>
        ) : null}
      </section>

      <Bezel className="md:col-span-5">
        <div className="flex flex-col divide-y divide-hairline">
          {running && !report ? (
            <div className="flex flex-col gap-4 px-6 py-8 md:px-8">
              <Skeleton className="h-5 w-40" />
              <Skeleton className="h-5 w-48" />
              <Skeleton className="h-5 w-36" />
            </div>
          ) : report ? (
            <>
              <MetricRow label="Accuracy" value={rate(report.accuracy)} />
              <MetricRow label="False approvals" value={String(report.false_approvals)} />
              <MetricRow label="False blocks" value={String(report.false_blocks)} />
              <MetricRow label="Violation precision" value={rate(report.violation_precision)} />
              <MetricRow label="Violation recall" value={rate(report.violation_recall)} />
              <MetricRow
                label="Avg latency"
                value={`${report.average_latency_ms.toFixed(2)} ms`}
              />
            </>
          ) : (
            <p className="px-6 py-8 text-sm leading-relaxed text-muted md:px-8">
              Run the suite to fill engine metrics.
            </p>
          )}
        </div>
      </Bezel>

      <section className="flex flex-col gap-4 md:col-span-12">
        <Eyebrow>Mismatches</Eyebrow>
        {!report && running ? (
          <Skeleton className="h-16 w-full" />
        ) : report && report.mismatches.length === 0 ? (
          <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
            No mismatches. Engine verdicts match the labeled gold set.
          </p>
        ) : report ? (
          <ol className="flex flex-col">
            {report.mismatches.map((item) => (
              <li
                key={item.id}
                className="grid grid-cols-1 gap-2 border-l border-hairline py-4 pl-6 md:grid-cols-[14rem_1fr]"
              >
                <span className="font-mono text-sm tracking-[0.04em] text-faint">{item.id}</span>
                <p className="text-sm leading-relaxed text-block">
                  expected {item.expected} got {item.actual}
                </p>
              </li>
            ))}
          </ol>
        ) : null}
      </section>

      {report ? (
        <section className="flex flex-col gap-4 md:col-span-12">
          <Eyebrow>Labeled cases</Eyebrow>
          <ol className="flex flex-col">
            {report.cases.map((item) => (
              <li
                key={item.id}
                className="grid grid-cols-[7rem_1fr_auto] items-baseline gap-4 border-l border-hairline py-3 pl-6"
              >
                <span className={`font-mono text-sm tracking-[0.04em] ${verdictTone(item.actual)}`}>
                  {item.actual}
                </span>
                <span className="truncate font-mono text-[11px] tracking-[0.04em] text-faint">
                  {item.id}
                </span>
                <span className="font-mono text-[11px] tracking-[0.04em] text-faint">
                  {item.match ? "match" : "miss"}
                </span>
              </li>
            ))}
          </ol>
        </section>
      ) : null}
    </main>
  );
}

function MetricRow({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex items-center justify-between gap-4 px-6 py-5 md:px-8">
      <span className="text-[11px] font-medium uppercase tracking-[0.16em] text-muted">{label}</span>
      <span className="font-mono text-sm tracking-[0.04em] text-ink">{value}</span>
    </div>
  );
}
