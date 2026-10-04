// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { InterviewsView } from "./interviews/InterviewsView";
import { ReportsView } from "./reports/ReportsView";
import { ChatThreadView } from "./chat/[conversationId]/ChatThreadView";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({ select: () => ({ eq: () => ({ maybeSingle: async () => ({ data: { title: "My chat" } }) }) }) }),
  }),
}));
// The window is not under test here: it just reports how many messages it was given.
vi.mock("@/components/chat/ChatWindow", () => ({
  ChatWindow: ({ initialMessages }: { initialMessages: unknown[] }) => <p>messages in window: {initialMessages.length}</p>,
}));

const interview = (n: number, status = "completed") => ({
  id: `i${n}`,
  type: "behavioral",
  status,
  phase: null,
  provider: "gemini",
  resume_id: "r1",
  started_at: null,
  ends_at: null,
  created_at: "2026-01-01T10:00:00Z",
});
const page = (from: number, count: number, status = "completed") =>
  Array.from({ length: count }, (_, k) => interview(from + k, status));

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset();
});

describe("InterviewsView: Show older interviews", () => {
  it("keeps the loaded list and offers a retry when the next page fails (M-12)", async () => {
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      if (path === "/interviews") return page(1, 50) as never;
      throw new ApiError(503, "Busy right now");
    });
    const user = userEvent.setup();
    renderWithProviders(<InterviewsView />);
    const list = await screen.findByRole("list", { name: "Your interviews" });
    expect(within(list).getAllByRole("link")).toHaveLength(50);

    await user.click(screen.getByRole("button", { name: "Show older interviews" }));
    expect(await screen.findByText("Could not load older interviews")).toBeInTheDocument();
    expect(screen.getByText("Busy right now")).toBeInTheDocument();
    // The page-level error block did not replace the list.
    expect(screen.getByRole("list", { name: "Your interviews" })).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Your interviews" })).getAllByRole("link")).toHaveLength(50);
    expect(screen.getByRole("button", { name: "Show older interviews" })).toBeInTheDocument();

    // The toast's Retry loads the page once the server recovers.
    vi.mocked(apiClient.get).mockResolvedValue(page(51, 3) as never);
    await user.click(screen.getByRole("button", { name: "Retry" }));
    await waitFor(() => expect(within(screen.getByRole("list", { name: "Your interviews" })).getAllByRole("link")).toHaveLength(53));
    expect(screen.queryByRole("button", { name: "Show older interviews" })).not.toBeInTheDocument();
  });
});

describe("ReportsView: completed interviews beyond the first 50", () => {
  it("loads further pages so an older completed interview can still get a report", async () => {
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      if (path === "/reports") return [] as never;
      if (path === "/interviews") return page(1, 50) as never;
      if (path === "/interviews?limit=50&offset=50") return page(51, 2) as never;
      throw new Error(`unexpected ${path}`);
    });
    const user = userEvent.setup();
    renderWithProviders(<ReportsView />);
    await screen.findAllByRole("button", { name: /Get my report for the/ });
    expect(screen.getAllByRole("button", { name: /Get my report for the/ })).toHaveLength(50);

    await user.click(screen.getByRole("button", { name: "Show older interviews" }));
    await waitFor(() => expect(screen.getAllByRole("button", { name: /Get my report for the/ })).toHaveLength(52));
    expect(screen.queryByRole("button", { name: "Show older interviews" })).not.toBeInTheDocument();
  });

  it("does not show the control when the first page is not full", async () => {
    vi.mocked(apiClient.get).mockImplementation(async (path: string) =>
      (path === "/reports" ? [] : page(1, 3)) as never
    );
    renderWithProviders(<ReportsView />);
    await screen.findAllByRole("button", { name: /Get my report for the/ });
    expect(screen.queryByRole("button", { name: "Show older interviews" })).not.toBeInTheDocument();
  });
});

describe("ChatThreadView: Show older messages", () => {
  const messages = (n: number) =>
    Array.from({ length: n }, (_, k) => ({ id: `m${k}`, role: "user", provider: null, content: `m${k}`, created_at: "" }));

  function route(count: number, fullCount = 320) {
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      if (path === "/keys") return [] as never;
      if (path.endsWith("/messages?limit=500")) return messages(fullCount) as never;
      if (path.endsWith("/messages")) return messages(count) as never;
      throw new Error(`unexpected ${path}`);
    });
  }

  it("is offered when exactly 200 messages came back, and loads the longer history", async () => {
    route(200);
    const user = userEvent.setup();
    renderWithProviders(<ChatThreadView conversationId="c1" />);
    expect(await screen.findByText("messages in window: 200")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Show older messages" }));
    expect(await screen.findByText("messages in window: 320")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show older messages" })).not.toBeInTheDocument();
  });

  it("is not offered for a shorter conversation", async () => {
    route(12);
    renderWithProviders(<ChatThreadView conversationId="c1" />);
    expect(await screen.findByText("messages in window: 12")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Show older messages" })).not.toBeInTheDocument();
  });
});
