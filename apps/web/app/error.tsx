"use client";

import { useEffect } from "react";
import Link from "next/link";
import { Alert } from "@/components/ui/Alert";
import { Button } from "@/components/ui/Button";
import { LinkButton } from "@/components/ui/LinkButton";
import { Logo } from "@/components/ui/Logo";
import { RefreshIcon } from "@/components/ui/icons";

/**
 * Error boundary for every route below the root layout. In this Next.js
 * version the retry prop is `retry` (re-fetches and re-renders the segment).
 */
export default function AppError({
  error,
  retry,
}: {
  error: Error & { digest?: string };
  retry: () => void;
}) {
  useEffect(() => {
    // Server errors arrive with a generic message and a digest that matches the server log.
    console.error(error);
  }, [error]);

  return (
    <main id="main" className="brand-wash flex min-h-screen flex-col items-center justify-center gap-6 px-4 py-12">
      <Link href="/" aria-label="CyntraAI home">
        <Logo size={28} />
      </Link>
      <div className="flex w-full max-w-md flex-col items-start gap-4 rounded-2xl border border-border bg-card p-6 shadow-md">
        <h1 className="text-xl font-semibold tracking-tight">Something went wrong</h1>
        <Alert role="alert" className="w-full">
          We couldn&apos;t load this page. This is usually temporary; trying again often fixes it.
          {error.digest ? <span className="mt-1 block text-xs opacity-80">Reference: {error.digest}</span> : null}
        </Alert>
        <div className="flex flex-wrap gap-2">
          <Button type="button" onClick={() => retry()}>
            <RefreshIcon size={14} />
            Try again
          </Button>
          <LinkButton href="/" variant="outline">
            Go to the home page
          </LinkButton>
        </div>
      </div>
    </main>
  );
}
