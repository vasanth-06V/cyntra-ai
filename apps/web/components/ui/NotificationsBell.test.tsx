// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from "vitest";
import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { renderWithProviders } from "@/test/utils";
import { NotificationsBell } from "./NotificationsBell";

type Row = { id: string; message: string; is_read: boolean; created_at: string };
let rows: Row[] = [];
let updateError: { message: string } | null = null;
const updates: { ids: string[] | "all" }[] = [];

// A tiny stand-in for the Supabase query builder used by the bell.
vi.mock("@/lib/supabase/client", () => ({
  createClient: () => ({
    from: () => ({
      select: () => ({
        order: () => ({ limit: async () => ({ data: rows, error: null }) }),
      }),
      update: () => ({
        eq: async () => {
          updates.push({ ids: "all" });
          if (!updateError) rows = rows.map((r) => ({ ...r, is_read: true }));
          return { error: updateError };
        },
        in: async (_col: string, ids: string[]) => {
          updates.push({ ids });
          if (!updateError) rows = rows.map((r) => (ids.includes(r.id) ? { ...r, is_read: true } : r));
          return { error: updateError };
        },
      }),
    }),
  }),
}));

const row = (id: string, message: string, is_read = false): Row => ({
  id,
  message,
  is_read,
  created_at: "2026-01-01T10:00:00Z",
});

beforeEach(() => {
  updates.length = 0;
  updateError = null;
  rows = [row("n1", "Your Gemini key hit its rate limit."), row("n2", "Switched to your backup Groq key.")];
});

describe("NotificationsBell", () => {
  it("shows the unread count and the notices when opened", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NotificationsBell />);
    const bell = await screen.findByRole("button", { name: "Notifications, 2 unread" });
    await user.click(bell);
    expect(screen.getByText("Your Gemini key hit its rate limit.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Notifications" })).toBeInTheDocument();
  });

  it("marks one notice read", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NotificationsBell />);
    await user.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));
    await user.click(screen.getByRole("button", { name: /Mark as read: Your Gemini key/ }));

    await waitFor(() => expect(updates).toEqual([{ ids: ["n1"] }]));
    expect(screen.getByRole("button", { name: "Notifications, 1 unread" })).toBeInTheDocument();
  });

  it("marks everything read", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NotificationsBell />);
    await user.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));
    await user.click(screen.getByRole("button", { name: "Mark all read" }));

    await waitFor(() => expect(screen.getByRole("button", { name: "Notifications" })).toBeInTheDocument());
    expect(updates).toEqual([{ ids: "all" }]);
  });

  it("puts the unread state back and says so when saving fails", async () => {
    updateError = { message: "permission denied" };
    const user = userEvent.setup();
    renderWithProviders(<NotificationsBell />);
    await user.click(await screen.findByRole("button", { name: "Notifications, 2 unread" }));
    await user.click(screen.getByRole("button", { name: "Mark all read" }));

    expect(await screen.findByText("Could not mark as read")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Notifications, 2 unread" })).toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the bell", async () => {
    const user = userEvent.setup();
    renderWithProviders(<NotificationsBell />);
    const bell = await screen.findByRole("button", { name: "Notifications, 2 unread" });
    await user.click(bell);
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("region", { name: "Notifications" })).not.toBeInTheDocument();
    expect(bell).toHaveFocus();
  });
});
