// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { TeamManager } from "./TeamManager";

vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

const user = (id: string, role: "owner" | "admin" | "user", name: string | null, perms: string[] = []) => ({
  id,
  email: `${id}@example.com`,
  full_name: name,
  role,
  permissions: perms,
  created_at: "2026-01-01T00:00:00Z",
});

const team = () => [
  user("o1", "owner", "Olivia Owner"),
  user("me", "admin", "Me Myself", ["manage_question_bank"]),
  user("a2", "admin", "Ada Admin", ["manage_question_bank"]),
  user("u1", "user", "Uma User"),
  user("u2", "user", null),
];

beforeEach(() => {
  vi.mocked(apiClient.get).mockReset().mockResolvedValue(team() as never);
  vi.mocked(apiClient.patch).mockReset();
  vi.mocked(apiClient.put).mockReset();
});

const row = (name: string) =>
  within(screen.getByRole("list", { name: "People on your team" })).getByText(name).closest("li") as HTMLElement;

describe("TeamManager", () => {
  it("shows a skeleton, then everyone with their role and no stub text", async () => {
    renderWithProviders(<TeamManager currentUserId="me" />);
    expect(screen.getByRole("status")).toHaveTextContent("Loading the team");

    expect(await screen.findByText("Olivia Owner")).toBeInTheDocument();
    expect(screen.getByText("Ada Admin")).toBeInTheDocument();
    expect(screen.getByText("u2@example.com")).toBeInTheDocument(); // no name: the email is the title
    expect(screen.getAllByText("Admin")).toHaveLength(2);
    expect(screen.getAllByText("User")).toHaveLength(2);
    expect(screen.getByText("Owner")).toBeInTheDocument();
    expect(screen.queryByText(/Not available yet/)).not.toBeInTheDocument();
    expect(screen.queryByRole("searchbox")).not.toBeInTheDocument(); // 8 users or fewer
  });

  it("makes the Owner row and your own row read-only", async () => {
    renderWithProviders(<TeamManager currentUserId="me" />);
    await screen.findByText("Olivia Owner");

    const owner = row("Olivia Owner");
    expect(within(owner).queryByRole("button")).not.toBeInTheDocument();
    expect(within(owner).queryByRole("checkbox")).not.toBeInTheDocument();
    expect(within(owner).getByText("Can't be changed")).toBeInTheDocument();

    const self = row("Me Myself");
    expect(within(self).getByText("(you)")).toBeInTheDocument();
    expect(within(self).queryByRole("button")).not.toBeInTheDocument();
    expect(within(self).queryByRole("checkbox")).not.toBeInTheDocument();
  });

  it("disables permissions for a plain user and explains how to enable them", async () => {
    renderWithProviders(<TeamManager currentUserId="me" />);
    await screen.findByText("Uma User");

    const plain = row("Uma User");
    expect(within(plain).getByRole("checkbox", { name: "Manage the question bank" })).toBeDisabled();
    expect(within(plain).getByText("Make them an Admin to grant permissions.")).toBeInTheDocument();
    // An admin's checkbox is live and reflects what was granted.
    expect(within(row("Ada Admin")).getByRole("checkbox", { name: /Manage the question bank/ })).toBeChecked();
  });

  it("promotes a user to Admin and enables the permissions", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ id: "u1", role: "admin" } as never);
    const u = userEvent.setup();
    renderWithProviders(<TeamManager currentUserId="me" />);
    await screen.findByText("Uma User");

    await u.click(screen.getByRole("button", { name: "Make Uma User an Admin" }));

    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledWith("/team/users/u1/role", { role: "admin" }));
    expect(await screen.findByRole("button", { name: "Make Uma User a User" })).toBeInTheDocument();
    expect(within(row("Uma User")).getByRole("checkbox", { name: /Manage the question bank/ })).toBeEnabled();
    expect(await screen.findByText("Made an Admin")).toBeInTheDocument();
  });

  it("demotes an admin only after confirming, and clears their permissions locally", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ id: "a2", role: "user" } as never);
    const u = userEvent.setup();
    renderWithProviders(<TeamManager currentUserId="me" />);
    await screen.findByText("Ada Admin");

    await u.click(screen.getByRole("button", { name: "Make Ada Admin a User" }));
    const dialog = await screen.findByRole("alertdialog");
    expect(apiClient.patch).not.toHaveBeenCalled();
    await u.click(within(dialog).getByRole("button", { name: "Make user" }));

    await waitFor(() => expect(apiClient.patch).toHaveBeenCalledWith("/team/users/a2/role", { role: "user" }));
    expect(await screen.findByRole("button", { name: "Make Ada Admin an Admin" })).toBeInTheDocument();
    const checkbox = within(row("Ada Admin")).getByRole("checkbox");
    expect(checkbox).toBeDisabled();
    expect(checkbox).not.toBeChecked();
  });

  it("does nothing when the demotion dialog is cancelled", async () => {
    const u = userEvent.setup();
    renderWithProviders(<TeamManager currentUserId="me" />);
    await screen.findByText("Ada Admin");
    await u.click(screen.getByRole("button", { name: "Make Ada Admin a User" }));
    await u.click(within(await screen.findByRole("alertdialog")).getByRole("button", { name: "Cancel" }));
    expect(apiClient.patch).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Make Ada Admin a User" })).toBeInTheDocument();
  });

  it("toggles a permission, sending the full list, and confirms", async () => {
    vi.mocked(apiClient.put).mockResolvedValue({ id: "a2", permissions: [] } as never);
    const u = userEvent.setup();
    renderWithProviders(<TeamManager currentUserId="me" />);
    await screen.findByText("Ada Admin");

    const box = within(row("Ada Admin")).getByRole("checkbox", { name: /Manage the question bank/ });
    await u.click(box);

    await waitFor(() => expect(apiClient.put).toHaveBeenCalledWith("/team/users/a2/permissions", { permissions: [] }));
    expect(box).not.toBeChecked();
    expect(await screen.findByText("Permission removed")).toBeInTheDocument();
  });

  it("rolls a permission change back and shows an error toast when the server refuses", async () => {
    vi.mocked(apiClient.put).mockRejectedValue(new ApiError(403, "Only the Owner can do that."));
    const u = userEvent.setup();
    renderWithProviders(<TeamManager currentUserId="me" />);
    await screen.findByText("Ada Admin");

    const box = within(row("Ada Admin")).getByRole("checkbox", { name: /Manage the question bank/ });
    await u.click(box);

    expect(await screen.findByText("Only the Owner can do that.")).toBeInTheDocument();
    await waitFor(() => expect(box).toBeChecked());
  });

  it("rolls a promotion back when the server refuses", async () => {
    vi.mocked(apiClient.patch).mockRejectedValue(new ApiError(409, "Cannot change this user."));
    const u = userEvent.setup();
    renderWithProviders(<TeamManager currentUserId="me" />);
    await screen.findByText("Uma User");

    await u.click(screen.getByRole("button", { name: "Make Uma User an Admin" }));

    expect(await screen.findByText("Cannot change this user.")).toBeInTheDocument();
    expect(await screen.findByRole("button", { name: "Make Uma User an Admin" })).toBeInTheDocument();
    expect(within(row("Uma User")).getByRole("checkbox")).toBeDisabled();
  });

  it("shows an error with a working retry", async () => {
    vi.mocked(apiClient.get).mockRejectedValueOnce(new ApiError(500, "team service down"));
    const u = userEvent.setup();
    renderWithProviders(<TeamManager currentUserId="me" />);
    expect(await screen.findByRole("alert")).toHaveTextContent("team service down");

    await u.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Olivia Owner")).toBeInTheDocument();
  });

  it("shows an empty state when nobody is listed", async () => {
    vi.mocked(apiClient.get).mockResolvedValue([] as never);
    renderWithProviders(<TeamManager currentUserId="me" />);
    expect(await screen.findByText("No users yet")).toBeInTheDocument();
  });

  it("offers a search box above eight users and filters by name, email and role", async () => {
    const many = [user("o1", "owner", "Olivia Owner"), ...Array.from({ length: 9 }, (_, i) => user(`x${i}`, "user", `Person ${i}`))];
    vi.mocked(apiClient.get).mockResolvedValue(many as never);
    const u = userEvent.setup();
    renderWithProviders(<TeamManager currentUserId="me" />);

    const search = await screen.findByRole("searchbox", { name: "Search people" });
    await u.type(search, "person 3");
    expect(screen.getByText("Person 3")).toBeInTheDocument();
    expect(screen.queryByText("Person 4")).not.toBeInTheDocument();
    expect(screen.getByText("1 of 10 people")).toBeInTheDocument();

    await u.clear(search);
    await u.type(search, "nobody-like-this");
    expect(screen.getByText("No one matches that search")).toBeInTheDocument();
  });
});
