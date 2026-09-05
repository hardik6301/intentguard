import { redirect } from "next/navigation";

type IntentShellProps = {
  params: Promise<{ id: string }>;
};

export default async function IntentShellPage({ params }: IntentShellProps) {
  const { id } = await params;
  redirect(`/intents/${id}/run`);
}
