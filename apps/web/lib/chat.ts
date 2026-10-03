export const MAX_CHAT_TITLE_LENGTH = 120;

/** First problem with a proposed conversation title, or null when it can be saved. */
export function validateChatTitle(value: string): string | null {
  const length = value.trim().length;
  if (length === 0) return "Give the chat a title.";
  if (length > MAX_CHAT_TITLE_LENGTH) return `Keep the title to ${MAX_CHAT_TITLE_LENGTH} characters or fewer.`;
  return null;
}
