"use client";

import type { ReactNode } from "react";
import { useState } from "react";

type FailureInjectProps = {
  children: ReactNode;
};

export function FailureInject({ children }: FailureInjectProps) {
  const [open, setOpen] = useState(false);

  return (
    <div className="flex flex-col gap-4">
      <button
        type="button"
        onClick={() => setOpen((value) => !value)}
        className="min-h-11 w-fit cursor-pointer text-sm text-muted underline decoration-hairline underline-offset-4 transition-colors duration-200 ease-intent hover:text-ink"
      >
        {open ? "Hide failure injection" : "Failure injection"}
      </button>
      {open ? (
        <div className="flex flex-col gap-3 border-t border-hairline pt-4">{children}</div>
      ) : null}
    </div>
  );
}

export function InjectChip({
  active,
  onClick,
  children,
}: {
  active?: boolean;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`inline-flex min-h-11 cursor-pointer items-center rounded-full border px-4 text-sm transition-[color,background-color,transform] duration-200 ease-intent active:scale-[0.98] ${
        active
          ? "border-teal/50 bg-teal/15 text-teal"
          : "border-hairline text-muted hover:text-ink"
      }`}
    >
      {children}
    </button>
  );
}
