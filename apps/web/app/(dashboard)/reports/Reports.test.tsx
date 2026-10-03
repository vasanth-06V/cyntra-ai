// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import type { ReportResponse, ReportSummary } from "@/types/reports";
import { ReportsView } from "./ReportsView";
import { ReportDetailView } from "./[interviewId]/ReportDetailView";

const push = vi.hoisted(() => vi.fn());
vi.mock("next/navigation", () => ({ useRouter: () => ({ push, refresh: vi.fn() }) }));
vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

const summary = (id: string, type = "behavioral"): ReportSummary => ({
  interview_id: id,
  interview_type: type,
  overall_score: 72,
  created_at: "2026-01-01T10:00:00Z",
  expires_at: "2099-01-08T10:00:00Z",
});

const full = (id: string): ReportResponse => ({
  ...summary(id),
  report: {
    version: 1,
    interview: { id, type: "behavioral", started_at: null, minutes_used: 55 },
    overall_score: 72,
    band: "Good",
    verdict: "A solid showing.",
    dimensions: [{ key: "communication", label: "Communication", score: 4, reason: "Clear.", quote: null }],
    strengths: [{ point: "Structured answers", quote: null }],
    improvements: [{ point: "Quantify impact", quote: null }],
    phase_notes: [],
    next_steps: ["Practise STAR answers"],
    coding: [],
    stats: { answers: 10, avg_words: 80, phases: [], omitted_turns: 0 },
    disclaimer: "Practice feedback only.",
  },
});

beforeEach(() => {
  push.mockReset();
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.delete).mockReset();
});

describe("ReportsView", () => {
  function listResponses(reports: ReportSummary[]) {
    vi.mocked(apiClient.get).mockImplementation(async (path: string) => {
      if (path === "/reports") return reports as never;
      if (path === "/interviews") return [] as never;
      throw new Error(`unexpected ${path}`);
    });
  }

  it("deletes a report from the list after confirming", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    listResponses([summary("i1"), summary("i2", "hr")]);
    vi.mocked(apiClient.delete).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<ReportsView />);

    await user.click(await screen.findByRole("button", { name: "Delete Behavioral report" }));
    const dialog = await screen.findByRole("alertdialog");
    await user.click(within(dialog).getByRole("button", { name: "Delete report" }));

    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith("/reports/i1"));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Delete Behavioral report" })).not.toBeInTheDocument());
    expect(screen.getByRole("button", { name: "Delete HR report" })).toBeInTheDocument();
  });

  it("shows an error with a retry when the list cannot be loaded", async () => {
    vi.mocked(apiClient.get).mockRejectedValue(new ApiError(500, "Reports are unavailable"));
    renderWithProviders(<ReportsView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("Reports are unavailable");
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});

describe("ReportDetailView", () => {
  it("deletes the report only after the dialog, then returns to the list", async () => {
    vi.mocked(apiClient.get).mockResolvedValue(full("i1") as never);
    vi.mocked(apiClient.delete).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<ReportDetailView interviewId="i1" />);

    await user.click(await screen.findByRole("button", { name: /Delete now/ }));
    expect(apiClient.delete).not.toHaveBeenCalled();
    await user.click(await screen.findByRole("button", { name: "Delete report" }));

    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith("/reports/i1"));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/reports"));
  });

  it("keeps the report on screen when the delete fails", async () => {
    vi.mocked(apiClient.get).mockResolvedValue(full("i1") as never);
    vi.mocked(apiClient.delete).mockRejectedValue(new ApiError(500, "Could not reach storage"));
    const user = userEvent.setup();
    renderWithProviders(<ReportDetailView interviewId="i1" />);

    await user.click(await screen.findByRole("button", { name: /Delete now/ }));
    await user.click(await screen.findByRole("button", { name: "Delete report" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Could not reach storage");
    expect(push).not.toHaveBeenCalled();
    expect(screen.getByText("A solid showing.")).toBeInTheDocument();
  });

  it("offers save as PDF (print) and download buttons", async () => {
    vi.mocked(apiClient.get).mockResolvedValue(full("i1") as never);
    const print = vi.spyOn(window, "print").mockImplementation(() => {});
    const user = userEvent.setup();
    renderWithProviders(<ReportDetailView interviewId="i1" />);
    await user.click(await screen.findByRole("button", { name: "Save as PDF" }));
    expect(print).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Download text" })).toBeEnabled();
  });
});
