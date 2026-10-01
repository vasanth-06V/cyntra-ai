import { ChatThreadView } from "./ChatThreadView";

export default async function ChatThreadPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return <ChatThreadView conversationId={conversationId} />;
}
