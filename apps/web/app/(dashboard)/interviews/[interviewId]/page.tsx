import { InterviewRoomView } from "./InterviewRoomView";

export const metadata = { title: "Interview room" };

export default async function InterviewRoomPage({
  params,
}: {
  params: Promise<{ interviewId: string }>;
}) {
  const { interviewId } = await params;
  return <InterviewRoomView interviewId={interviewId} />;
}
