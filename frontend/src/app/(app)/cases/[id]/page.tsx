import { CaseDetailClient } from "@/components/cases/CaseDetailClient";

type PageProps = {
  params: Promise<{ id: string }>;
};

export default async function CaseDetailPage({ params }: PageProps) {
  const { id } = await params;
  return <CaseDetailClient caseId={id} />;
}
