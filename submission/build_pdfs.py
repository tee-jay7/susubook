#!/usr/bin/env python3
"""Build the submission PDFs from the markdown documentation.

Pipeline: markdown -> (pandoc) -> HTML -> (headless Chrome) -> PDF.

Two things need care:
  * Mermaid code blocks are replaced with the SVGs already rendered to
    docs/diagrams/, in document order. Pandoc would otherwise emit them as
    unreadable code listings.
  * Intermediate HTML is written into docs/ so that relative image paths
    (screenshots/..., diagrams/...) resolve without rewriting them.

Usage:  python3 submission/build_pdfs.py
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
OUT = ROOT / "submission"
BUILD = DOCS / "_build"

# Mermaid blocks in 07 appear in this order and correspond to these renders.
DIAGRAMS = [
    ("01-context-dfd", "Context diagram (Level 0 data flow)"),
    ("02-level1-dfd", "Level 1 data flow — recording a contribution"),
    ("03-use-case", "Use case diagram"),
    ("04-cycle-state", "Contribution cycle state model"),
    ("05-layer-stack", "Layered architecture"),
    ("06-class-diagram", "Domain class diagram"),
    ("07-sequence-uc03", "Sequence diagram — UC-03 record contribution"),
    ("08-erd", "Entity-relationship diagram"),
]

# Consolidated document, in the order examination §10 requires.
PROJECT_DOC = [
    ("00-section-map", "Mapping to Examination Requirements"),
    ("01-problem-definition", "Sections 1–3: Title, Problem Statement, Aim and Objectives"),
    ("02-stakeholder-analysis", "Section 4: Stakeholders"),
    ("03-requirements", "Section 5: Requirements Analysis"),
    ("04-srs", "Section 6: Software Requirements Specification"),
    ("05-effort-estimation", "Section 7: Software Effort Estimation"),
    ("07-system-analysis-and-design", "Sections 8–9: System Analysis and Design"),
    ("10-implementation", "Section 10: Implementation"),
    ("09-testing", "Section 11: Testing"),
    ("08-technical-debt", "Section 12: Technical Debt"),
    ("12-deployment", "Section 13: Deployment"),
    ("13-user-manual", "Section 14: User Manual"),
    ("11-maintenance-evolution", "Sections 15–16: Maintenance and Future Evolution"),
    ("14-conclusion", "Sections 17–19: Limitations, Conclusion, References"),
    ("06-scope", "Appendix A: Project Scope Definition"),
    ("CHANGELOG-requirements", "Appendix B: Requirements Change Log"),
]

STANDALONE = [
    ("SRS", ["04-srs"]),
    ("Testing_Report", ["09-testing"]),
    ("Technical_Debt_Plan", ["08-technical-debt"]),
    ("User_Manual", ["13-user-manual"]),
]

TITLE_PAGE = """
<div class="titlepage">
  <p class="inst">UNIVERSITY OF GHANA</p>
  <p class="dept">College of Basic and Applied Sciences<br>Department of Computer Science</p>
  <hr>
  <p class="course">CSCD602 — Advanced Software Engineering</p>
  <p class="assess">Individual Project-Based Examination</p>
  <h1>SusuBook</h1>
  <p class="subtitle">A Digital Susu Collection and Accountability System</p>
  <hr>
  <table class="meta">
    <tr><td>Student</td><td>[STUDENT NAME]</td></tr>
    <tr><td>Student ID</td><td>[STUDENT ID]</td></tr>
    <tr><td>Examiner</td><td>Prof. Solomon Mensah</td></tr>
    <tr><td>Live application</td><td>https://susubook-fdtbppd7sq-uc.a.run.app</td></tr>
    <tr><td>Source repository</td><td>https://github.com/tee-jay7/susubook</td></tr>
  </table>
</div>
"""


def replace_mermaid(text: str) -> str:
    """Swap fenced mermaid blocks for the pre-rendered SVGs, in order."""
    blocks = list(re.finditer(r"```mermaid\n.*?```", text, re.S))
    if not blocks:
        return text
    if len(blocks) != len(DIAGRAMS):
        print(f"  ! {len(blocks)} mermaid blocks but {len(DIAGRAMS)} diagrams mapped")
    out, last = [], 0
    for i, m in enumerate(blocks):
        out.append(text[last:m.start()])
        if i < len(DIAGRAMS):
            name, caption = DIAGRAMS[i]
            out.append(
                f'<figure class="diagram">\n'
                f'<img src="diagrams/{name}.svg" alt="{caption}">\n'
                f"<figcaption>{caption}</figcaption>\n</figure>\n"
            )
        last = m.end()
    out.append(text[last:])
    return "".join(out)


def prepare(stems: list[str], headings: dict[str, str] | None) -> Path:
    """Concatenate the sections, one page break between each."""
    BUILD.mkdir(exist_ok=True)
    parts = []
    for i, stem in enumerate(stems):
        src = DOCS / f"{stem}.md"
        if not src.exists():
            sys.exit(f"missing: {src}")
        if i:
            parts.append('\n<div class="pagebreak"></div>\n')
        if headings and stem in headings:
            parts.append(f'\n<div class="partdivider">{headings[stem]}</div>\n')
        parts.append(replace_mermaid(src.read_text()))
    combined = BUILD / "combined.md"
    combined.write_text("\n\n".join(parts))
    return combined


def to_pdf(md: Path, out_pdf: Path, doc_title: str, *, front_matter: bool = False) -> None:
    # The HTML must sit directly in docs/, not in a subdirectory: every image
    # reference in the markdown is relative to docs/ (screenshots/...,
    # diagrams/...), and so is the stylesheet link. Rendering from docs/_build/
    # silently resolved both one level too deep — broken images and no CSS.
    html = DOCS / f"_render_{out_pdf.stem}.html"
    cmd = ["pandoc", str(md), "-f", "gfm+raw_html", "-t", "html5", "-s",
           "--metadata", f"title={doc_title}",
           "--css", "_build/pdf.css", "-o", str(html)]
    if front_matter:
        # pandoc emits include-before-body ahead of the table of contents, so
        # the order becomes title page -> contents -> body.
        (BUILD / "title.html").write_text(TITLE_PAGE)
        cmd += ["--include-before-body", "_build/title.html",
                "--toc", "--toc-depth=2"]
    try:
        subprocess.run(cmd, check=True, cwd=DOCS)
        subprocess.run(
            ["node", str(OUT / "render.mjs"), str(html), str(out_pdf)],
            check=True,
        )
    finally:
        html.unlink(missing_ok=True)
    print(f"  ✓ {out_pdf.name}")


def main() -> None:
    if not shutil.which("pandoc"):
        sys.exit("pandoc not found")
    BUILD.mkdir(exist_ok=True)
    shutil.copy(OUT / "pdf.css", BUILD / "pdf.css")
    OUT.mkdir(exist_ok=True)

    print("Building submission PDFs\n")

    headings = {stem: label for stem, label in PROJECT_DOC}
    md = prepare([s for s, _ in PROJECT_DOC], headings)
    to_pdf(md, OUT / "Project_Documentation.pdf",
           "SusuBook — Project Documentation", front_matter=True)

    for name, stems in STANDALONE:
        md = prepare(stems, None)
        to_pdf(md, OUT / f"{name}.pdf", f"SusuBook — {name.replace('_', ' ')}")

    shutil.rmtree(BUILD, ignore_errors=True)
    print("\nDone. Output in submission/")


if __name__ == "__main__":
    main()
