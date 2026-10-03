import { randomUUID } from "crypto";
import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import { deleteFromStorage, uploadToStorage } from "@/lib/storage";
import { MAX_RESUMES } from "@/lib/resumes";

const ALLOWED_EXTENSIONS = ["pdf", "docx"];
// Sent explicitly (not the browser's guess) so it always matches the bucket's
// allowed MIME types in Supabase Storage.
const CONTENT_TYPES: Record<string, string> = {
  pdf: "application/pdf",
  docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
};
// Resumes are small text documents (typically ~200 KB). Keep this equal to
// _MAX_FILE_BYTES in api/app/rag/service.py and the UI hint in ResumesView.
const MAX_FILE_SIZE_BYTES = 500 * 1024; // 500KB

export async function POST(request: Request) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    return NextResponse.json({ error: "Not signed in" }, { status: 401 });
  }

  // Each account keeps at most MAX_RESUMES resumes: checked before any bytes
  // are stored, so a refused upload leaves nothing behind.
  const { count, error: countError } = await supabase
    .from("resumes")
    .select("id", { count: "exact", head: true })
    .eq("user_id", user.id);
  if (countError) {
    return NextResponse.json({ error: countError.message }, { status: 500 });
  }
  if ((count ?? 0) >= MAX_RESUMES) {
    return NextResponse.json(
      {
        error: `You can keep up to ${MAX_RESUMES} resumes. Delete one to upload another.`,
        code: "resume_limit",
      },
      { status: 409 }
    );
  }

  let formData: FormData;
  try {
    formData = await request.formData();
  } catch {
    return NextResponse.json({ error: "Could not read the upload" }, { status: 400 });
  }
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
    return NextResponse.json({ error: "File is too large (max 500KB)" }, { status: 400 });
  }

  const resumeId = randomUUID();
  const fileKey = `resumes/${user.id}/${resumeId}.${extension}`;
  const buffer = Buffer.from(await file.arrayBuffer());

  // The extension is user-controlled; check the file's own signature too.
  const signature = buffer.subarray(0, 4).toString("latin1");
  const looksRight = extension === "pdf" ? signature === "%PDF" : signature.startsWith("PK");
  if (!looksRight) {
    return NextResponse.json(
      { error: "That file doesn't look like a valid PDF or DOCX" },
      { status: 400 }
    );
  }

  try {
    await uploadToStorage(fileKey, buffer, CONTENT_TYPES[extension]);
  } catch {
    return NextResponse.json(
      { error: "Could not store the file right now -- please try again." },
      { status: 502 }
    );
  }

  const { data: resume, error: insertError } = await supabase
    .from("resumes")
    .insert({ id: resumeId, user_id: user.id, file_key: fileKey })
    .select()
    .single();

  if (insertError) {
    // Don't leave an orphaned object behind.
    await deleteFromStorage(fileKey).catch(() => {});
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
