COMP90072 Final Report, 22 October 2026

Compile main.tex, as specified by https://github.com/SuzieSheehy/FinalReport .
Template commit: 671f572c1d5da799ae8b5064f71243c9c2df61e7.
The template BSD 3-Clause LICENSE is retained.

The completed report uses the draft's writing style, the teacher's A4 report
class, one-sided pages, 2 cm margins, cover, contents, chapter-based numbering
and abbrv bibliography. The supported 11pt body size replaces the template's
nonstandard 10.5pt option. The cover, Abstract and Contents occupy three separate
pages. Each of the six numbered chapters starts on a new page, with a two-line
Chapter N / chapter-title heading, as in the supplied draft. Bibliography also
starts on its own page. The final document has 20 physical pages.

To meet the page cap while retaining this structure, the body remains 11pt,
with normal body leading, slightly tighter Results leading, 9pt captions, and wide
figure panels regenerated from the unchanged experimental data. Figure data,
labels and curve definitions are unchanged. The correlation matrix uses
rectangular cells so its numeric annotations remain separated. No scientific
result or reference was removed. The 22 October revision strengthens key captions,
research motivation, terminology and the scientific conclusion. Precision-only
macro changes expose narrow intervals from the original stored estimates.
The subsequent language edit removes file inventories and internal workflow
commentary from the report. Body and Results line spacing are both increased;
scientific methods, measurements, mathematical arguments and citations remain.

Author: Chia-Chi Hsu. Subject: COMP-90072.
Cover date: 21 October 2026. Latest editorial revision: 22 October 2026.
Coordinators follow the supplied template: A/Prof. Suzie Sheehy and
Prof. Christian Reichardt. The template's sample project title, author, date
and unrelated Coulomb illustration have been replaced or removed.

Files:
- main.tex: primary teacher-template document.
- preamble.tex, cover.tex, abstract.tex: settings and front matter.
- chapter1.tex to chapter6.tex: completed introduction, model, theory, methods,
  results (including all three extensions), and discussion/conclusion.
- biblio.bib: nine verified references with their original citation keys.
- figures/uom_banner.pdf: the template's University of Melbourne logo.
- generated/: production-derived figures, tables and numeric macros.
- main.pdf: the completed report.
- final_report.tex: compatibility entry point that inputs main.tex.
  The workspace final_report.pdf is identical to main.pdf.

Build in this directory using Tectonic 0.17.0:
  tectonic -X compile main.tex

Or use standard LaTeX/BibTeX:
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
  bibtex main
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
  pdflatex -interaction=nonstopmode -halt-on-error main.tex

The Tectonic command was tested. The standard sequence is supplied for LaTeX
users; it was not executed on this host. All generated inputs are included,
so compiling this source handoff does not require rerunning simulations.
The handoff is the editable report, not the full simulation/data archive.
For production provenance and code, see the complete workspace README and
analysis/report_manifest.json. Earlier draft and article editions are preserved
in the full project's report/archive directories and are outside this handoff.
