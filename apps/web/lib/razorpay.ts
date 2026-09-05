"use client";

declare global {
  interface Window {
    Razorpay?: new (options: RazorpayOptions) => { open: () => void };
  }
}

type RazorpayOptions = {
  key: string;
  amount: number;
  currency: string;
  order_id: string;
  name: string;
  description: string;
  theme: { color: string };
  handler: (response: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  }) => void;
};

export async function loadRazorpayCheckout(): Promise<void> {
  if (typeof window === "undefined") {
    throw new Error("Razorpay checkout is browser-only.");
  }
  if (window.Razorpay) {
    return;
  }
  await new Promise<void>((resolve, reject) => {
    const existing = document.querySelector("script[data-intentguard-razorpay]");
    if (existing) {
      existing.addEventListener("load", () => resolve());
      existing.addEventListener("error", () => reject(new Error("Razorpay checkout failed to load.")));
      return;
    }
    const script = document.createElement("script");
    script.src = "https://checkout.razorpay.com/v1/checkout.js";
    script.async = true;
    script.dataset.intentguardRazorpay = "true";
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("Razorpay checkout failed to load."));
    document.body.appendChild(script);
  });
}

export async function openRazorpayCheckout(options: RazorpayOptions): Promise<void> {
  await loadRazorpayCheckout();
  if (!window.Razorpay) {
    throw new Error("Razorpay checkout is unavailable.");
  }
  const checkout = new window.Razorpay(options);
  checkout.open();
}
