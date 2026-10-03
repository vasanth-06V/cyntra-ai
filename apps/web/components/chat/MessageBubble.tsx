import { motion } from "framer-motion";
import type { ChatMessage } from "@/types/chat";
import { PROVIDER_INFO } from "@/types/keys";
import { SparkleIcon, UserIcon } from "@/components/ui/icons";

/**
 * One chat or interview message. `assistantLabel` names the other side when the
 * message has no provider (the interview room passes "Interviewer").
 */
export function MessageBubble({
  message,
  assistantLabel,
}: {
  message: ChatMessage;
  assistantLabel?: string;
}) {
  const isUser = message.role === "user";
  const name = isUser
    ? "You"
    : (assistantLabel ?? (message.provider ? PROVIDER_INFO[message.provider].label : "Assistant"));

  return (
    <motion.div
      initial={{ opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
      className={`flex items-end gap-2.5 ${isUser ? "flex-row-reverse" : ""}`}
    >
      <span
        aria-hidden="true"
        className={`mb-0.5 hidden h-8 w-8 shrink-0 items-center justify-center rounded-full sm:flex ${
          isUser ? "bg-secondary text-muted-foreground" : "bg-accent text-accent-foreground"
        }`}
      >
        {isUser ? <UserIcon size={16} /> : <SparkleIcon size={16} />}
      </span>
      <div className={`flex min-w-0 max-w-[85%] flex-col sm:max-w-[75%] ${isUser ? "items-end" : "items-start"}`}>
        <span className="mb-1 px-1 text-xs font-medium text-muted-foreground">{name}</span>
        <div
          className={`whitespace-pre-wrap break-words px-4 py-2.5 text-sm leading-6 shadow-xs ${
            isUser
              ? "rounded-2xl rounded-br-md bg-primary text-primary-foreground"
              : "rounded-2xl rounded-bl-md border border-border bg-card text-card-foreground"
          }`}
        >
          {message.content || <TypingDots />}
        </div>
      </div>
    </motion.div>
  );
}

/** Three softly fading dots; decorative, shown only while a reply is on its way. */
export function TypingDots() {
  return (
    <span className="inline-flex items-center gap-1 py-1" aria-hidden="true">
      <span className="h-1.5 w-1.5 animate-dot rounded-full bg-current [animation-delay:-0.32s]" />
      <span className="h-1.5 w-1.5 animate-dot rounded-full bg-current [animation-delay:-0.16s]" />
      <span className="h-1.5 w-1.5 animate-dot rounded-full bg-current" />
    </span>
  );
}
