"use client";

import { ArrowRight } from "@phosphor-icons/react";
import type { ButtonHTMLAttributes, ReactNode } from "react";

type PrimaryButtonProps = ButtonHTMLAttributes<HTMLButtonElement> & {
  children: ReactNode;
};

export function PrimaryButton({
  children,
  disabled,
  type = "button",
  ...props
}: PrimaryButtonProps) {
  return (
    <button
      type={type}
      disabled={disabled}
      className="inline-flex min-h-11 items-center gap-3 rounded-full bg-teal px-6 py-3 text-sm font-medium text-ink transition-transform duration-500 ease-intent hover:brightness-110 active:scale-[0.98] disabled:pointer-events-none disabled:opacity-40"
      {...props}
    >
      {children}
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-black/20">
        <ArrowRight size={16} weight="regular" />
      </span>
    </button>
  );
}
