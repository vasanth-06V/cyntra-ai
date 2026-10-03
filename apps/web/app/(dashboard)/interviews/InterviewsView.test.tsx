// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { InterviewsView } from "./InterviewsView";

vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn(), refresh: vi.fn() }) }));
vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

const iv = (n: number, over: Record<string, unknown> = {}) => ({
  id: `i${n}`,
  type: n === 1 ? "behavioral" : "coding",
  status: "completed",
  phase: null,
  provider: "gemini",
  resume_id: n === 2 ? null : "r1", // resume_id can be null after a resume was deleted
  started_at: null,
  ends_at: null,
  created_at: `2026-01-0${n}T10:00:00Z`,
  ...over,
});

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset().mockResolvedValue([iv(1), iv(2)] as never);
  vi.mocked(apiClient.delete).mockReset();
});

describe("InterviewsView", () => {
  it("links each row to its room, including an interview without a resume", async () => {
    renderWithProviders(<InterviewsView />);
    const list = await screen.findByRole("list", { name: "Your interviews" });
    const links = within(list).getAllByRole("link");
    expect(links.map((a) => a.getAttribute("href"))).toEqual(["/interviews/i1", "/interviews/i2"]);
  });

  it("deletes an interview after the dialog explains what goes with it, then removes the row", async () => {
    vi.mocked(apiClient.delete).mockResolvedValue(undefined as never);
    const user = userEvent.setup();
    renderWithProviders(<InterviewsView />);

    const buttons = await screen.findAllByRole("button", { name: /^Delete .* interview from/ });
    await user.click(buttons[0]);
    const dialog = await screen.findByRole("alertdialog", { name: "Delete this interview?" });
    expect(dialog).toHaveTextContent(/transcript/i);
    expect(dialog).toHaveTextContent(/report/i);
    expect(apiClient.delete).not.toHaveBeenCalled();
    await user.click(within(dialog).getByRole("button", { name: "Delete interview" }));

    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith("/interviews/i1"));
    await waitFor(() => expect(within(screen.getByRole("list", { name: "Your interviews" })).getAllByRole("link")).toHaveLength(1));
    expect(await screen.findByText("Interview deleted")).toBeInTheDocument();
  });

  it("keeps the row when the dialog is cancelled", async () => {
    const user = userEvent.setup();
    renderWithProviders(<InterviewsView />);
    await user.click((await screen.findAllByRole("button", { name: /^Delete .* interview from/ }))[0]);
    await user.click(await screen.findByRole("button", { name: "Cancel" }));
    expect(apiClient.delete).not.toHaveBeenCalled();
    expect(within(screen.getByRole("list", { name: "Your interviews" })).getAllByRole("link")).toHaveLength(2);
  });

  it("shows the failure inside the dialog and keeps the row when delete fails", async () => {
    vi.mocked(apiClient.delete).mockRejectedValue(new ApiError(500, "could not delete interview"));
    const user = userEvent.setup();
    renderWithProviders(<InterviewsView />);
    await user.click((await screen.findAllByRole("button", { name: /^Delete .* interview from/ }))[0]);
    await user.click(await screen.findByRole("button", { name: "Delete interview" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("could not delete interview");
    expect(within(screen.getByRole("list", { name: "Your interviews" })).getAllByRole("link")).toHaveLength(2);
  });
});
