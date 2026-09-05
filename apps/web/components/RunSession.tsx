"use client";

import { AgentRunSession } from "@/components/AgentRunSession";

type RunSessionProps = {
  intentId: string;
};

export function RunSession({ intentId }: RunSessionProps) {
  return <AgentRunSession intentId={intentId} />;
}
