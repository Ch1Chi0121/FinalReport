COMP90072 Complex Systems report
Author: Chia-Chi Hsu
Migrated to the course template on 10 October 2026.

Template: https://github.com/SuzieSheehy/FinalReport
Source revision: 671f572c1d5da799ae8b5064f71243c9c2df61e7
The template's BSD 3-Clause LICENSE is retained in this directory.

Files:
- main.tex: root document; compile this file.
- preamble.tex: packages, report settings, author name, and date.
- cover.tex: university logo, course details, project title, and author.
- abstract.tex: existing abstract.
- chapter1.tex: all six chapters of the report.
- biblio.bib: nine references, with the original citation keys and DOI links.
- appendix1.tex: commented Q1-12 coverage and revision notes; not typeset.
- figures/uom_banner.pdf: university logo from the course template.
- main.pdf: compiled report to include in the GitHub submission.

The report uses the template's report class, A4 paper, 2 cm margins, cover
layout, contents, chapter numbering, and abbrv bibliography style. The font
size is 11pt; the template's 10.5pt is not a standard report-class option.
Unused example content and packages were removed. References are set flush
left to avoid stretched spacing around long DOI links.

The revised abstract and body text are preserved verbatim, apart from heading
commands changed to chapter/section levels. Equations and citation keys are
unchanged; equation, table, and reference numbers follow the template.
Conclusion remains omitted. Results and Discussion retain their TODOs.

The report follows Complex_Systems_Project_Plan.md and
the supplied specification and rubrics. Questions 1-12 are covered at the
theoretical or proposed-experiment stage. Optional extensions in Section 3
are excluded. No simulation, experiment, or numerical result was generated.

Before submission:
- Author and date are configured in preamble.tex. The author is Chia-Chi Hsu;
  this value also supplies PDF metadata.
- Search the .tex files for TODO to find missing evidence and revision notes.
  Blue TODO paragraphs are visible; percent-prefixed comments are not.
- Keep the final report within 20 pages, including front matter and references.

Build with a standard LaTeX installation, from this report directory:
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
  bibtex main
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
  pdflatex -interaction=nonstopmode -halt-on-error main.tex

Alternatively, Tectonic runs BibTeX and repeat passes automatically:
  tectonic main.tex
The multi-file project needs every source file and the logo when compiling.

Build verification:
- Compiled with Tectonic 0.17.0: 13 A4 pages, including the cover and references.
- All pages were rendered and visually checked.
- No unresolved citations/references or overflowing text were reported.
- main.pdf and ../output/pdf/COMP90072_Report.pdf are identical copies.

For the teacher's GitHub workflow, copy this project's source files, logo,
LICENSE, and main.pdf into your fork of FinalReport. Include the compiled PDF
in the commit. The .gitignore excludes build intermediates and local archives,
but does not exclude main.pdf. Local migration does not create a fork or PR.

Earlier source and PDF snapshots are retained locally in archive directories
and are not included in the handoff ZIP.
