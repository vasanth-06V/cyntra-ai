// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { ChatListView } from "./ChatListView";

const push = vi.hoisted(() => vi.fn());
const state = vi.hoisted(() => ({
  deleted: [] as string[],
  result: { data: [{ id: "c1" }] as unknown[] | null, error: null as { message: string } | null },
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));
vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    from: (table: string) => ({
      delete: () => ({
        eq: (_col: string, id: string) => ({
          select: async () => {
            if (table === "conversations" && !state.result.error) state.deleted.push(id);
            return state.result;
          },
        }),
      }),
    }),
  }),
}));

const conversations = [
  { id: "c1", title: "Salary negotiation", created_at: "2026-01-01T10:00:00Z" },
  { id: "c2", title: null, created_at: "2026-01-02T10:00:00Z" },
];

beforeEach(() => {
  push.mockReset();
  state.deleted = [];
  state.result = { data: [{ id: "c1" }], error: null };
  vi.mocked(apiClient.get).mockReset().mockResolvedValue(conversations as never);
  vi.mocked(apiClient.post).mockReset();
});

describe("ChatListView", () => {
  it("deletes a conversation after confirming and removes it from the list", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    const user = userEvent.setup();
    renderWithProviders(<ChatListView />);

    await user.click(await screen.findByRole("button", { name: "Delete conversation Salary negotiation" }));
    expect(state.deleted).toEqual([]);
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete conversation" }));

    await waitFor(() => expect(state.deleted).toEqual(["c1"]));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(screen.queryByRole("link", { name: "Salary negotiation" })).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Untitled conversation" })).toBeInTheDocument();
  });

  it("keeps the conversation and explains when the database refuses", async () => {
    state.result = { data: null, error: { message: "boom" } };
    const user = userEvent.setup();
    renderWithProviders(<ChatListView />);

    await user.click(await screen.findByRole("button", { name: "Delete conversation Salary negotiation" }));
    await user.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Delete conversation" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not delete this conversation");
    expect(screen.getByRole("link", { name: "Salary negotiation" })).toBeInTheDocument();
  });

  it("opens a new chat", async () => {
    vi.mocked(apiClient.post).mockResolvedValue({ id: "c9", title: null, created_at: "2026-01-03" } as never);
    const user = userEvent.setup();
    renderWithProviders(<ChatListView />);
    await user.click(await screen.findByRole("button", { name: "New chat" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/chat/c9"));
  });

  it("reports a failed new chat without hiding the list", async () => {
    vi.mocked(apiClient.post).mockRejectedValue(new ApiError(500, "Could not create"));
    const user = userEvent.setup();
    renderWithProviders(<ChatListView />);
    await user.click(await screen.findByRole("button", { name: "New chat" }));
    expect(await screen.findByText("Could not start a new chat")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Salary negotiation" })).toBeInTheDocument();
  });
});
