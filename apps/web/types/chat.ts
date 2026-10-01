import type { ProviderName } from "./keys";

export type Conversation = {
  id: string;
  title: string | null;
  created_at: string;
};

export type ChatMessage = {
  id: string;
  role: "user" | "assistant";
  provider: ProviderName | null;
  content: string;
  created_at: string;
};
