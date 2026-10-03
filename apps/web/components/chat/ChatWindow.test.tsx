// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import type { ChatMessage } from "@/types/chat";
import { ChatWindow } from "./ChatWindow";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn(), streamPost: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

async function* chunks(...parts: string[]) {
  for (const p of parts) yield p;
}

const history: ChatMessage[] = [
  { id: "m1", role: "assistant", provider: "gemini", content: "Hello! Ask me anything.", created_at: "2026-01-01" },
];

beforeEach(() => {
  vi.mocked(apiClient.streamPost).mockReset();
});

describe("ChatWindow", () => {
  it("sends with the Send button and streams the reply into the log", async () => {
    vi.mocked(apiClient.streamPost).mockReturnValue(chunks("Sure, ", "here you go.") as never);
    const user = userEvent.setup();
    renderWithProviders(<ChatWindow conversationId="c1" initialMessages={history} validProviders={["gemini"]} />);

    await user.type(screen.getByLabelText("Message"), "Help me prep");
    await user.click(screen.getByRole("button", { name: /Send/ }));

    expect(apiClient.streamPost).toHaveBeenCalledWith("/chat/conversations/c1/messages", {
      provider: "gemini",
      content: "Help me prep",
    });
    const log = screen.getByRole("log");
    expect(await screen.findByText("Sure, here you go.")).toBeInTheDocument();
    expect(log).toHaveTextContent("Help me prep");
    expect(screen.getByLabelText("Message")).toHaveValue("");
  });

  it("sends on Enter and inserts a new line on Shift+Enter", async () => {
    vi.mocked(apiClient.streamPost).mockReturnValue(chunks("ok") as never);
    const user = userEvent.setup();
    renderWithProviders(<ChatWindow conversationId="c1" initialMessages={[]} validProviders={["gemini"]} />);

    const box = screen.getByLabelText("Message");
    await user.type(box, "line one{Shift>}{Enter}{/Shift}line two");
    expect(apiClient.streamPost).not.toHaveBeenCalled();
    expect(box).toHaveValue("line one\nline two");

    await user.keyboard("{Enter}");
    await waitFor(() => expect(apiClient.streamPost).toHaveBeenCalledTimes(1));
    expect(vi.mocked(apiClient.streamPost).mock.calls[0][1]).toEqual({
      provider: "gemini",
      content: "line one\nline two",
    });
  });

  it("restores the draft and shows the error when the send fails before any reply", async () => {
    vi.mocked(apiClient.streamPost).mockImplementation(() => {
      return (async function* () {
        throw new ApiError(429, "Rate limit reached");
      })() as never;
    });
    const user = userEvent.setup();
    renderWithProviders(<ChatWindow conversationId="c1" initialMessages={[]} validProviders={["gemini"]} />);

    await user.type(screen.getByLabelText("Message"), "Hello there");
    await user.click(screen.getByRole("button", { name: /Send/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Rate limit reached");
    expect(screen.getByLabelText("Message")).toHaveValue("Hello there");
    expect(screen.getByRole("log")).not.toHaveTextContent("Hello there");
  });

  it("points to API Keys when no provider key is usable", () => {
    renderWithProviders(<ChatWindow conversationId="c1" initialMessages={[]} validProviders={[]} />);
    expect(screen.getByRole("link", { name: /Add one in API Keys/ })).toHaveAttribute("href", "/settings/api-keys");
    expect(screen.getByLabelText("Message")).toBeDisabled();
  });

  it("copies an assistant reply", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<ChatWindow conversationId="c1" initialMessages={history} validProviders={["gemini"]} />);
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    await user.click(screen.getByRole("button", { name: "Copy this reply" }));
    expect(writeText).toHaveBeenCalledWith("Hello! Ask me anything.");
    expect(await screen.findByText("Copied to clipboard")).toBeInTheDocument();
  });
});
