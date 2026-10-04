/**
 * The temporary email/password demo sign-up is on in development and OFF in
 * production builds, unless NEXT_PUBLIC_ENABLE_DEMO_SIGNUP=true was set at
 * build time (NEXT_PUBLIC_ values are inlined into the bundle by `next build`).
 */
export function demoSignUpEnabled(): boolean {
  return process.env.NODE_ENV !== "production" || process.env.NEXT_PUBLIC_ENABLE_DEMO_SIGNUP === "true";
}
