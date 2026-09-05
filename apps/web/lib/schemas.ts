import { z } from "zod";

const amountSchema = z.number().positive();

export const hardConstraintsSchema = z.object({
  max_amount: amountSchema,
  currency: z.literal("INR"),
  category: z.string().nullable().optional(),
  quantity: z.number().int().positive().default(1),
  allowed_merchants: z.array(z.string()).default([]),
  forbidden_attributes: z.array(z.string()).default([]),
  must_include: z.array(z.string()).default([]),
  time_window: z.string().nullable().optional(),
  location: z.string().nullable().optional(),
});

export const preferencesSchema = z
  .object({
    weight: z.string().nullable().optional(),
    use_case: z.string().nullable().optional(),
    preferred_brands: z.array(z.string()).default([]),
  })
  .passthrough();

export const intentContractSchema = z.object({
  intent_id: z.string().uuid().nullable().optional(),
  created_at: z.string().nullable().optional(),
  raw_request: z.string().min(1),
  goal: z.string().min(1),
  hard_constraints: hardConstraintsSchema,
  preferences: preferencesSchema.default({ preferred_brands: [] }),
  approval_required_for: z.array(z.string()).default([]),
  expires_at: z.string().nullable().optional(),
  status: z.enum([
    "draft",
    "active",
    "paused",
    "approved",
    "blocked",
    "expired",
    "paid",
  ]).default("draft"),
});

export const proposedActionSchema = z.object({
  action: z.literal("purchase").default("purchase"),
  amount: amountSchema,
  currency: z.string().default("INR"),
  merchant: z.string().min(1),
  product: z.object({
    id: z.string(),
    name: z.string(),
    category: z.string().nullable().optional(),
    attributes: z.record(z.string(), z.unknown()).default({}),
  }),
  quantity: z.number().int().positive().default(1),
  line_items: z
    .array(
      z.object({
        sku: z.string(),
        name: z.string(),
        amount: amountSchema,
        quantity: z.number().int().positive().default(1),
      }),
    )
    .default([]),
  agent_rationale: z.string().nullable().optional(),
  scheduled_at: z.string().nullable().optional(),
  location: z.string().nullable().optional(),
});

export const semanticAssessmentSchema = z.object({
  semantic_match: z.number().min(0).max(1).nullable(),
  violated_preferences: z.array(z.string()).default([]),
  substitution_severity: z.enum(["none", "minor", "major"]).default("none"),
  reason: z.string().default(""),
  error: z.boolean().default(false),
});

export const decisionSchema = z.object({
  verdict: z.enum(["APPROVE", "PAUSE", "BLOCK"]),
  reasons: z.array(z.string()).default([]),
  policy_version: z.string(),
  proposal_id: z.string().uuid().nullable().optional(),
});

export type IntentContract = z.infer<typeof intentContractSchema>;
export type ProposedAction = z.infer<typeof proposedActionSchema>;
export type SemanticAssessment = z.infer<typeof semanticAssessmentSchema>;
export type Decision = z.infer<typeof decisionSchema>;
