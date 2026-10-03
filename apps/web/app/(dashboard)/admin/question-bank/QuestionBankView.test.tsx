// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import type { Question } from "@/types/interviews";
import { QuestionBankView } from "./QuestionBankView";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

const q = (id: string, text: string, type: Question["type"] = "behavioral"): Question => ({
  id,
  type,
  question: text,
  solution_code: null,
  solution_language: null,
  test_cases: null,
  tags: null,
  difficulty: null,
  topic: null,
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
});

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset();
  vi.mocked(apiClient.delete).mockReset();
  vi.mocked(apiClient.post).mockReset();
  vi.mocked(apiClient.patch).mockReset();
});

describe("QuestionBankView", () => {
  it("deletes a question after confirming in the dialog", async () => {
    vi.spyOn(window, "confirm").mockReturnValue(false);
    vi.mocked(apiClient.get).mockResolvedValue([q("a", "Tell me about a conflict."), q("b", "Why this company?")]);
    vi.mocked(apiClient.delete).mockResolvedValue(undefined);
    const user = userEvent.setup();
    renderWithProviders(<QuestionBankView />);

    await user.click(await screen.findByRole("button", { name: /Delete question: Tell me about a conflict/ }));
    await user.click(await screen.findByRole("button", { name: "Delete question" }));

    await waitFor(() => expect(apiClient.delete).toHaveBeenCalledWith("/interviews/question-bank/a"));
    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(screen.queryByText("Tell me about a conflict.")).not.toBeInTheDocument();
    expect(screen.getByText("Why this company?")).toBeInTheDocument();
    expect(await screen.findByText("Question deleted")).toBeInTheDocument();
  });

  it("keeps the question and shows why when the delete fails", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([q("a", "Tell me about a conflict.")]);
    vi.mocked(apiClient.delete).mockRejectedValue(new ApiError(403, "You are not allowed to do that."));
    const user = userEvent.setup();
    renderWithProviders(<QuestionBankView />);

    await user.click(await screen.findByRole("button", { name: /Delete question: Tell me/ }));
    await user.click(await screen.findByRole("button", { name: "Delete question" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("You are not allowed to do that.");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
  });

  it("requires a reference solution for coding questions", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([]);
    const user = userEvent.setup();
    renderWithProviders(<QuestionBankView />);
    await screen.findByText("No questions yet");

    await user.selectOptions(screen.getByLabelText("Question type"), "coding");
    await user.type(screen.getByLabelText("Question text"), "Reverse a linked list");
    await user.click(screen.getByRole("button", { name: "Add question" }));

    expect(await screen.findByRole("alert")).toHaveTextContent(/reference solution/i);
    expect(apiClient.post).not.toHaveBeenCalled();
  });

  it("adds a question and reloads the list", async () => {
    vi.mocked(apiClient.get).mockResolvedValueOnce([]).mockResolvedValueOnce([q("n", "Describe a failure.")]);
    vi.mocked(apiClient.post).mockResolvedValue(q("n", "Describe a failure."));
    const user = userEvent.setup();
    renderWithProviders(<QuestionBankView />);
    await screen.findByText("No questions yet");

    await user.selectOptions(screen.getByLabelText("Question type"), "behavioral");
    await user.type(screen.getByLabelText("Question text"), "Describe a failure.");
    await user.click(screen.getByRole("button", { name: "Add question" }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("1 question")).toBeInTheDocument();
    expect(await screen.findByText("Describe a failure.")).toBeInTheDocument();
  });
});
