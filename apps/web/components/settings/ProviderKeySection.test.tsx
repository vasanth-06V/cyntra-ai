// @vitest-environment jsdom
import { useState } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import type { ProviderKey } from "@/types/keys";
import { ProviderKeySection } from "./ProviderKeySection";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

const key = (over: Partial<ProviderKey> = {}): ProviderKey => ({
  id: "k1",
  provider: "groq",
  slot: "primary",
  is_valid: true,
  last_validated_at: "2026-01-01T00:00:00Z",
  ...over,
});

function Harness({ initial, provider = "groq" }: { initial: ProviderKey[]; provider?: "groq" | "gemini" }) {
  const [keys, setKeys] = useState(initial);
  return <ProviderKeySection provider={provider} keys={keys} onKeysChange={setKeys} />;
}

beforeEach(() => {
  vi.mocked(apiClient.delete).mockReset();
  vi.mocked(apiClient.post).mockReset();
});

describe("ProviderKeySection", () => {
  it("deletes a key only after the dialog is confirmed, and updates the card", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false); // must not matter
    vi.mocked(apiClient.delete).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[key()]} />);
    expect(screen.getByText("Connected")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Delete groq primary key" }));
    expect(apiClient.delete).not.toHaveBeenCalled();
    await user.click(await screen.findByRole("button", { name: "Delete key" }));

    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith("/keys/k1"));
    expect(await screen.findByText("Not connected")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Delete groq primary key" })).not.toBeInTheDocument();
  });

  it("keeps the key when the dialog is cancelled", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[key()]} />);
    await user.click(screen.getByRole("button", { name: "Delete groq primary key" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(apiClient.delete).not.toHaveBeenCalled();
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("shows the API error inside the dialog when deletion fails", async () => {
    vi.mocked(apiClient.delete).mockRejectedValue(new ApiError(500, "Key store unavailable"));
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[key()]} />);
    await user.click(screen.getByRole("button", { name: "Delete groq primary key" }));
    await user.click(await screen.findByRole("button", { name: "Delete key" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Key store unavailable");
    expect(screen.getByText("Connected")).toBeInTheDocument();
  });

  it("warns that Gemini is required before deleting the primary Gemini key", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness provider="gemini" initial={[key({ provider: "gemini" })]} />);
    await user.click(screen.getByRole("button", { name: "Delete gemini primary key" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(dialog).toHaveAccessibleDescription(/Gemini is required/);
  });

  it("saves a pasted key and reports validation", async () => {
    vi.mocked(apiClient.post).mockResolvedValue(key({ id: "k2", is_valid: true }));
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[]} />);

    await user.type(screen.getByLabelText("groq primary API key"), "gsk_1234567890");
    await user.click(screen.getByRole("button", { name: "Save groq primary key" }));

    await waitFor(() =>
      expect(apiClient.post).toHaveBeenCalledWith("/keys", {
        provider: "groq",
        slot: "primary",
        api_key: "gsk_1234567890",
      })
    );
    expect(await screen.findByText("Connected")).toBeInTheDocument();
  });

  it("refuses an obviously too-short key without calling the API", async () => {
    const user = userEvent.setup();
    renderWithProviders(<Harness initial={[]} />);
    await user.type(screen.getByLabelText("groq primary API key"), "abc");
    await user.click(screen.getByRole("button", { name: "Save groq primary key" }));
    expect(await screen.findByText(/too short/i)).toBeInTheDocument();
    expect(apiClient.post).not.toHaveBeenCalled();
  });
});
