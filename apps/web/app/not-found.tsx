import Link from "next/link";
import { LinkButton } from "@/components/ui/LinkButton";
import { Logo } from "@/components/ui/Logo";

export const metadata = { title: "Page not found" };

export default function NotFound() {
  return (
    <main id="main" className="brand-wash flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-12 text-center">
      <Link href="/" aria-label="CyntraAI home">
        <Logo size={28} />
      </Link>
      <div className="flex max-w-md flex-col items-center gap-3">
        <p className="text-sm font-medium text-muted-foreground">404</p>
        <h1 className="text-3xl font-semibold tracking-[-0.03em]">We can&apos;t find that page</h1>
        <p className="text-sm text-muted-foreground">
          The link may be old or mistyped. Head back and pick up where you left off.
        </p>
        <LinkButton href="/" className="mt-2">
          Go to the home page
        </LinkButton>
      </div>
    </main>
  );
}
