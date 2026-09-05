import { z } from "zod";

import type { IntentContract } from "@/lib/schemas";
import {
  decisionSchema,
  intentContractSchema,
  proposedActionSchema,
  semanticAssessmentSchema,
} from "@/lib/schemas";

const API_URL = process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000";

export function apiUrl(path: string): string {
  return `${API_URL}${path}`;
}

const compileResponseSchema = z.object({
  intent_id: z.string().uuid(),
  contract_hash: z.string().min(16),
  contract: intentContractSchema,
});

const intentRecordSchema = z.object({
  intent_id: z.string().uuid(),
  contract_hash: z.string().min(16),
  status: z.string(),
  contract: intentContractSchema,
});

export type CompileResponse = z.infer<typeof compileResponseSchema>;
export type IntentRecord = z.infer<typeof intentRecordSchema>;

export class ApiError extends Error {
  status: number;
  details: string[];

  constructor(message: string, status: number, details: string[] = []) {
    super(message);
    this.status = status;
    this.details = details;
  }
}

async function readError(response: Response): Promise<ApiError> {
  const body: unknown = await response.json().catch(() => null);
  if (body && typeof body === "object" && "detail" in body) {
    const detail = (body as { detail: unknown }).detail;
    if (typeof detail === "string") {
      return new ApiError(detail, response.status);
    }
    if (detail && typeof detail === "object" && "message" in detail) {
      const payload = detail as { message: string; details?: string[] };
      return new ApiError(payload.message, response.status, payload.details ?? []);
    }
  }
  return new ApiError("IntentGuard request failed", response.status);
}

export async function compileIntent(
  rawRequest: string,
  options?: { force_invalid_json?: boolean },
): Promise<CompileResponse> {
  const response = await fetch(apiUrl("/v1/intents/compile"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      raw_request: rawRequest,
      force_invalid_json: options?.force_invalid_json ?? false,
    }),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return compileResponseSchema.parse(await response.json());
}

export async function confirmIntent(
  intentId: string,
  contract?: IntentContract,
): Promise<IntentRecord> {
  const response = await fetch(apiUrl("/v1/intents/"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ intent_id: intentId, contract }),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return intentRecordSchema.parse(await response.json());
}

export async function getIntent(intentId: string): Promise<IntentRecord> {
  const response = await fetch(apiUrl(`/v1/intents/${intentId}`), { cache: "no-store" });
  if (!response.ok) {
    throw await readError(response);
  }
  return intentRecordSchema.parse(await response.json());
}

const hardResultSchema = z.object({
  passed: z.boolean(),
  failures: z.array(
    z.object({
      code: z.string(),
      message: z.string(),
    }),
  ),
});

const riskAssessmentSchema = z.object({
  risk_level: z.enum(["low", "medium", "high"]).default("low"),
  injection_high: z.boolean().default(false),
  flags: z.array(z.string()).default([]),
});

const grantSchema = z.object({
  id: z.string().uuid(),
  intent_id: z.string().uuid(),
  proposal_id: z.string().uuid(),
  amount: z.number(),
  currency: z.string(),
  expires_at: z.string(),
  used: z.boolean(),
  token: z.string().nullable().optional(),
});

const paymentSchema = z.object({
  id: z.string().uuid(),
  grant_id: z.string().uuid(),
  intent_id: z.string().uuid().nullable().optional(),
  provider: z.string(),
  provider_ref: z.string().nullable().optional(),
  idempotency_key: z.string(),
  status: z.string(),
  amount: z.number(),
  currency: z.string().default("INR"),
  checkout: z
    .object({
      key_id: z.string(),
      order_id: z.string(),
      amount_paise: z.number(),
      currency: z.string(),
      name: z.string().optional(),
    })
    .nullable()
    .optional(),
});

export type GrantView = z.infer<typeof grantSchema>;
export type PaymentRecord = z.infer<typeof paymentSchema>;

const proposalEvaluationSchema = z.object({
  proposal_id: z.string().uuid(),
  intent_id: z.string().uuid(),
  fingerprint: z.string(),
  hard: hardResultSchema,
  semantic: semanticAssessmentSchema,
  risk: riskAssessmentSchema,
  decision: decisionSchema,
  proposal: proposedActionSchema,
  goal: z.string(),
  raw_request: z.string(),
  max_amount: z.number(),
  grant: grantSchema.nullable().optional(),
  payment: paymentSchema.nullable().optional(),
  decision_id: z.string().uuid().nullable().optional(),
  resolution: z.enum(["pending", "confirmed", "rejected"]).nullable().optional(),
});

export type ProposalEvaluation = z.infer<typeof proposalEvaluationSchema>;

