import { AuditPageBody } from "@/components/AuditTimeline";

type AuditPageProps = {
  params: Promise<{ id: string }>;
};

export default async function AuditPage({ params }: AuditPageProps) {
  const { id } = await params;
  return <AuditPageBody intentId={id} />;
}
