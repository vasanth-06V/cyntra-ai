import { ChatThreadView } from "./ChatThreadView";

export const metadata = { title: "Chat" };

export default async function ChatThreadPage({
  params,
}: {
  params: Promise<{ conversationId: string }>;
}) {
  const { conversationId } = await params;
  return <ChatThreadView conversationId={conversationId} />;
}
