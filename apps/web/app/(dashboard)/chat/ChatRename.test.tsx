// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { ChatListView } from "./ChatListView";
import { ChatThreadView } from "./[conversationId]/ChatThreadView";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({ eq: () => ({ maybeSingle: async () => ({ data: { title: "Salary negotiation" } }) }) }),
    }),
  }),
}));
vi.mock("@/components/chat/ChatWindow", () => ({ ChatWindow: () => <p>chat window</p> }));

const conversations = [
  { id: "c1", title: "Salary negotiation", created_at: "2026-01-01T10:00:00Z" },
  { id: "c2", title: null, created_at: "2026-01-02T10:00:00Z" },
];

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset().mockResolvedValue(conversations as never);
  vi.mocked(apiClient.patch).mockReset();
});

describe("ChatListView rename", () => {
  it("renames a chat inline with Enter, sends the trimmed title and toasts", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ id: "c1", title: "Offer talk", created_at: "x" } as never);
    const user = userEvent.setup();
    renderWithProviders(<ChatListView />);

    await user.click(await screen.findByRole("button", { name: "Rename conversation Salary negotiation" }));
    const input = screen.getByLabelText("New title for Salary negotiation");
    expect(input).toHaveFocus();
    await user.clear(input);
    await user.type(input, "  Offer talk  {Enter}");

    await waitFor(() =>
      expect(apiClient.patch).toHaveBeenCalledWith("/chat/conversations/c1", { title: "Offer talk" })
    );
    const list = screen.getByRole("list", { name: "Your conversations" });
    expect(await within(list).findByRole("link", { name: "Offer talk" })).toHaveAttribute("href", "/chat/c1");
    expect(await screen.findByText("Chat renamed")).toBeInTheDocument();
  });

  it("validates: an empty title and one over 120 characters cannot be saved", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ChatListView />);
    await user.click(await screen.findByRole("button", { name: "Rename conversation Salary negotiation" }));
    const input = screen.getByLabelText("New title for Salary negotiation");

    await user.clear(input);
    expect(screen.getByRole("alert")).toHaveTextContent(/title/i);
    expect(screen.getByRole("button", { name: "Save name" })).toBeDisabled();

    await user.type(input, "a".repeat(121));
    expect(screen.getByRole("alert")).toHaveTextContent("120");
    await user.keyboard("{Enter}");
    expect(apiClient.patch).not.toHaveBeenCalled();
  });

  it("cancels with Escape without a request", async () => {
    const user = userEvent.setup();
    renderWithProviders(<ChatListView />);
    await user.click(await screen.findByRole("button", { name: "Rename conversation Salary negotiation" }));
    await user.type(screen.getByLabelText("New title for Salary negotiation"), "zzz{Escape}");
    expect(screen.queryByLabelText(/New title for/)).not.toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Salary negotiation" })).toBeInTheDocument();
    expect(apiClient.patch).not.toHaveBeenCalled();
  });

  it("shows the API error inline and keeps the editor open on failure", async () => {
    vi.mocked(apiClient.patch).mockRejectedValue(new ApiError(500, "could not rename"));
    const user = userEvent.setup();
    renderWithProviders(<ChatListView />);
    await user.click(await screen.findByRole("button", { name: "Rename conversation Salary negotiation" }));
    await user.type(screen.getByLabelText("New title for Salary negotiation"), "x{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("could not rename");
    expect(screen.getByLabelText("New title for Salary negotiation")).toBeInTheDocument();
  });
});

describe("ChatThreadView rename", () => {
  beforeEach(() => {
    vi.mocked(apiClient.get).mockImplementation((async (path: string) =>
      path.endsWith("/messages") ? [] : []) as never);
  });

  it("shows the title in a header and renames it from there", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ id: "c1", title: "New plan", created_at: "x" } as never);
    const user = userEvent.setup();
    renderWithProviders(<ChatThreadView conversationId="c1" />);

    expect(await screen.findByRole("heading", { name: "Salary negotiation" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Rename this chat" }));
    const input = screen.getByLabelText("New title for this chat");
    await user.clear(input);
    await user.type(input, "New plan{Enter}");

    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledWith("/chat/conversations/c1", { title: "New plan" }));
    expect(await screen.findByRole("heading", { name: "New plan" })).toBeInTheDocument();
    expect(await screen.findByText("Chat renamed")).toBeInTheDocument();
  });

  it("keeps the old title and shows the error when renaming fails", async () => {
    vi.mocked(apiClient.patch).mockRejectedValue(new ApiError(422, "Title is too long"));
    const user = userEvent.setup();
    renderWithProviders(<ChatThreadView conversationId="c1" />);
    await user.click(await screen.findByRole("button", { name: "Rename this chat" }));
    await user.type(screen.getByLabelText("New title for this chat"), "x{Enter}");
    expect(await screen.findByRole("alert")).toHaveTextContent("Title is too long");
    await user.click(screen.getByRole("button", { name: "Cancel rename" }));
    expect(screen.getByRole("heading", { name: "Salary negotiation" })).toBeInTheDocument();
  });
});
