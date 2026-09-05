import type { ReactNode } from "react";

type EyebrowProps = {
  children: ReactNode;
};

export function Eyebrow({ children }: EyebrowProps) {
  return (
    <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">
      {children}
    </p>
  );
}
