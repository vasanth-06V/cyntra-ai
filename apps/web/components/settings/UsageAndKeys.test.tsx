// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { UsageToday } from "./UsageToday";
import { ApiKeysView } from "@/app/(dashboard)/settings/api-keys/ApiKeysView";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset();
});

describe("UsageToday", () => {
  it("lists today's usage per provider and kind", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([
      { provider: "gemini", kind: "chat", requests: 1, input_tokens: 1200, output_tokens: 300, thought_tokens: 50 },
      { provider: "gemini", kind: "embed", requests: 4, input_tokens: 800, output_tokens: 0 },
    ] as never);
    renderWithProviders(<UsageToday />);
    expect(await screen.findByText("1 request")).toBeInTheDocument();
    expect(screen.getByText("4 requests")).toBeInTheDocument();
    expect(screen.getByText("chat")).toBeInTheDocument();
    expect(screen.getByText("embeddings")).toBeInTheDocument();
    expect(screen.getByText(/1,200 in \/ 300 out tokens \(\+50 thinking\)/)).toBeInTheDocument();
    expect(apiClient.get).toHaveBeenCalledWith("/usage");
  });

  it("says so when nothing was used today", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([] as never);
    renderWithProviders(<UsageToday />);
    expect(await screen.findByText("No requests yet today.")).toBeInTheDocument();
  });

  it("shows an honest error (not 'no requests') and can retry", async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(new Error("down")).mockResolvedValueOnce([] as never);
    renderWithProviders(<UsageToday />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not load today's usage.");
    expect(screen.queryByText("No requests yet today.")).not.toBeInTheDocument();
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    expect(await screen.findByText("No requests yet today.")).toBeInTheDocument();
  });
});

describe("ApiKeysView", () => {
  const key = { id: "k1", provider: "gemini", slot: "primary", is_valid: true, last_validated_at: "2026-01-01T00:00:00Z" };

  function route(keys: unknown, usage: unknown = []) {
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      if (path === "/keys") {
        if (keys instanceof Error) throw keys;
        return keys as never;
      }
      if (path === "/usage") return usage as never;
      throw new Error(`unexpected GET ${path}`);
    });
  }

  it("renders a section per provider and the usage card once keys load", async () => {
    route([key]);
    renderWithProviders(<ApiKeysView />);
    expect(await screen.findByRole("heading", { name: "API Keys" })).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText("Used today")).toBeInTheDocument());
    // one card per provider
    for (const name of [/gemini/i, /groq/i, /claude/i]) {
      expect(screen.getAllByText(name).length).toBeGreaterThan(0);
    }
  });

  it("shows the load error with a retry that reloads the keys", async () => {
    route(new ApiError(500, "Keys unavailable"));
    renderWithProviders(<ApiKeysView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Keys unavailable");

    route([key]);
    await userEvent.setup().click(screen.getByRole("button", { name: "Try again" }));
    await waitFor(() => expect(screen.queryByRole("alert")).not.toBeInTheDocument());
    expect(await screen.findByText("Used today")).toBeInTheDocument();
  });
});
