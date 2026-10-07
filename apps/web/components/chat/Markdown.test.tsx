// @vitest-environment jsdom
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Markdown } from "./Markdown";

describe("Markdown", () => {
  it("renders headings, bold text, lists and rules instead of showing the markers", () => {
    const { container } = render(
      <Markdown>{"### 1. Learning\n* **Brainstorming:** ideas\n* Language\n\n---\n\nDone"}</Markdown>
    );
    expect(screen.getByRole("heading", { name: "1. Learning" })).toBeInTheDocument();
    expect(container.querySelectorAll("li")).toHaveLength(2);
    expect(container.querySelector("strong")?.textContent).toBe("Brainstorming:");
    expect(container.querySelector("hr")).not.toBeNull();
    expect(container.textContent).not.toContain("###");
    expect(container.textContent).not.toContain("**");
  });

  it("renders code blocks and tables", () => {
    const { container } = render(<Markdown>{"```py\nprint(1)\n```\n\n| a | b |\n|---|---|\n| 1 | 2 |"}</Markdown>);
    expect(container.querySelector("pre code")?.textContent).toContain("print(1)");
    expect(container.querySelectorAll("td")).toHaveLength(2);
  });

  it("does not render raw HTML or script-style links", () => {
    const { container } = render(<Markdown>{"<img src=x onerror=alert(1)>\n\n[click](javascript:alert(1))"}</Markdown>);
    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("a")?.getAttribute("href") ?? "").not.toContain("javascript:");
  });
});
