// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { AccountSetupForm } from "./AccountSetupForm";

const nav = vi.hoisted(() => ({ push: vi.fn(), refresh: vi.fn() }));
const supa = vi.hoisted(() => ({
  updateUser: vi.fn(),
  insert: vi.fn(),
}));
vi.mock("next/navigation", () => ({ useRouter: () => nav }));
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    auth: { updateUser: supa.updateUser, getUser: async () => ({ data: { user: { id: "u1" } } }) },
    from: () => ({ insert: supa.insert }),
  }),
}));

const PASSWORD = "Str0ng!pass";

async function submit() {
  const user = userEvent.setup();
  renderWithProviders(<AccountSetupForm email="a@b.co" fullName="Ada" />);
  await user.type(screen.getByLabelText("New password"), PASSWORD);
  await user.type(screen.getByLabelText("Confirm password"), PASSWORD);
  return user;
}

beforeEach(() => {
  nav.push.mockReset();
  nav.refresh.mockReset();
  supa.updateUser.mockReset().mockResolvedValue({ error: null });
  supa.insert.mockReset().mockResolvedValue({ error: null });
});

describe("AccountSetupForm", () => {
  it("sets the password, creates the profile and moves on to onboarding", async () => {
    const user = await submit();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/onboarding"));
    expect(supa.updateUser).toHaveBeenCalledWith({ password: PASSWORD });
    expect(supa.insert).toHaveBeenCalledWith({ id: "u1", full_name: "Ada" });
  });

  it("M-13: a retry after the profile insert failed does not set the same password again", async () => {
    supa.insert.mockResolvedValueOnce({ error: { message: "network blip" } });
    const user = await submit();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("network blip");
    expect(nav.push).not.toHaveBeenCalled();

    // Supabase would reject an unchanged password; the retry must not even ask.
    supa.updateUser.mockResolvedValue({ error: { message: "New password should be different", code: "same_password" } });
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/onboarding"));
    expect(supa.updateUser).toHaveBeenCalledTimes(1);
    expect(supa.insert).toHaveBeenCalledTimes(2);
  });

  it("treats a same_password rejection as success", async () => {
    supa.updateUser.mockResolvedValue({ error: { message: "same", code: "same_password" } });
    const user = await submit();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/onboarding"));
  });

  it("still shows other password errors and stops", async () => {
    supa.updateUser.mockResolvedValue({ error: { message: "Password is too weak", code: "weak_password" } });
    const user = await submit();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Password is too weak");
    expect(supa.insert).not.toHaveBeenCalled();
  });

  it("carries on when the profile already exists (duplicate key)", async () => {
    supa.insert.mockResolvedValue({ error: { message: "duplicate key", code: "23505" } });
    const user = await submit();
    await user.click(screen.getByRole("button", { name: "Continue" }));
    await waitFor(() => expect(nav.push).toHaveBeenCalledWith("/onboarding"));
  });
});