export async function submitProposal(
  intentId: string,
  proposal: {
    amount: number;
    merchant: string;
    product: { id: string; name: string; category?: string | null };
    line_items?: { sku: string; name: string; amount: number; quantity?: number }[];
  },
): Promise<ProposalEvaluation> {
  const response = await fetch(apiUrl(`/v1/intents/${intentId}/proposals`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      action: "purchase",
      currency: "INR",
      ...proposal,
    }),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return proposalEvaluationSchema.parse(await response.json());
}

export async function getLatestDecision(intentId: string): Promise<ProposalEvaluation | null> {
  const response = await fetch(apiUrl(`/v1/intents/${intentId}/decision`), { cache: "no-store" });
  if (response.status === 404) {
    return null;
  }
  if (!response.ok) {
    throw await readError(response);
  }
  return proposalEvaluationSchema.parse(await response.json());
}

const agentStepSchema = z.object({
  tool: z.string(),
  detail: z.string(),
});

const agentRunSchema = z.object({
  intent_id: z.string().uuid(),
  steps: z.array(agentStepSchema),
  would_charge: z.boolean(),
  evaluation: proposalEvaluationSchema.nullable(),
});

export type AgentRun = z.infer<typeof agentRunSchema>;

export async function runAgent(
  intentId: string,
  options?: { inject?: "poison" | "low_semantic"; force_agent_fail?: boolean },
): Promise<AgentRun> {
  const response = await fetch(apiUrl(`/v1/intents/${intentId}/run`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      inject: options?.inject ?? null,
      force_agent_fail: options?.force_agent_fail ?? false,
    }),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return agentRunSchema.parse(await response.json());
}

const activityEventSchema = z.object({
  id: z.number(),
  ts: z.string().nullable(),
  actor: z.string(),
  event_type: z.string(),
  payload: z.record(z.string(), z.unknown()),
});

export type ActivityEvent = z.infer<typeof activityEventSchema>;

export async function getActivity(intentId: string): Promise<ActivityEvent[]> {
  const response = await fetch(apiUrl(`/v1/intents/${intentId}/activity`), { cache: "no-store" });
  if (!response.ok) {
    throw await readError(response);
  }
  return z.array(activityEventSchema).parse(await response.json());
}

export async function createPayment(input: {
  grant_token: string;
  amount: number;
  currency?: string;
  idempotency_key: string;
  force_timeout?: boolean;
}): Promise<PaymentRecord> {
  const response = await fetch(apiUrl("/v1/payments"), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      grant_token: input.grant_token,
      amount: input.amount,
      currency: input.currency ?? "INR",
      idempotency_key: input.idempotency_key,
      force_timeout: input.force_timeout ?? false,
    }),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return paymentSchema.parse(await response.json());
}

export async function getPayment(paymentId: string): Promise<PaymentRecord> {
  const response = await fetch(apiUrl(`/v1/payments/${paymentId}`), { cache: "no-store" });
  if (!response.ok) {
    throw await readError(response);
  }
  return paymentSchema.parse(await response.json());
}

const paymentConfigSchema = z.object({
  provider: z.string(),
  razorpay_key_id: z.string().nullable().optional(),
});

export type PaymentConfig = z.infer<typeof paymentConfigSchema>;

export async function getPaymentConfig(): Promise<PaymentConfig> {
  const response = await fetch(apiUrl("/v1/payments/config"), { cache: "no-store" });
  if (!response.ok) {
    throw await readError(response);
  }
  return paymentConfigSchema.parse(await response.json());
}

export async function confirmCheckout(
  paymentId: string,
  payload: {
    razorpay_order_id: string;
    razorpay_payment_id: string;
    razorpay_signature: string;
  },
): Promise<PaymentRecord> {
  const response = await fetch(apiUrl(`/v1/payments/${paymentId}/confirm`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return paymentSchema.parse(await response.json());
}

export async function resolvePause(
  decisionId: string,
  action: "confirm" | "reject",
): Promise<ProposalEvaluation> {
  const response = await fetch(apiUrl(`/v1/decisions/${decisionId}/confirm`), {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ action }),
  });
  if (!response.ok) {
    throw await readError(response);
  }
  return proposalEvaluationSchema.parse(await response.json());
}

const auditEventSchema = z.object({
  id: z.number(),
  ts: z.string().nullable(),
  actor: z.string(),
  event_type: z.string(),
  title: z.string(),
  payload: z.record(z.string(), z.unknown()),
  tone: z.string().default("default"),
});

export type AuditEvent = z.infer<typeof auditEventSchema>;

export async function getAudit(intentId: string): Promise<AuditEvent[]> {
  const response = await fetch(apiUrl(`/v1/intents/${intentId}/audit`), { cache: "no-store" });
  if (!response.ok) {
    throw await readError(response);
  }
  return z.array(auditEventSchema).parse(await response.json());
}
