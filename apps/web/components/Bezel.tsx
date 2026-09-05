import type { ReactNode } from "react";

type BezelProps = {
  children: ReactNode;
  className?: string;
};

export function Bezel({ children, className }: BezelProps) {
  return (
    <div
      className={`rounded-[1.75rem] bg-white/5 p-1.5 ring-1 ring-white/10 ${className ?? ""}`}
    >
      <div className="rounded-[calc(1.75rem-0.375rem)] bg-panel shadow-[inset_0_1px_0_rgba(255,255,255,0.08)]">
        {children}
      </div>
    </div>
  );
}
