"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import type { Resume } from "@/types/resumes";

function statusLabel(resume: Resume): { text: string; className: string } {
  if (resume.parsed_text) {
    return { text: "Processed", className: "text-green-600 dark:text-green-400" };
  }
  return { text: "Processing failed or pending", className: "text-destructive" };
}

export function ResumesView() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  async function loadResumes() {
    setLoading(true);
    try {
      const res = await fetch("/api/resumes");
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? "Could not load resumes.");
      setResumes(body);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Could not load resumes.");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    loadResumes();
  }, []);

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;

    setUploading(true);
    setError(null);

    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/resumes", { method: "POST", body: formData });
      const body = await res.json();
      if (!res.ok) throw new Error(body.error ?? "Upload failed.");
      if (body.processingError) {
        setError(`Uploaded, but processing failed: ${body.processingError}`);
      }
      await loadResumes();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Upload failed.");
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = "";
    }
  }

  async function handleDelete(id: string) {
    setResumes((prev) => prev.filter((r) => r.id !== id));
    await fetch(`/api/resumes/${id}`, { method: "DELETE" }).catch(() => {
      loadResumes();
    });
  }

  return (
    <div>
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">Resumes</h1>
        <div>
          <input
            ref={fileInputRef}
            type="file"
            accept=".pdf,.docx"
            onChange={handleFileChange}
            className="hidden"
            id="resume-upload"
          />
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
          >
            {uploading ? "Uploading…" : "Upload resume"}
          </Button>
        </div>
      </div>
      <p className="mt-1 text-sm text-muted-foreground">
        PDF or DOCX, up to 5MB. Used for interviews and ATS score checks.
      </p>

      {error && <p className="mt-4 text-sm text-destructive">{error}</p>}

      {loading ? (
        <p className="mt-6 text-sm text-muted-foreground">Loading…</p>
      ) : resumes.length === 0 ? (
        <div className="mt-6 rounded-xl border border-dashed border-border p-8 text-center text-sm text-muted-foreground">
          No resumes yet -- upload one above.
        </div>
      ) : (
        <div className="mt-6 flex flex-col gap-2">
          <AnimatePresence initial={false}>
            {resumes.map((resume) => {
              const status = statusLabel(resume);
              return (
                <motion.div
                  key={resume.id}
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0 }}
                >
                  <Card className="flex items-center justify-between p-4">
                    <div>
                      <p className="text-sm font-medium">
                        {resume.file_key.split("/").pop()}
                      </p>
                      <p className={`text-xs ${status.className}`}>{status.text}</p>
                    </div>
                    <button
                      type="button"
                      onClick={() => handleDelete(resume.id)}
                      className="text-sm text-muted-foreground hover:text-destructive cursor-pointer"
                    >
                      Delete
                    </button>
                  </Card>
                </motion.div>
              );
            })}
          </AnimatePresence>
        </div>
      )}
    </div>
  );
}
