"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Alert } from "@/components/ui/Alert";
import { Badge, type Tone } from "@/components/ui/Badge";
import { Button } from "@/components/ui/Button";
import { useConfirm } from "@/components/ui/ConfirmProvider";
import { EmptyState } from "@/components/ui/EmptyState";
import { InlineRename } from "@/components/ui/InlineRename";
import { ListRow } from "@/components/ui/ListRow";
import { PageHeader } from "@/components/ui/PageHeader";
import { ListSkeleton } from "@/components/ui/Skeleton";
import { useToast } from "@/components/ui/Toast";
import { FileIcon, PencilIcon, RefreshIcon, TrashIcon, UploadIcon } from "@/components/ui/icons";
import { apiClient, ApiError } from "@/lib/api-client/fastapi";
import {
  MAX_RESUMES,
  MAX_RESUME_NAME_LENGTH,
  fetchResumes,
  resumeName,
  validateResumeFile,
  validateResumeName,
} from "@/lib/resumes";
import type { Resume } from "@/types/resumes";

function statusLabel(resume: Resume): { text: string; tone: Tone } {
  if (resume.parsed_text) {
    return { text: "Processed", tone: "success" };
  }
  return { text: "Not processed yet", tone: "warning" };
}

export function ResumesView() {
  const confirm = useConfirm();
  const { toast } = useToast();
  const [resumes, setResumes] = useState<Resume[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [uploading, setUploading] = useState(false);
  const [retryingId, setRetryingId] = useState<string | null>(null);
  const [renamingId, setRenamingId] = useState<string | null>(null);
  const renameOpener = useRef<HTMLButtonElement | null>(null);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Reloads the list in place (no spinner flash). Used after every mutation
  // so the page always reflects the server, not just local guesses.
  const reload = useCallback(async () => {
    try {
      setResumes(await fetchResumes());
      setLoadError(null);
    } catch (err) {
      setLoadError(err instanceof Error ? err.message : "Could not load resumes.");
    } finally {
      setLoading(false);
    }
  }, []);

  // Initial load is written out inline: calling reload() from an effect
  // makes React treat its state updates as synchronous in the effect body.
  useEffect(() => {
    fetchResumes()
      .then(setResumes)
      .catch((err) => setLoadError(err instanceof Error ? err.message : "Could not load resumes."))
      .finally(() => setLoading(false));
  }, []);

  function retryLoad() {
    setLoading(true);
    void reload();
  }

  const used = resumes.length;
  const atLimit = used >= MAX_RESUMES;

  async function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    const input = e.target;
    setUploadError(null);

    const problem = validateResumeFile(file);
    if (problem) {
      setUploadError(problem);
      input.value = "";
      return;
    }

    setUploading(true);
    const formData = new FormData();
    formData.append("file", file);

    try {
      const res = await fetch("/api/resumes", { method: "POST", body: formData });
      const body = await res.json().catch(() => ({}));
      if (!res.ok) throw new Error(body.error ?? "Upload failed.");
      if (body.processingError) {
        toast({
          tone: "error",
          title: "Uploaded, but processing failed",
          description: `${body.processingError}. Use "Retry processing" on the resume below.`,
          duration: 0,
        });
      } else {
        toast({ tone: "success", title: "Resume uploaded and processed" });
      }
      await reload();
    } catch (err) {
      setUploadError(err instanceof Error ? err.message : "Upload failed.");
      await reload();
    } finally {
      setUploading(false);
      input.value = "";
    }
  }

  async function deleteResume(id: string) {
    let res: Response;
    try {
      res = await fetch(`/api/resumes/${id}`, { method: "DELETE" });
    } catch {
      throw new Error("Could not reach the server. Check your connection and try again.");
    }
    if (!res.ok) {
      const body = await res.json().catch(() => ({}));
      throw new Error(body.error ?? `Could not delete this resume (error ${res.status}).`);
    }
    setResumes((prev) => prev.filter((r) => r.id !== id));
  }

  async function handleDelete(resume: Resume) {
    const name = resumeName(resume);
    const ok = await confirm({
      title: "Delete this resume?",
      description: (
        <>
          <span className="font-medium text-foreground">{name}</span> and its extracted text will be removed for
          good. Interviews that used it are kept.
        </>
      ),
      confirmLabel: "Delete resume",
      tone: "danger",
      onConfirm: () => deleteResume(resume.id),
    });
    if (ok) {
      toast({ tone: "success", title: "Resume deleted", description: name });
      void reload();
    }
  }

  async function renameResume(resume: Resume, value: string) {
    let res: Response;
    try {
      res = await fetch(`/api/resumes/${resume.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ display_name: value.trim() === "" ? null : value.trim() }),
      });
    } catch {
      throw new Error("Could not reach the server. Check your connection and try again.");
    }
    const body = await res.json().catch(() => ({}));
    if (!res.ok) throw new Error(body.error ?? `Could not rename this resume (error ${res.status}).`);
    const saved = (body as { display_name?: string | null }).display_name ?? null;
    setResumes((prev) => prev.map((r) => (r.id === resume.id ? { ...r, display_name: saved } : r)));
    toast({ tone: "success", title: saved ? "Resume renamed" : "Name reset to the file name", description: saved ?? undefined });
  }

  function closeRename(saved: boolean) {
    void saved;
    setRenamingId(null);
    // Put focus back on the Rename button that opened the editor.
    setTimeout(() => renameOpener.current?.focus(), 0);
  }

  async function handleRetry(id: string) {
    setRetryingId(id);
    try {
      await apiClient.post(`/rag/resumes/${id}/process`);
      toast({ tone: "success", title: "Resume processed" });
      await reload();
    } catch (err) {
      toast({
        tone: "error",
        title: "Processing failed",
        description: err instanceof ApiError ? err.message : "Please try again in a moment.",
      });
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
              aria-label="Choose a resume file"
              tabIndex={-1}
            />
            <Button
              onClick={() => fileInputRef.current?.click()}
              loading={uploading}
              disabled={loading || atLimit}
            >
              {!uploading && <UploadIcon size={16} />}
              {uploading ? "Uploading…" : "Upload resume"}
            </Button>
          </>
        }
      />

      {!loading && !loadError && (
        <p className="mt-3 flex flex-wrap items-center gap-2 text-sm text-muted-foreground" aria-live="polite">
          <Badge tone={atLimit ? "warning" : "neutral"} className="tabular-nums">
            {used} of {MAX_RESUMES} used
          </Badge>
          {atLimit && <span>Delete a resume to upload a new one.</span>}
        </p>
      )}

      {uploadError && (
        <Alert role="alert" className="mt-4">
          {uploadError}
        </Alert>
      )}

      {loading ? (
        <ListSkeleton className="mt-6" rows={3} />
      ) : loadError ? (
        <div className="mt-6 flex flex-col items-start gap-3">
          <Alert role="alert" className="w-full">
            {loadError}
          </Alert>
          <Button variant="outline" size="sm" onClick={retryLoad}>
            <RefreshIcon size={14} />
            Try again
          </Button>
        </div>
      ) : resumes.length === 0 ? (
        <EmptyState
          className="mt-6 max-w-3xl"
          icon={<FileIcon size={20} />}
          title="No resumes yet"
          action={
            <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()}>
              <UploadIcon size={14} />
              Upload your first resume
            </Button>
          }
        >
          Add a PDF or DOCX and CyntraAI will read it so interviews and ATS checks can use it.
        </EmptyState>
      ) : (
        <ul className="mt-6 flex max-w-3xl flex-col gap-2" aria-label="Your resumes">
          <AnimatePresence initial={false}>
            {resumes.map((resume) => {
              const status = statusLabel(resume);
              const name = resumeName(resume);
              return (
                <motion.li
                  key={resume.id}
                  layout="position"
                  initial={{ opacity: 0, y: -8 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, scale: 0.98 }}
                  transition={{ duration: 0.22, ease: [0.22, 1, 0.36, 1] }}
                >
                  <ListRow
                    icon={<FileIcon size={18} />}
                    title={name}
                    editor={
                      renamingId === resume.id ? (
                        <InlineRename
                          initialValue={name}
                          label={`New name for ${name}`}
                          placeholder="Name (empty uses the file name)"
                          maxLength={MAX_RESUME_NAME_LENGTH}
                          validate={validateResumeName}
                          onSave={(v) => renameResume(resume, v)}
                          onClose={closeRename}
                        />
                      ) : undefined
                    }
                    meta={`${resume.display_name ? `${resume.file_key.split("/").pop()} · ` : ""}Uploaded ${new Date(resume.created_at).toLocaleDateString()}`}
                    badge={<Badge tone={status.tone}>{status.text}</Badge>}
                    actions={
                      <>
                        {!resume.parsed_text && (
                          <Button
                            type="button"
                            variant="secondary"
                            size="sm"
                            onClick={() => handleRetry(resume.id)}
                            loading={retryingId === resume.id}
                            aria-label={`Retry processing ${name}`}
                          >
                            {retryingId === resume.id ? "Processing…" : "Retry processing"}
                          </Button>
                        )}
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={(e) => {
                            renameOpener.current = e.currentTarget;
                            setRenamingId(resume.id);
                          }}
                          aria-label={`Rename ${name}`}
                          className="text-muted-foreground"
                        >
                          <PencilIcon size={14} />
                          Rename
                        </Button>
                        <Button
                          type="button"
                          variant="ghost"
                          size="sm"
                          onClick={() => handleDelete(resume)}
                          aria-label={`Delete ${name}`}
                          className="text-muted-foreground hover:bg-destructive-soft hover:text-destructive"
                        >
                          <TrashIcon size={14} />
                          Delete
                        </Button>
                      </>
                    }
                  />
                </motion.li>
              );
            })}
          </AnimatePresence>
        </ul>
      )}
    </div>
  );
}
