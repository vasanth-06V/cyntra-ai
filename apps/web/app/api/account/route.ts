import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { deleteFromStorage } from "@/lib/storage";

const API_TIMEOUT_MS = 30_000;
/** Storage clean-up must never hold the response hostage. */
const STORAGE_DELETE_TIMEOUT_MS = 10_000;

/**
 * Permanently deletes the signed-in user's account. The API removes the
 * sign-in account (the database cascades to everything the user owns); only
 * then are the resume files removed from storage, so a refusal (the Owner
 * can't be deleted) leaves every file in place.
 */
export async function DELETE(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  let confirm: unknown;
  try {
    confirm = ((await request.json()) as { confirm?: unknown } | null)?.confirm;
  } catch {
    confirm = undefined;
  }
  if (confirm !== "DELETE") {
    return NextResponse.json({ error: "Type DELETE to confirm." }, { status: 400 });
  }

  // Read the file keys first: they disappear with the account.
  const { data: resumes, error: resumesError } = await supabase
    .from("resumes")
    .select("file_key")
    .eq("user_id", user.id);
  if (resumesError) {
    return NextResponse.json({ error: "Could not prepare the deletion. Please try again." }, { status: 500 });
  }

  const {
    data: { session },
  } = await supabase.auth.getSession();

  let res: Response;
  try {
    res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/account/delete`, {
      method: "POST",
      headers: { Authorization: `Bearer ${session?.access_token}`, "Content-Type": "application/json" },
      body: JSON.stringify({ confirm: "DELETE" }),
      signal: AbortSignal.timeout(API_TIMEOUT_MS),
    });
  } catch {
    return NextResponse.json({ error: "Could not reach the server. Please try again." }, { status: 502 });
  }
  if (!res.ok) {
    const body = (await res.json().catch(() => null)) as {
      error?: { message?: string };
      detail?: unknown;
    } | null;
    const message =
      body?.error?.message ?? (typeof body?.detail === "string" ? body.detail : "Could not delete the account.");
    return NextResponse.json({ error: message }, { status: res.status });
  }

  // The account is gone. Clean up the files without making the user wait on a slow store.
  await Promise.race([
    Promise.allSettled((resumes ?? []).map((r) => deleteFromStorage(r.file_key))).then((results) => {
      for (const r of results) {
        if (r.status === "rejected") console.error("Could not delete a resume object from storage", r.reason);
      }
    }),
    new Promise<void>((resolve) => setTimeout(resolve, STORAGE_DELETE_TIMEOUT_MS)),
  ]);

  // Clears the session cookies; the server-side session is already invalid.
  await supabase.auth.signOut().catch(() => undefined);

  return new NextResponse(null, { status: 204 });
}
