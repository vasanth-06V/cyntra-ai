// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { mockFetch, renderWithProviders } from "@/test/utils";
import { ResumesView } from "./ResumesView";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

const resume = (n: number, parsed = true) => ({
  id: `r${n}`,
  file_key: `resumes/u1/file-${n}.pdf`,
  parsed_text: parsed ? "text" : null,
  created_at: "2026-01-02T10:00:00Z",
});

describe("ResumesView", () => {
  it("lists resumes with a usage count", async () => {
    mockFetch([{ match: "/api/resumes", json: [resume(1), resume(2)] }]);
    renderWithProviders(<ResumesView />);

    expect(await screen.findByText("file-1.pdf")).toBeInTheDocument();
    expect(screen.getByText("file-2.pdf")).toBeInTheDocument();
    expect(screen.getByText("2 of 3 used")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload resume" })).toBeEnabled();
  });

  it("deletes a resume through the in-app dialog even when window.confirm would answer 'no'", async () => {
    // The reported bug: window.confirm silently returned false in some browsers/webviews,
    // so nothing happened. The app must not depend on it any more.
    const nativeConfirm = vi.spyOn(window, "confirm").mockReturnValue(false);
    let stored = [resume(1), resume(2)];
    const { calls } = mockFetch([
      { match: "/api/resumes", json: () => stored },
      {
        method: "DELETE",
        match: "/api/resumes/r1",
        status: 204,
        onCall: () => (stored = stored.filter((r) => r.id !== "r1")),
      },
    ]);
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);

    await user.click(await screen.findByRole("button", { name: "Delete file-1.pdf" }));
    const dialog = await screen.findByRole("alertdialog", { name: "Delete this resume?" });
    expect(calls.some((c) => c.method === "DELETE")).toBe(false); // nothing yet
    await user.click(within(dialog).getByRole("button", { name: "Delete resume" }));

    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    const list = screen.getByRole("list", { name: "Your resumes" });
    await waitFor(() => expect(within(list).queryByText("file-1.pdf")).not.toBeInTheDocument());
    expect(within(list).getByText("file-2.pdf")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "DELETE").map((c) => c.url)).toEqual(["/api/resumes/r1"]);
    expect(nativeConfirm).not.toHaveBeenCalled();
    expect(await screen.findByText("Resume deleted")).toBeInTheDocument();
  });

  it("does nothing when the dialog is cancelled", async () => {
    const { calls } = mockFetch([{ match: "/api/resumes", json: [resume(1)] }]);
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);

    await user.click(await screen.findByRole("button", { name: "Delete file-1.pdf" }));
    await user.click(await screen.findByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(screen.getByText("file-1.pdf")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "DELETE")).toBe(false);
  });

  it("shows the server's error, keeps the row and the dialog when the delete fails", async () => {
    mockFetch([
      { match: "/api/resumes", json: [resume(1)] },
      { method: "DELETE", match: "/api/resumes/r1", status: 500, json: { error: "violates foreign key constraint" } },
    ]);
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);

    await user.click(await screen.findByRole("button", { name: "Delete file-1.pdf" }));
    await user.click(await screen.findByRole("button", { name: "Delete resume" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("violates foreign key constraint");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(within(screen.getByRole("list", { name: "Your resumes" })).getByText("file-1.pdf")).toBeInTheDocument();
  });

  it("disables upload and explains why once three resumes are stored", async () => {
    mockFetch([{ match: "/api/resumes", json: [resume(1), resume(2), resume(3)] }]);
    renderWithProviders(<ResumesView />);

    expect(await screen.findByText("3 of 3 used")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Upload resume" })).toBeDisabled();
    expect(screen.getByText(/Delete a resume to upload a new one/)).toBeInTheDocument();
  });

  it("rejects a file that is too large before sending anything", async () => {
    const { calls } = mockFetch([{ match: "/api/resumes", json: [resume(1)] }]);
    const user = userEvent.setup({ applyAccept: false });
    renderWithProviders(<ResumesView />);
    await screen.findByText("file-1.pdf");

    const big = new File([new Uint8Array(600 * 1024)], "big.pdf", { type: "application/pdf" });
    await user.upload(screen.getByLabelText("Choose a resume file"), big);

    expect(await screen.findByRole("alert")).toHaveTextContent("too large");
    expect(calls.some((c) => c.method === "POST")).toBe(false);
  });

  it("uploads a valid file and reloads the list", async () => {
    let listed = [resume(1)];
    const { calls, fn } = mockFetch([
      { match: "/api/resumes", json: [] },
      { method: "POST", match: "/api/resumes", json: { resume: resume(2), processingError: null } },
    ]);
    fn.mockImplementation(async (_input, init) => {
      const method = (init?.method ?? "GET").toUpperCase();
      calls.push({ url: "/api/resumes", method });
      if (method === "POST") listed = [resume(2), ...listed];
      return new Response(JSON.stringify(method === "POST" ? { resume: resume(2), processingError: null } : listed), {
        status: 200,
      });
    });
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);
    await screen.findByText("file-1.pdf");

    await user.upload(
      screen.getByLabelText("Choose a resume file"),
      new File(["%PDF-1.4"], "new.pdf", { type: "application/pdf" })
    );

    expect(await screen.findByText("file-2.pdf")).toBeInTheDocument();
    expect(calls.filter((c) => c.method === "POST")).toHaveLength(1);
    expect(screen.getByText("2 of 3 used")).toBeInTheDocument();
  });

  it("shows a retry button when the list cannot be loaded", async () => {
    mockFetch([{ match: "/api/resumes", status: 500, json: { error: "database is down" } }]);
    renderWithProviders(<ResumesView />);
    expect(await screen.findByRole("alert")).toHaveTextContent("database is down");

    mockFetch([{ match: "/api/resumes", json: [resume(1)] }]);
    await userEvent.setup().click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("file-1.pdf")).toBeInTheDocument();
  });
});

