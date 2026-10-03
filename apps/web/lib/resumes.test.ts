import { describe, expect, it } from "vitest";
import { MAX_RESUMES, resumeName, validateResumeFile, validateResumeName } from "./resumes";

describe("resumes helpers", () => {
  it("allows three resumes", () => expect(MAX_RESUMES).toBe(3));

  it("names a resume by its file, not its storage folder", () => {
    expect(resumeName({ file_key: "resumes/u1/abc.pdf" })).toBe("abc.pdf");
  });

  it("accepts a small PDF or DOCX", () => {
    expect(validateResumeFile({ name: "cv.PDF", size: 1000 })).toBeNull();
    expect(validateResumeFile({ name: "cv.docx", size: 500 * 1024 })).toBeNull();
  });

  it("rejects the wrong type, an empty file and an oversized file", () => {
    expect(validateResumeFile({ name: "cv.txt", size: 10 })).toMatch(/PDF and DOCX/);
    expect(validateResumeFile({ name: "cv.pdf", size: 0 })).toMatch(/empty/);
    expect(validateResumeFile({ name: "cv.pdf", size: 500 * 1024 + 1 })).toMatch(/too large/);
  });

  it("prefers the owner's display name over the file name", () => {
    expect(resumeName({ file_key: "resumes/u1/abc.pdf", display_name: "Backend CV" })).toBe("Backend CV");
    expect(resumeName({ file_key: "resumes/u1/abc.pdf", display_name: null })).toBe("abc.pdf");
    expect(resumeName({ file_key: "resumes/u1/abc.pdf", display_name: "  " })).toBe("abc.pdf");
  });

  it("validates a resume name: empty is fine, over 80 characters is not", () => {
    expect(validateResumeName("")).toBeNull();
    expect(validateResumeName("a".repeat(80))).toBeNull();
    expect(validateResumeName("a".repeat(81))).toMatch(/80/);
    expect(validateResumeName(" ".repeat(90))).toBeNull();
  });
});
