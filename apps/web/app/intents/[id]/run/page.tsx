import { RunSession } from "@/components/RunSession";

type RunPageProps = {
  params: Promise<{ id: string }>;
};

export default async function RunPage({ params }: RunPageProps) {
  const { id } = await params;
  return <RunSession intentId={id} />;
}
