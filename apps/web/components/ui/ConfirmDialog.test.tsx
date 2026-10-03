// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ConfirmProvider, useConfirm } from "./ConfirmProvider";

function Harness({ onResult, onConfirm }: { onResult: (ok: boolean) => void; onConfirm?: () => Promise<void> }) {
  const confirm = useConfirm();
  return (
    <main id="main">
      <button
        onClick={async () =>
          onResult(
            await confirm({
              title: "Delete this thing?",
              description: "It cannot be undone.",
              confirmLabel: "Delete it",
              tone: "danger",
              onConfirm,
            })
          )
        }
      >
        Open
      </button>
      <button>Other</button>
    </main>
  );
}

function setup(onConfirm?: () => Promise<void>) {
  const onResult = vi.fn();
  render(
    <ConfirmProvider>
      <Harness onResult={onResult} onConfirm={onConfirm} />
    </ConfirmProvider>
  );
  return { onResult, user: userEvent.setup() };
}

describe("ConfirmDialog", () => {
  it("is an accessible alertdialog with a label and description, and focuses Cancel first", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Open" }));

    const dialog = await screen.findByRole("alertdialog", { name: "Delete this thing?" });
    expect(dialog).toHaveAttribute("aria-modal", "true");
    expect(dialog).toHaveAccessibleDescription("It cannot be undone.");
    expect(screen.getByRole("button", { name: "Cancel" })).toHaveFocus();
  });

  it("cancels with Escape and returns focus to the button that opened it", async () => {
    const { user, onResult } = setup();
    const opener = screen.getByRole("button", { name: "Open" });
    await user.click(opener);
    await screen.findByRole("alertdialog");

    await user.keyboard("{Escape}");

    await waitFor(() => expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument());
    expect(onResult).toHaveBeenCalledWith(false);
    await waitFor(() => expect(opener).toHaveFocus());
  });

  it("traps Tab and Shift+Tab inside the dialog", async () => {
    const { user } = setup();
    await user.click(screen.getByRole("button", { name: "Open" }));
    const cancel = await screen.findByRole("button", { name: "Cancel" });
    const confirm = screen.getByRole("button", { name: "Delete it" });

    expect(cancel).toHaveFocus();
    await user.tab();
    expect(confirm).toHaveFocus();
    await user.tab(); // wraps instead of escaping to the page behind
    expect(cancel).toHaveFocus();
    await user.tab({ shift: true });
    expect(confirm).toHaveFocus();
    expect(screen.getByRole("button", { name: "Other" })).not.toHaveFocus();
  });

  it("resolves true when confirmed", async () => {
    const { user, onResult } = setup();
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(await screen.findByRole("button", { name: "Delete it" }));
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
    expect(screen.queryByRole("alertdialog")).not.toBeInTheDocument();
  });

  it("shows a busy confirm button while the action runs and blocks Escape", async () => {
    let release!: () => void;
    const action = vi.fn(() => new Promise<void>((resolve) => (release = resolve)));
    const { user, onResult } = setup(action);
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(await screen.findByRole("button", { name: "Delete it" }));

    expect(screen.getByRole("button", { name: "Delete it" })).toHaveAttribute("aria-busy", "true");
    await user.keyboard("{Escape}");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();

    release();
    await waitFor(() => expect(onResult).toHaveBeenCalledWith(true));
    expect(action).toHaveBeenCalledTimes(1);
  });

  it("keeps the dialog open and shows the error when the action fails", async () => {
    const action = vi.fn().mockRejectedValue(new Error("Server said no."));
    const { user, onResult } = setup(action);
    await user.click(screen.getByRole("button", { name: "Open" }));
    await user.click(await screen.findByRole("button", { name: "Delete it" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Server said no.");
    expect(screen.getByRole("alertdialog")).toBeInTheDocument();
    expect(onResult).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Try again" })).toBeEnabled();
  });
});
