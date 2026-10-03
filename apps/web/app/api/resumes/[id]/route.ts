import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { deleteFromStorage } from "@/lib/storage";

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
    // Interviews that used this resume are kept (their link is cleared by the database).
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  // The row is gone; a storage hiccup shouldn't turn that into an error.
  await deleteFromStorage(resume.file_key).catch((err) => {
    console.error("Could not delete resume object from storage", err);
  });

  return new NextResponse(null, { status: 204 });
}
