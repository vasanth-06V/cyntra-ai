"use client";

import { useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { Card } from "@/components/ui/Card";
import { EmptyState } from "@/components/ui/EmptyState";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { FileIcon, UploadIcon } from "@/components/ui/icons";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import type { Resume } from "@/types/resumes";

function statusLabel(resume: Resume): { text: string; tone: Tone } {
  if (resume.parsed_text) {
    return { text: "Processed", tone: "success" };
  }
  return { text: "Processing failed or pending", tone: "danger" };
}

export function ResumesView() {
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // `loading` starts true, so the first load shows the spinner; later reloads
  // refresh the list in place instead of flashing it away.
  async function loadResumes() {
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

  // Initial load is written out inline: calling loadResumes() from an effect
  // makes React treat its state updates as synchronous in the effect body.
  useEffect(() => {
    fetch("/api/resumes")
      .then(async (res) => {
        const body = await res.json();
        if (!res.ok) throw new Error(body.error ?? "Could not load resumes.");
        setResumes(body);
      })
      .catch((err) =>
        setError(err instanceof Error ? err.message : "Could not load resumes.")
      )
      .finally(() => setLoading(false));
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
      const body = await res.json().catch(() => ({}));
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
    if (!window.confirm("Delete this resume? This cannot be undone.")) return;
    setError(null);
    const previous = resumes;
    setResumes((prev) => prev.filter((r) => r.id !== id));
    try {
      const res = await fetch(`/api/resumes/${id}`, { method: "DELETE" });
      if (!res.ok) {
        const body = await res.json().catch(() => ({}));
        throw new Error(body.error ?? "Could not delete this resume.");
      }
    } catch (err) {
      setResumes(previous);
      setError(err instanceof Error ? err.message : "Could not delete this resume.");
    }
  }

  async function handleRetry(id: string) {
    setError(null);
    setRetryingId(id);
    try {
      await apiClient.post(`/rag/resumes/${id}/process`);
      await loadResumes();
    } catch (err) {
      setError(
        err instanceof ApiError ? `Processing failed: ${err.message}` : "Processing failed."
      );
    } finally {
      setRetryingId(null);
    }
  }

  return (
    <div>
      <PageHeader
        title="Resumes"
        description="PDF or DOCX, up to 500KB. Used for interviews and ATS score checks."
        actions={
          <>
            <input
              ref={fileInputRef}
              type="file"
              accept=".pdf,.docx"
              onChange={handleFileChange}
              className="hidden"
              id="resume-upload"
            />
            <Button onClick={() => fileInputRef.current?.click()} loading={uploading}>
              {!uploading && <UploadIcon size={16} />}
              {uploading ? "Uploading…" : "Upload resume"}
            </Button>
          </>
        }
      />

      {error && (
        <Alert role="alert" className="mt-4">
          {error}
        </Alert>
      )}

      {loading ? (
        <ListSkeleton className="mt-6" rows={3} />
      ) : resumes.length === 0 ? (
        <EmptyState className="mt-6" icon={<FileIcon size={20} />} title="No resumes yet">
          No resumes yet -- upload one above.
        </EmptyState>
      ) : (
        <div className="mt-6 flex flex-col gap-2">
          <AnimatePresence initial={false}>
            {resumes.map((resume) => {
              const status = statusLabel(resume);
              return (
                <motion.div
                  key={resume.id}
                  layout="position"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, height: 0 }}
                  transition={{ duration: 0.24, ease: [0.22, 1, 0.36, 1] }}
                >
                  <Card className="flex flex-wrap items-center justify-between gap-3 p-4">
                    <div className="flex min-w-0 items-center gap-3.5">
                      <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl bg-accent text-accent-foreground">
                        <FileIcon size={18} />
                      </span>
                      <div className="min-w-0">
                        <p className="truncate text-sm font-medium">{resume.file_key.split("/").pop()}</p>
                        <Badge tone={status.tone} className="mt-1">
                          {status.text}
                        </Badge>
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      {!resume.parsed_text && (
                        <Button
                          type="button"
                          variant="secondary"
                          size="sm"
                          onClick={() => handleRetry(resume.id)}
                          loading={retryingId === resume.id}
                        >
                          {retryingId === resume.id ? "Processing…" : "Retry processing"}
                        </Button>
                      )}
                      <Button
                        type="button"
                        variant="ghost"
                        size="sm"
                        onClick={() => handleDelete(resume.id)}
                        className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                      >
                        Delete
                      </Button>
                    </div>
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
