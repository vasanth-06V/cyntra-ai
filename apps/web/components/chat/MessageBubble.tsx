import { motion } from "framer-motion";
import type { ChatMessage } from "@/types/chat";
import { PROVIDER_INFO } from "@/types/keys";
import { useToast } from "@/components/ui/Toast";
import { CopyIcon, SparkleIcon, UserIcon } from "@/components/ui/icons";

/**
 * One chat or interview message. `assistantLabel` names the other side when the
 * message has no provider (the interview room passes "Interviewer").
 */
export function MessageBubble({
  message,
  assistantLabel,
  copyable = false,
}: {
  message: ChatMessage;
  assistantLabel?: string;
  /** Shows a copy button under assistant messages (chat only). */
  copyable?: boolean;
}) {
  const { toast } = useToast();
  const isUser = message.role === "user";
  const name = isUser
    ? "You"
    : (assistantLabel ?? (message.provider ? PROVIDER_INFO[message.provider].label : "Assistant"));

  async function copy() {
    try {
      await navigator.clipboard.writeText(message.content);
      toast({ tone: "success", title: "Copied to clipboard", duration: 2200 });
    } catch {
      toast({ tone: "error", title: "Could not copy", description: "Select the text and copy it by hand." });
    }
  }

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
      <div className={`flex min-w-0 max-w-[85%] flex-col sm:max-w-[75%] lg:max-w-[42rem] ${isUser ? "items-end" : "items-start"}`}>
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
        {copyable && !isUser && message.content && (
          <button
            type="button"
            onClick={() => void copy()}
            aria-label="Copy this reply"
            className="mt-1 inline-flex cursor-pointer items-center gap-1 rounded-md px-1.5 py-0.5 text-xs text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          >
            <CopyIcon size={12} />
            Copy
          </button>
        )}
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
