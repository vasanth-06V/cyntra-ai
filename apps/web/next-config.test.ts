import { describe, expect, it } from "vitest";
import nextConfig from "./next.config";

describe("next.config security headers (M-1)", () => {
  it("applies the baseline headers to every route", async () => {
    const rules = await nextConfig.headers!();
    const all = rules.find((r) => r.source === "/:path*");
    expect(all).toBeDefined();
    const h = Object.fromEntries(all!.headers.map((x) => [x.key, x.value]));
    expect(h["X-Content-Type-Options"]).toBe("nosniff");
    expect(h["X-Frame-Options"]).toBe("DENY");
    expect(h["Referrer-Policy"]).toBe("strict-origin-when-cross-origin");
  });

  it("allows the microphone for this origin only and denies camera and geolocation", async () => {
    const rules = await nextConfig.headers!();
    const policy = rules[0].headers.find((x) => x.key === "Permissions-Policy")!.value;
    expect(policy).toContain("microphone=(self)");
    expect(policy).toContain("camera=()");
    expect(policy).toContain("geolocation=()");
  });

  it("keeps the CSP to framing, base, form and object restrictions (no script/style/connect rules)", async () => {
    const rules = await nextConfig.headers!();
    const csp = rules[0].headers.find((x) => x.key === "Content-Security-Policy")!.value;
    expect(csp).toContain("frame-ancestors 'none'");
    expect(csp).toContain("base-uri 'self'");
    expect(csp).toContain("form-action 'self'");
    expect(csp).toContain("object-src 'none'");
    expect(csp).not.toMatch(/script-src|style-src|connect-src|default-src/);
  });
});
