# External facts the product depends on

Each fact: what, source, date verified. Re-check before Phases 7, 8 and 10, and before relying on a model name.
Format: `fact — source — verified`.

## Hosting
- Render free web service spins down after 15 min without inbound traffic; cold start about 1 min; 750 free instance-hours/month per workspace; ephemeral filesystem; WebSockets supported and count as traffic; no inbound private-network traffic — https://render.com/docs/free — 2026-10-02
- Vercel Functions: request/response body cap 4.5 MB; Hobby max duration 300 s (default and maximum); 2 GB / 1 vCPU — https://vercel.com/docs/functions/limitations — 2026-10-02

## Gemini
- Rate limits are per project (not per key); daily (RPD) quotas reset at midnight Pacific time — https://ai.google.dev/gemini-api/docs/rate-limits — 2026-10-02
- `gemini-embedding-001`: task types SEMANTIC_SIMILARITY, CLASSIFICATION, CLUSTERING, RETRIEVAL_DOCUMENT, RETRIEVAL_QUERY, CODE_RETRIEVAL_QUERY, QUESTION_ANSWERING, FACT_VERIFICATION; output dimensionality 128–3072 (768/1536/3072 recommended); dimensions other than 3072 must be normalized manually; 2,048 input tokens — https://ai.google.dev/gemini-api/docs/embeddings — 2026-10-02
- Thinking: reported separately (thought tokens) and billed with output; default-on for gemini-3.8-flash (medium) and gemini-3.5-flash-lite (minimal); off by default for gemini-2.5-flash-lite — https://ai.google.dev/gemini-api/docs/thinking — 2026-10-02
- Live API: audio-only sessions limited to 15 min (extendable with context-window compression and session resumption); 128k context for native-audio models; input raw 16-bit PCM 16 kHz, output 24 kHz; automatic VAD with configurable sensitivity — https://ai.google.dev/gemini-api/docs/live-api/capabilities — 2026-10-02
- Error handling guidance: retry 429/408/5xx with exponential backoff and jitter; the docs do not specify retry-delay or quota-type fields in 429 bodies — https://ai.google.dev/gemini-api/docs/troubleshooting — 2026-10-02
- `google-generativeai` is deprecated in favor of `google-genai` (reported by the LLM audit; confirm before migrating)

## Claude
- Current API IDs: `claude-fable-5-1`, `claude-opus-5-5`, `claude-sonnet-5-5`, `claude-haiku-4-5-20251001`; Sonnet 5.5 adaptive thinking; Haiku 4.5 retirement not sooner than 2026-10-15; `claude-sonnet-5` is a legacy model — https://platform.claude.com/docs/en/models/overview — 2026-10-02

## Groq
- Production models include Llama 3.1 8B (`llama-3.1-8b-instant`), Llama 3.3 70B (`llama-3.3-70b-versatile`), OpenAI GPT-OSS 20B/120B, Whisper speech-to-text — https://console.groq.com/docs/models — 2026-10-02

## Judge0
- Self-hosting is free; official hosted plans reported at about EUR 27/month for 2,000 submissions/day (EUR 54 for 5,000, EUR 107 for 10,000); the free shared RapidAPI key is reported at about 50 requests/day (anecdotal) — web search results (judge0.com, RapidAPI pricing) — 2026-10-02 — **verify before Phase 7**

## Not yet measured (to be recorded by the user-run smoke script)
- Real Gemini 429/503/400 response bodies and any retry/quota fields
- Time to first token and thinking-token counts for our configured Gemini alias
- Live API free-tier concurrent-session limits
- Measured Render cold-start time
