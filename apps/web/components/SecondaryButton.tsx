"use client";

import type { ButtonHTMLAttributes, ReactNode } from "react";

type SecondaryButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
  tone?: "ink" | "block";
};

export function SecondaryButton({
  children,
  disabled,
  tone = "ink",
  type = "button",
  className,
  ...props
}: SecondaryButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      className={[
        "inline-flex min-h-11 cursor-pointer items-center rounded-full border border-hairline px-6 py-3 text-sm font-medium transition-[color,background-color,transform] duration-200 ease-intent hover:bg-white/5 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:pointer-events-none disabled:cursor-not-allowed disabled:text-faint disabled:hover:bg-transparent",
        tone === "block" ? "text-block" : "text-ink",
        className ?? "",
      ].join(" ")}
      {...props}
    >
      {children}
    </button>
  );
}
