// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";
import { act, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { ToastProvider, useToast } from "./Toast";

function Trigger({ onUndo }: { onUndo?: () => void }) {
  const { toast } = useToast();
  return (
    <>
      <button onClick={() => toast({ tone: "success", title: "Saved" })}>ok</button>
      <button onClick={() => toast({ tone: "error", title: "Broke", description: "Try later" })}>fail</button>
      <button onClick={() => toast({ title: "Removed", action: { label: "Undo", onClick: onUndo ?? (() => {}) } })}>
        undo
      </button>
    </>
  );
}

describe("Toast", () => {
  it("announces successes politely and errors assertively", async () => {
    const user = userEvent.setup();
    const { container } = render(
      <ToastProvider>
        <Trigger />
      </ToastProvider>
    );
    await user.click(screen.getByText("ok"));
    await user.click(screen.getByText("fail"));

    const polite = container.ownerDocument.querySelector('[aria-live="polite"]')!;
    const assertive = container.ownerDocument.querySelector('[aria-live="assertive"]')!;
    expect(polite).toHaveTextContent("Saved");
    expect(assertive).toHaveTextContent("Broke");
    expect(assertive).toHaveTextContent("Try later");
  });

  it("can be dismissed and runs an action", async () => {
    const onUndo = vi.fn();
    const user = userEvent.setup();
    render(
      <ToastProvider>
        <Trigger onUndo={onUndo} />
      </ToastProvider>
    );
    await user.click(screen.getByText("undo"));
    await user.click(screen.getByRole("button", { name: "Undo" }));
    expect(onUndo).toHaveBeenCalled();
    expect(screen.queryByText("Removed")).not.toBeInTheDocument();

    await user.click(screen.getByText("ok"));
    await user.click(screen.getByRole("button", { name: "Dismiss message" }));
    expect(screen.queryByText("Saved")).not.toBeInTheDocument();
  });

  it("goes away on its own", async () => {
    vi.useFakeTimers();
    try {
      render(
        <ToastProvider>
          <Trigger />
        </ToastProvider>
      );
      act(() => screen.getByText("ok").click());
      expect(screen.getByText("Saved")).toBeInTheDocument();
      act(() => {
        vi.advanceTimersByTime(5000);
      });
      expect(screen.queryByText("Saved")).not.toBeInTheDocument();
    } finally {
      vi.useRealTimers();
    }
  });
});
