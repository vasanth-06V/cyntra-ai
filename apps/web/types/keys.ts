export type ProviderName = "gemini" | "claude" | "groq";
export type KeySlot = "primary" | "backup";

export type ProviderKey = {
  id: string;
  provider: ProviderName;
  slot: KeySlot;
  is_valid: boolean;
  last_validated_at: string | null;
};

export const PROVIDER_INFO: Record<
  ProviderName,
  { label: string; instructions: string; getKeyUrl: string }
> = {
  gemini: {
    label: "Gemini",
    instructions:
      "Open Google AI Studio, sign in, click \"Get API key\", then \"Create API key\".",
    getKeyUrl: "https://aistudio.google.com/apikey",
  },
  claude: {
    label: "Claude",
    instructions:
      "Open the Anthropic Console, go to Settings → API Keys, then \"Create Key\".",
    getKeyUrl: "https://console.anthropic.com/settings/keys",
  },
  groq: {
    label: "Groq",
    instructions:
      "Open the GroqCloud console, go to API Keys, then \"Create API Key\".",
    getKeyUrl: "https://console.groq.com/keys",
  },
};
