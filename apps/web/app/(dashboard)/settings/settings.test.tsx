// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { ApiError, apiClient } from "@/lib/api-client/fastapi";
import { AccountForm } from "./account/AccountForm";
import { DeleteAccountForm } from "./delete-account/DeleteAccountForm";
import { SettingsNav } from "./SettingsNav";

const push = vi.fn();
const refresh = vi.fn();
vi.mock("next/navigation", () => ({
  useRouter: () => ({ push, refresh }),
  usePathname: () => "/settings/account",
}));
vi.mock("@/lib/api-client/fastapi", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/lib/api-client/fastapi")>()),
  apiClient: { get: vi.fn(), post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn() },
}));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

beforeEach(() => {
  push.mockReset();
  refresh.mockReset();
  vi.mocked(apiClient.patch).mockReset();
  vi.unstubAllGlobals();
});

describe("SettingsNav", () => {
  it("lists the sections, with Team only for the Owner and Delete account last", () => {
    const { unmount } = renderWithProviders(<SettingsNav isOwner={false} />);
    const labels = () => screen.getAllByRole("link").map((l) => l.textContent);
    expect(labels()).toEqual(["Account", "Resumes", "API keys", "Security", "Delete account"]);
    expect(screen.getByRole("link", { name: "Account" })).toHaveAttribute("aria-current", "page");
    unmount();

    renderWithProviders(<SettingsNav isOwner />);
    expect(labels()).toEqual(["Account", "Resumes", "API keys", "Security", "Team", "Delete account"]);
  });
});

describe("AccountForm", () => {
  const form = () => <AccountForm email="a@x.com" initialName="Ada" role="user" memberSince={null} />;

  it("saves only a changed name, through the API", async () => {
    vi.mocked(apiClient.patch).mockResolvedValue({ full_name: "Ada Lovelace" } as never);
    renderWithProviders(form());
    const save = screen.getByRole("button", { name: "Save changes" });
    expect(save).toBeDisabled();

    await userEvent.clear(screen.getByLabelText("Full name"));
    await userEvent.type(screen.getByLabelText("Full name"), "Ada Lovelace");
    await userEvent.click(save);

    expect(apiClient.patch).toHaveBeenCalledWith("/account", { full_name: "Ada Lovelace" });
    await waitFor(() => expect(refresh).toHaveBeenCalled());
  });

  it("shows the server's message when saving fails", async () => {
    vi.mocked(apiClient.patch).mockRejectedValue(new ApiError(500, "Could not save"));
    renderWithProviders(form());
    await userEvent.type(screen.getByLabelText("Full name"), "x");
    await userEvent.click(screen.getByRole("button", { name: "Save changes" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Could not save");
  });

  it("will not save an empty name", async () => {
    renderWithProviders(form());
    await userEvent.clear(screen.getByLabelText("Full name"));
    expect(screen.getByRole("button", { name: "Save changes" })).toBeDisabled();
  });
});

describe("DeleteAccountForm", () => {
  const open = async () => {
    await userEvent.click(screen.getByRole("button", { name: "Delete my account" }));
    return screen.findByRole("alertdialog");
  };

  it("asks for confirmation on click; the final button works only after typing continue", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DeleteAccountForm isOwner={false} />);
    const dialog = await open();
    expect(fetchMock).not.toHaveBeenCalled(); // opening the dialog deletes nothing

    const confirmButton = within(dialog).getByRole("button", { name: "Delete my account" });
    expect(confirmButton).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/Type/), "contin");
    expect(confirmButton).toBeDisabled();
    await userEvent.type(within(dialog).getByLabelText(/Type/), "ue");
    expect(confirmButton).toBeEnabled();
    await userEvent.click(confirmButton);

    expect(fetchMock).toHaveBeenCalledWith("/api/account", expect.objectContaining({ method: "DELETE" }));
    await waitFor(() => expect(push).toHaveBeenCalledWith("/sign-in"));
  });

  it("cancelling deletes nothing", async () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);
    renderWithProviders(<DeleteAccountForm isOwner={false} />);
    const dialog = await open();
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("alertdialog")).toBeNull();
    expect(fetchMock).not.toHaveBeenCalled();
    expect(push).not.toHaveBeenCalled();
  });

  it("shows a refusal inside the dialog and stays on the page", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(new Response(JSON.stringify({ error: "Try again later" }), { status: 500 }))
    );
    renderWithProviders(<DeleteAccountForm isOwner={false} />);
    const dialog = await open();
    await userEvent.type(within(dialog).getByLabelText(/Type/), "continue");
    await userEvent.click(within(dialog).getByRole("button", { name: "Delete my account" }));
    expect(await within(dialog).findByRole("alert")).toHaveTextContent("Try again later");
    expect(push).not.toHaveBeenCalled();
  });

  it("offers no way to delete the Owner account", () => {
    renderWithProviders(<DeleteAccountForm isOwner />);
    expect(screen.queryByRole("button", { name: "Delete my account" })).toBeNull();
    expect(screen.getByText(/Owner account can't be deleted/)).toBeInTheDocument();
  });
});
