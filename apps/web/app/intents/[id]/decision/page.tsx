import { DecisionHero } from "@/components/DecisionHero";

type DecisionPageProps = {
  params: Promise<{ id: string }>;
};

export default async function DecisionPage({ params }: DecisionPageProps) {
  const { id } = await params;
  return <DecisionHero intentId={id} />;
}
