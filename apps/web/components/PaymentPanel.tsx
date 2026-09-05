"use client";

import { useEffect, useMemo, useState } from "react";

import { PrimaryButton } from "@/components/PrimaryButton";
import { SecondaryButton } from "@/components/SecondaryButton";
import {
  ApiError,
  confirmCheckout,
  createPayment,
  getPayment,
  getPaymentConfig,
  type GrantView,
  type PaymentConfig,
  type PaymentRecord,
} from "@/lib/api";
import { openRazorpayCheckout } from "@/lib/razorpay";

function rupees(amount: number): string {
  return `₹${amount.toLocaleString("en-IN")}`;
}

type PaymentPanelProps = {
  grant: GrantView | null | undefined;
  payment: PaymentRecord | null | undefined;
};

export function PaymentPanel({ grant, payment: initial }: PaymentPanelProps) {
  const idempotencyKey = useMemo(() => crypto.randomUUID(), []);
  const [payment, setPayment] = useState<PaymentRecord | null>(initial ?? null);
  const [config, setConfig] = useState<PaymentConfig | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  const token = grant?.token ?? null;
  const status = payment?.status ?? null;
  const checkout = payment?.checkout ?? null;
  const provider = payment?.provider ?? config?.provider ?? "simulated";

  useEffect(() => {
    let cancelled = false;
    getPaymentConfig()
      .then((value) => {
        if (!cancelled) {
          setConfig(value);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setConfig({ provider: "simulated", razorpay_key_id: null });
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function openCheckout(record: PaymentRecord) {
    const session = record.checkout;
    if (!session) {
      setPayment(record);
      return;
    }
    try {
      await openRazorpayCheckout({
        key: session.key_id,
        amount: session.amount_paise,
        currency: session.currency,
        order_id: session.order_id,
        name: session.name ?? "IntentGuard",
        description: "Authorized purchase",
        theme: { color: "#3F8F7A" },
        handler: (response) => {
          void confirmCheckout(record.id, response)
            .then(setPayment)
            .catch((caught) => {
              setError(caught instanceof ApiError ? caught.message : "Checkout confirmation failed.");
            });
        },
      });
      setPayment(record);
    } catch (caught) {
      setPayment(record);
      setError(caught instanceof Error ? caught.message : "Razorpay checkout failed to load.");
    }
  }

  async function charge(forceTimeout: boolean) {
    if (!token || !grant) {
      setError("Payment requires a valid unused authorization grant.");
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const result = await createPayment({
        grant_token: token,
        amount: grant.amount,
        currency: grant.currency,
        idempotency_key: idempotencyKey,
        force_timeout: forceTimeout,
      });
      if (result.checkout && !forceTimeout) {
        await openCheckout(result);
      } else {
        setPayment(result);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Payment could not be created.");
    } finally {
      setBusy(false);
    }
  }

  async function onPay() {
    await charge(false);
  }

  async function onTimeout() {
    await charge(true);
  }

  async function onReconcile() {
    if (!payment) {
      return;
    }
    setBusy(true);
    setError(null);
    try {
      const latest = await getPayment(payment.id);
      if (latest.checkout && latest.status !== "succeeded") {
        await openCheckout(latest);
      } else {
        setPayment(latest);
      }
    } catch (caught) {
      setError(caught instanceof ApiError ? caught.message : "Payment status could not be reconciled.");
    } finally {
      setBusy(false);
    }
  }

  if (!grant) {
    return null;
  }

  if (status === "succeeded") {
    const copy =
      provider === "razorpay"
        ? `Razorpay Test Mode captured ${rupees(payment?.amount ?? grant.amount)}. Grant is spent.`
        : `Simulated ledger charged ${rupees(payment?.amount ?? grant.amount)}. Grant is spent.`;
    return (
      <div className="flex flex-col gap-2 border-t border-hairline pt-6">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">Payment</p>
        <p className="font-mono text-sm tracking-[0.04em] text-approve">SUCCEEDED</p>
        <p className="max-w-[65ch] text-sm leading-relaxed text-muted">{copy}</p>
        {payment?.provider_ref ? (
          <p className="font-mono text-[11px] tracking-[0.04em] text-faint">{payment.provider_ref}</p>
        ) : null}
      </div>
    );
  }

  if (status === "unknown") {
    return (
      <div className="flex flex-col gap-4 border-t border-hairline pt-6">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">Payment</p>
        <p className="font-mono text-sm tracking-[0.04em] text-pause">UNKNOWN</p>
        <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
          Payment status is unknown. Reconcile before any retry. IntentGuard will not create a second
          charge for this grant.
        </p>
        <SecondaryButton onClick={onReconcile} disabled={busy}>
          {busy ? "Reconciling" : "Reconcile status"}
        </SecondaryButton>
        {error ? <p className="text-sm text-block">{error}</p> : null}
      </div>
    );
  }

  if ((status === "pending" || status === "created") && checkout) {
    return (
      <div className="flex flex-col gap-4 border-t border-hairline pt-6">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">Payment</p>
        <p className="font-mono text-sm tracking-[0.04em] text-pause">TEST CHECKOUT</p>
        <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
          Razorpay Test Mode. Complete checkout to capture. The agent cannot open this.
        </p>
        <PrimaryButton onClick={() => void onReconcile()} disabled={busy}>
          {busy ? "Opening checkout" : "Complete test checkout"}
        </PrimaryButton>
        {error ? <p className="text-sm text-block">{error}</p> : null}
      </div>
    );
  }

  if (status === "pending" || status === "created") {
    return (
      <div className="flex flex-col gap-4 border-t border-hairline pt-6">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">Payment</p>
        <p className="font-mono text-sm tracking-[0.04em] text-pause">PENDING</p>
        <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
          The order is pending. Reconcile status. IntentGuard will not mint a second grant.
        </p>
        <SecondaryButton onClick={onReconcile} disabled={busy}>
          {busy ? "Reconciling" : "Reconcile status"}
        </SecondaryButton>
        {error ? <p className="text-sm text-block">{error}</p> : null}
      </div>
    );
  }

  if (status === "failed") {
    return (
      <div className="flex flex-col gap-2 border-t border-hairline pt-6">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">Payment</p>
        <p className="font-mono text-sm tracking-[0.04em] text-block">FAILED</p>
        <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
          The provider reported failure. This grant is spent. Payment was not completed.
        </p>
      </div>
    );
  }

  if (grant.used || !token) {
    return (
      <div className="flex flex-col gap-2 border-t border-hairline pt-6">
        <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">Payment</p>
        <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
          The grant is no longer available. Reload the decision to reconcile any in-flight payment.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-4 border-t border-hairline pt-6">
      <p className="text-[10px] font-medium uppercase tracking-[0.18em] text-muted">Payment</p>
      <p className="max-w-[65ch] text-sm leading-relaxed text-muted">
        {provider === "razorpay"
          ? `A one-time grant is locked to this intent and ${rupees(grant.amount)}. Razorpay Test Mode opens only after this grant.`
          : `A one-time grant is locked to this intent, proposal, and ${rupees(grant.amount)}. The agent cannot charge. Initiating payment consumes the grant.`}
      </p>
      <PrimaryButton onClick={onPay} disabled={busy}>
        {busy
          ? provider === "razorpay"
            ? "Creating test order"
            : "Charging ledger"
          : provider === "razorpay"
            ? "Create test order"
            : "Initiate payment"}
      </PrimaryButton>
      <SecondaryButton onClick={() => void onTimeout()} disabled={busy}>
        {busy ? "Simulating timeout" : "Simulate timeout"}
      </SecondaryButton>
      {error ? <p className="text-sm text-block">{error}</p> : null}
    </div>
  );
}
