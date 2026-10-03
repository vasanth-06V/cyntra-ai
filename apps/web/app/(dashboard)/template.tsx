/**
 * Re-mounts on every navigation inside the dashboard, which replays a short
 * fade-and-rise entrance. CSS only; the global reduced-motion rule covers it.
 */
export default function DashboardTemplate({ children }: { children: React.ReactNode }) {
  return <div className="animate-page-in print:animate-none">{children}</div>;
}
