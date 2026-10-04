import { afterEach, describe, expect, it, vi } from "vitest";
import { demoSignUpEnabled } from "./demo-signup";

afterEach(() => vi.unstubAllEnvs());

describe("demoSignUpEnabled (M-2)", () => {
  it("is on in development and test builds", () => {
    vi.stubEnv("NODE_ENV", "development");
    expect(demoSignUpEnabled()).toBe(true);
    vi.stubEnv("NODE_ENV", "test");
    expect(demoSignUpEnabled()).toBe(true);
  });

  it("is off in production by default", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_ENABLE_DEMO_SIGNUP", "");
    expect(demoSignUpEnabled()).toBe(false);
  });

  it("is only switched on in production by the exact value 'true'", () => {
    vi.stubEnv("NODE_ENV", "production");
    vi.stubEnv("NEXT_PUBLIC_ENABLE_DEMO_SIGNUP", "1");
    expect(demoSignUpEnabled()).toBe(false);
    vi.stubEnv("NEXT_PUBLIC_ENABLE_DEMO_SIGNUP", "true");
    expect(demoSignUpEnabled()).toBe(true);
  });
});
