import type { NextConfig } from "next";

// Conservative on purpose: no script-src / style-src / connect-src, because the
// editor (Monaco from a CDN), Supabase and the fonts cannot all be verified
// against a strict policy here. These directives only close framing and
// injection of <base>, <object> and foreign form targets.
const CONTENT_SECURITY_POLICY = "frame-ancestors 'none'; base-uri 'self'; form-action 'self'; object-src 'none'";

const securityHeaders = [
  { key: "X-Content-Type-Options", value: "nosniff" },
  { key: "X-Frame-Options", value: "DENY" },
  { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
  // Voice mode needs the microphone, for this origin only.
  { key: "Permissions-Policy", value: "microphone=(self), camera=(), geolocation=()" },
  { key: "Content-Security-Policy", value: CONTENT_SECURITY_POLICY },
];

const nextConfig: NextConfig = {
  async headers() {
    return [{ source: "/:path*", headers: securityHeaders }];
  },
};

export default nextConfig;
