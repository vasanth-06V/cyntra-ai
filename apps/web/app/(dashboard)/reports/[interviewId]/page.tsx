import { ReportDetailView } from "./ReportDetailView";

export const metadata = { title: "Interview report" };

export default async function ReportPage({
  params,
}: {
  params: Promise<{ interviewId: string }>;
}) {
  const { interviewId } = await params;
  return <ReportDetailView interviewId={interviewId} />;
}