describe("ResumesView rename", () => {
  it("shows the display name instead of the file name, with the file name as a hint", async () => {
    mockFetch([{ match: "/api/resumes", json: [{ ...resume(1), display_name: "Backend CV" }] }]);
    renderWithProviders(<ResumesView />);
    expect(await screen.findByText("Backend CV")).toBeInTheDocument();
    expect(screen.getByText(/file-1\.pdf · Uploaded/)).toBeInTheDocument();
  });

  it("renames inline with Enter, sends the trimmed name and confirms with a toast", async () => {
    const { calls } = mockFetch([
      { match: "/api/resumes", json: [resume(1)] },
      { method: "PATCH", match: "/api/resumes/r1", json: { id: "r1", display_name: "Backend CV" } },
    ]);
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);

    await user.click(await screen.findByRole("button", { name: "Rename file-1.pdf" }));
    const input = screen.getByLabelText("New name for file-1.pdf");
    expect(input).toHaveFocus();
    await user.clear(input);
    await user.type(input, "  Backend CV  {Enter}");

    const list = screen.getByRole("list", { name: "Your resumes" });
    expect(await within(list).findByText("Backend CV")).toBeInTheDocument();
    expect(screen.queryByLabelText(/New name for/)).not.toBeInTheDocument();
    const patch = calls.find((c) => c.method === "PATCH")!;
    expect(JSON.parse(patch.body as string)).toEqual({ display_name: "Backend CV" });
    expect(await screen.findByText("Resume renamed")).toBeInTheDocument();
  });

  it("sends null when the name is emptied (back to the file name)", async () => {
    const { calls } = mockFetch([
      { match: "/api/resumes", json: [{ ...resume(1), display_name: "Backend CV" }] },
      { method: "PATCH", match: "/api/resumes/r1", json: { id: "r1", display_name: null } },
    ]);
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);

    await user.click(await screen.findByRole("button", { name: "Rename Backend CV" }));
    await user.clear(screen.getByLabelText("New name for Backend CV"));
    await user.click(screen.getByRole("button", { name: "Save name" }));

    expect(await screen.findByText("Name reset to the file name")).toBeInTheDocument();
    expect(JSON.parse(calls.find((c) => c.method === "PATCH")!.body as string)).toEqual({ display_name: null });
    expect(within(screen.getByRole("list", { name: "Your resumes" })).getByText("file-1.pdf")).toBeInTheDocument();
  });

  it("blocks a name over 80 characters with an inline message and no request", async () => {
    const { calls } = mockFetch([{ match: "/api/resumes", json: [resume(1)] }]);
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);

    await user.click(await screen.findByRole("button", { name: "Rename file-1.pdf" }));
    const input = screen.getByLabelText("New name for file-1.pdf");
    await user.clear(input);
    await user.type(input, "a".repeat(81));

    expect(screen.getByRole("alert")).toHaveTextContent("80 characters");
    expect(screen.getByRole("button", { name: "Save name" })).toBeDisabled();
    await user.keyboard("{Enter}");
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
  });

  it("cancels with Escape and with the Cancel button, changing nothing", async () => {
    const { calls } = mockFetch([{ match: "/api/resumes", json: [resume(1)] }]);
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);

    const rename = await screen.findByRole("button", { name: "Rename file-1.pdf" });
    await user.click(rename);
    await user.type(screen.getByLabelText("New name for file-1.pdf"), "zzz{Escape}");
    expect(screen.queryByLabelText(/New name for/)).not.toBeInTheDocument();
    await waitFor(() => expect(rename).toHaveFocus());

    await user.click(rename);
    await user.click(screen.getByRole("button", { name: "Cancel rename" }));
    expect(screen.queryByLabelText(/New name for/)).not.toBeInTheDocument();
    expect(screen.getByText("file-1.pdf")).toBeInTheDocument();
    expect(calls.some((c) => c.method === "PATCH")).toBe(false);
  });

  it("keeps the editor open and shows the error inline when saving fails", async () => {
    mockFetch([
      { match: "/api/resumes", json: [resume(1)] },
      { method: "PATCH", match: "/api/resumes/r1", status: 500, json: { error: "permission denied" } },
    ]);
    const user = userEvent.setup();
    renderWithProviders(<ResumesView />);

    await user.click(await screen.findByRole("button", { name: "Rename file-1.pdf" }));
    await user.type(screen.getByLabelText("New name for file-1.pdf"), "x{Enter}");

    expect(await screen.findByRole("alert")).toHaveTextContent("permission denied");
    expect(screen.getByLabelText("New name for file-1.pdf")).toBeInTheDocument();
    expect(screen.queryByText("Resume renamed")).not.toBeInTheDocument();
  });
});
