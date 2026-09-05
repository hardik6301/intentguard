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
      className="group inline-flex min-h-11 cursor-pointer items-center gap-3 rounded-full bg-teal px-6 py-3 text-sm font-medium text-ink transition-[transform,filter] duration-200 ease-intent hover:brightness-110 active:scale-[0.98] focus-visible:ring-2 focus-visible:ring-teal focus-visible:ring-offset-2 focus-visible:ring-offset-canvas disabled:pointer-events-none disabled:cursor-not-allowed disabled:bg-raised disabled:text-faint disabled:ring-1 disabled:ring-hairline disabled:brightness-100"
      {...props}
    >
      {children}
      <span className="flex h-8 w-8 items-center justify-center rounded-full bg-black/20 group-disabled:bg-white/5">
        <ArrowRight size={16} weight="regular" />
      </span>
    </button>
  );
}
