"""Prints the eval table.  From apps/api:  python -m tests.rag_eval.report

Offline and free: it uses the deterministic fake embedder, no network."""

from . import harness as h
from .golden import RESUMES


def pipelines():
    out = {"v1": (h.v1_chunker, h.v1_semantic)}
    try:
        from . import v2_pipeline

        out["v2"] = (v2_pipeline.chunker, v2_pipeline.semantic)
    except ImportError:
        pass
    return out


def main() -> None:
    for name, (chunker, scorer) in pipelines().items():
        print(f"\n=== pipeline {name} ===")
        print(f"{'resume':16} {'chunks':>6} {'max':>5} {'cut':>4} {'sections':>9} {'ev@1':>5} {'ev@3':>5}")
        for resume, text in RESUMES.items():
            chunks = chunker(text)
            stats = h.chunk_stats(text, chunks)
            jd = "frontend" if resume == "frontend_dev" else "backend"
            print(
                f"{resume:16} {stats['count']:>6} {stats['max_chars']:>5} {stats['cut_mid_line']:>4} "
                f"{h.section_recall(resume, chunks):>9.2f} {h.evidence_hit(resume, jd, chunks, 1):>5.2f} "
                f"{h.evidence_hit(resume, jd, chunks, 3):>5.2f}"
            )
        for jd in ("backend", "frontend"):
            sem = h.semantic_scores(jd, chunker, scorer)
            comp = h.composite_scores(jd, chunker, scorer)
            print(f"\n  JD={jd}")
            print("  semantic :", {k: round(v, 2) for k, v in sem.items()})
            print("  composite:", comp)
            print("  ranking  :", h.ranking_quality(jd, comp), "| weak-resume floor:", h.weak_resume_floor(jd, comp))


if __name__ == "__main__":
    main()
