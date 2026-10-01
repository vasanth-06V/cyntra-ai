import { randomUUID } from "crypto";
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { uploadToR2 } from "@/lib/storage";

const ALLOWED_EXTENSIONS = ["pdf", "docx"];
const MAX_FILE_SIZE_BYTES = 5 * 1024 * 1024; // 5MB

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const formData = await request.formData();
  const file = formData.get("file");

  if (!(file instanceof File)) {
    return NextResponse.json({ error: "No file provided" }, { status: 400 });
  }

  const extension = file.name.split(".").pop()?.toLowerCase();
  if (!extension || !ALLOWED_EXTENSIONS.includes(extension)) {
    return NextResponse.json(
      { error: "Only PDF and DOCX files are supported" },
      { status: 400 }
    );
  }

  if (file.size > MAX_FILE_SIZE_BYTES) {
    return NextResponse.json({ error: "File is too large (max 5MB)" }, { status: 400 });
  }

  const resumeId = randomUUID();
  const fileKey = `resumes/${user.id}/${resumeId}.${extension}`;
  const buffer = Buffer.from(await file.arrayBuffer());

  await uploadToR2(fileKey, buffer, file.type || "application/octet-stream");

  const { data: resume, error: insertError } = await supabase
    .from("resumes")
    .insert({ id: resumeId, user_id: user.id, file_key: fileKey })
    .select()
    .single();

  if (insertError) {
    return NextResponse.json({ error: insertError.message }, { status: 500 });
  }

  // Trigger RAG processing (parse/chunk/embed) -- failure here doesn't fail
  // the upload itself, since the file is already safely stored; the resume
  // just stays unprocessed until the user retries.
  const {
    data: { session },
  } = await supabase.auth.getSession();

  let processingError: string | null = null;
  try {
    const res = await fetch(
      `${process.env.NEXT_PUBLIC_API_URL}/rag/resumes/${resumeId}/process`,
      {
        method: "POST",
        headers: { Authorization: `Bearer ${session?.access_token}` },
      }
    );
    if (!res.ok) {
      const body = await res.json().catch(() => ({ detail: res.statusText }));
      processingError = body.detail ?? res.statusText;
    }
  } catch {
    processingError = "Could not reach the processing service";
  }

  return NextResponse.json({ resume, processingError });
}

export async function GET() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  const { data, error } = await supabase
    .from("resumes")
    .select("id, file_key, parsed_text, created_at")
    .eq("user_id", user.id)
    .order("created_at", { ascending: false });

  if (error) {
    return NextResponse.json({ error: error.message }, { status: 500 });
  }

  return NextResponse.json(data);
}
