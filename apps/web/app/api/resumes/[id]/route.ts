import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { deleteFromR2 } from "@/lib/storage";

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

  const { error } = await supabase
    .from("resumes")
    .delete()
    .eq("id", id)
    .eq("user_id", user.id);

  if (error) {
    // 23503 = foreign-key violation: an interview still references this resume.
    const message =
      error.code === "23503"
        ? "This resume is used by an interview and can't be deleted yet."
        : error.message;
    return NextResponse.json({ error: message }, { status: error.code === "23503" ? 409 : 500 });
  }

  // The row is gone; a storage hiccup shouldn't turn that into an error.
  await deleteFromR2(resume.file_key).catch((err) => {
    console.error("Could not delete resume object from storage", err);
  });

  return new NextResponse(null, { status: 204 });
}
