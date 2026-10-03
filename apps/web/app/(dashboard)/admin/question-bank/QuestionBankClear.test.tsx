// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { apiClient } from "@/lib/api-client/fastapi";
import type { Question } from "@/types/interviews";
import { QuestionBankView } from "./QuestionBankView";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

const question: Question = {
  id: "a",
  type: "behavioral",
  question: "Tell me about a conflict.",
  solution_code: null,
  solution_language: null,
  test_cases: null,
  tags: null,
  difficulty: 3,
  topic: "conflict",
  created_by: null,
  created_at: "2026-01-01T00:00:00Z",
};

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset().mockResolvedValue([question]);
  vi.mocked(apiClient.patch).mockReset().mockResolvedValue(undefined as never);
  vi.mocked(apiClient.post).mockReset().mockResolvedValue(undefined as never);
});

describe("QuestionBankView: clearing topic and difficulty", () => {
  it("sends explicit nulls when an existing question's topic is emptied and difficulty is blanked", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QuestionBankView />);

    await user.click(await screen.findByRole("button", { name: /Edit question: Tell me about a conflict/ }));
    expect(screen.getByLabelText("Topic")).toHaveValue("conflict");
    expect(screen.getByLabelText("Difficulty")).toHaveValue("3");
    await user.clear(screen.getByLabelText("Topic"));
    await user.selectOptions(screen.getByLabelText("Difficulty"), "");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledTimes(1));
    const [path, body] = vi.mocked(apiClient.patch).mock.calls[0] as [string, Record<string, unknown>];
    expect(path).toBe("/interviews/question-bank/a");
    // `null` (not undefined) so JSON.stringify keeps the key and the API clears the column.
    expect(body.topic).toBeNull();
    expect(body.difficulty).toBeNull();
    expect(JSON.parse(JSON.stringify(body))).toMatchObject({ topic: null, difficulty: null });
  });

  it("still sends a changed topic and difficulty as values", async () => {
    const user = userEvent.setup();
    renderWithProviders(<QuestionBankView />);
    await user.click(await screen.findByRole("button", { name: /Edit question: Tell me about a conflict/ }));
    await user.clear(screen.getByLabelText("Topic"));
    await user.type(screen.getByLabelText("Topic"), "teamwork");
    await user.selectOptions(screen.getByLabelText("Difficulty"), "5");
    await user.click(screen.getByRole("button", { name: "Save changes" }));

    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledTimes(1));
    expect(vi.mocked(apiClient.patch).mock.calls[0][1]).toMatchObject({ topic: "teamwork", difficulty: 5 });
  });

  it("omits empty topic and difficulty when creating a question", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([]);
    const user = userEvent.setup();
    renderWithProviders(<QuestionBankView />);
    await screen.findByText("No questions yet");

    await user.selectOptions(screen.getByLabelText("Question type"), "behavioral");
    await user.type(screen.getByLabelText("Question text"), "Why this company?");
    await user.click(screen.getByRole("button", { name: "Add question" }));

    await waitFor(() => expect(apiClient.post).toHaveBeenCalledTimes(1));
    const body = vi.mocked(apiClient.post).mock.calls[0][1] as Record<string, unknown>;
    expect(JSON.parse(JSON.stringify(body))).not.toHaveProperty("topic");
    expect(JSON.parse(JSON.stringify(body))).not.toHaveProperty("difficulty");
  });
});
