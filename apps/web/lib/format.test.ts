import { describe, expect, it } from "vitest";
import { initials, relativeTime } from "./format";
import { MAX_CHAT_TITLE_LENGTH, validateChatTitle } from "./chat";

const NOW = new Date("2026-03-10T12:00:00Z").getTime();
const ago = (ms: number) => new Date(NOW - ms).toISOString();

describe("relativeTime", () => {
  it("reads naturally at each scale", () => {
    expect(relativeTime(ago(10_000), NOW)).toBe("just now");
    expect(relativeTime(ago(60_000), NOW)).toBe("1 minute ago");
    expect(relativeTime(ago(5 * 60_000), NOW)).toBe("5 minutes ago");
    expect(relativeTime(ago(3 * 3_600_000), NOW)).toBe("3 hours ago");
    expect(relativeTime(ago(30 * 3_600_000), NOW)).toBe("yesterday");
    expect(relativeTime(ago(4 * 86_400_000), NOW)).toBe("4 days ago");
  });
  it("falls back to a date after a week and to empty for garbage", () => {
    expect(relativeTime(ago(20 * 86_400_000), NOW)).toBe(new Date(ago(20 * 86_400_000)).toLocaleDateString());
    expect(relativeTime("nope", NOW)).toBe("");
  });
});

describe("initials", () => {
  it("uses first and last name, or the email name", () => {
    expect(initials("Ada Lovelace")).toBe("AL");
    expect(initials("Cher")).toBe("CH");
    expect(initials(null, "grace.hopper@example.com")).toBe("GH");
    expect(initials(null, null)).toBe("?");
  });
});

describe("validateChatTitle", () => {
  it("requires 1-120 characters after trimming", () => {
    expect(validateChatTitle("   ")).toMatch(/title/i);
    expect(validateChatTitle("Salary talk")).toBeNull();
    expect(validateChatTitle("a".repeat(MAX_CHAT_TITLE_LENGTH))).toBeNull();
    expect(validateChatTitle("a".repeat(MAX_CHAT_TITLE_LENGTH + 1))).toMatch(/120/);
  });
});
