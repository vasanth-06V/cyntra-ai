import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { deleteFromStorage } from "@/lib/storage";

/** Storage clean-up must never hold the response hostage (a dead storage endpoint can hang for a long time). */
const STORAGE_DELETE_TIMEOUT_MS = 8000;

export async function DELETE(
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const { data: resume } = await supabase
    .from("resumes")
    .select("file_key")
    .eq("id", id)
    .eq("user_id", user.id)
    .maybeSingle();

  if (!resume) {
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  }

  // Ask for the deleted rows back: a delete that matched nothing (for example
  // a policy hiding the row) must not be reported as a success.
  const { data: deleted, error } = await supabase
    .from("resumes")
    .delete()
    .eq("id", id)
    .eq("user_id", user.id)
    .select("id");

  if (error) {
    // Interviews that used this resume are kept (their link is cleared by the database).
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  if (!deleted || deleted.length === 0) {
    return NextResponse.json(
      { error: "The resume could not be deleted. Please refresh and try again." },
      { status: 409 }
    );
  }

  // The row is gone; a storage hiccup shouldn't turn that into an error, and
  // it shouldn't make the user wait either.
  await Promise.race([
    deleteFromStorage(resume.file_key).catch((err) => {
      console.error("Could not delete resume object from storage", err);
    }),
    new Promise<void>((resolve) => setTimeout(resolve, STORAGE_DELETE_TIMEOUT_MS)),
  ]);

  return new NextResponse(null, { status: 204 });
}

const MAX_DISPLAY_NAME_LENGTH = 80;

/**
 * Renames a resume. The owner may update only `display_name` straight through
 * Supabase (column grant), so this handler stays within that: trimmed text,
 * 1-80 characters, or null (an empty string clears the name).
 */
export async function PATCH(
  request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params;
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  let body: unknown;
  try {
    body = await request.json();
  } catch {
    return NextResponse.json({ error: "Could not read the request" }, { status: 400 });
  }
  const raw = (body as { display_name?: unknown } | null)?.display_name;
  if (raw !== null && typeof raw !== "string") {
    return NextResponse.json({ error: "display_name must be text or null" }, { status: 400 });
  }
  const trimmed = raw === null ? "" : raw.trim();
  if (trimmed.length > MAX_DISPLAY_NAME_LENGTH) {
    return NextResponse.json(
      { error: `The name can be at most ${MAX_DISPLAY_NAME_LENGTH} characters.` },
      { status: 400 }
    );
  }
  const displayName = trimmed === "" ? null : trimmed;

  const { data, error } = await supabase
    .from("resumes")
    .update({ display_name: displayName })
    .eq("id", id)
    .eq("user_id", user.id)
    .select("id, display_name");

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }
  if (!data || data.length === 0) {
    return NextResponse.json({ error: "Resume not found" }, { status: 404 });
  }
  return NextResponse.json(data[0]);
}
