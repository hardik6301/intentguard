"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const STEPS: { id: string; label: string; suffix: string | null }[] = [
  { id: "create", label: "Create", suffix: null },
  { id: "run", label: "Run", suffix: "/run" },
  { id: "decision", label: "Decision", suffix: "/decision" },
  { id: "audit", label: "Audit", suffix: "/audit" },
];

function intentIdFromPath(pathname: string): string | null {
  const match = pathname.match(/^\/intents\/([^/]+)/);
  return match?.[1] ?? null;
}

function shortIntentId(intentId: string): string {
  if (intentId.length <= 14) {
    return intentId;
  }
  return `${intentId.slice(0, 8)}…${intentId.slice(-4)}`;
}

function stepHref(intentId: string | null, suffix: string | null): string | undefined {
  if (suffix === null) {
    return "/";
  }
  if (!intentId) {
    return undefined;
  }
  return `/intents/${intentId}${suffix}`;
}

function isActive(pathname: string, suffix: string | null, intentId: string | null): boolean {
  const href = stepHref(intentId, suffix);
  return href !== undefined && pathname === href;
}

export function SessionNav() {
  const pathname = usePathname();
  const intentId = intentIdFromPath(pathname);

  return (
    <header className="sticky top-0 z-20 pt-4">
      <nav className="mx-auto flex w-[min(1120px,calc(100%-2rem))] items-center justify-between rounded-full border border-white/10 bg-panel/80 px-4 py-2 shadow-[inset_0_1px_0_rgba(255,255,255,0.1)] backdrop-blur-xl md:px-5">
        <Link
          href="/"
          className="flex min-h-11 cursor-pointer items-center gap-3 rounded-full focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas"
        >
          <span className="text-[11px] font-medium uppercase tracking-[0.18em] text-ink">
            IntentGuard
          </span>
          {intentId ? (
            <span
              className="hidden font-mono text-[11px] tracking-[0.04em] text-faint md:inline"
              title={intentId}
            >
              {shortIntentId(intentId)}
            </span>
          ) : null}
        </Link>
        <ol className="flex items-center gap-1 md:gap-2">
          {STEPS.map((step) => {
            const href = stepHref(intentId, step.suffix);
            const active = isActive(pathname, step.suffix, intentId);
            const className = [
              "flex min-h-11 items-center rounded-full px-3 text-[11px] font-medium uppercase tracking-[0.16em] transition-colors duration-200 ease-intent focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
              active ? "bg-teal/20 text-teal" : "text-faint",
              href && !active ? "cursor-pointer hover:text-muted" : "",
              !href ? "cursor-not-allowed text-faint/50" : "",
            ].join(" ");

            if (!href) {
              return (
                <li key={step.id}>
                  <span className={className}>{step.label}</span>
                </li>
              );
            }

            return (
              <li key={step.id}>
                <Link href={href} className={className}>
                  {step.label}
                </Link>
              </li>
            );
          })}
          <li>
            <Link
              href="/eval"
              className={[
                "flex min-h-11 cursor-pointer items-center rounded-full px-3 text-[11px] font-medium uppercase tracking-[0.16em] transition-colors duration-200 ease-intent focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas",
                pathname === "/eval" ? "bg-teal/20 text-teal" : "text-faint hover:text-muted",
              ].join(" ")}
            >
              Eval
            </Link>
          </li>
        </ol>
      </nav>
    </header>
  );
}
