COMP90072 Final Report

Author: Chia-Chi Hsu
Cover date: 21 October 2026
Source edition: 23 October 2026

The English report has 20 physical pages, including the cover, Abstract,
Contents and bibliography. It uses A4 pages, 11pt body text, 2 cm margins
and chapter numbering. Abstract and Contents occupy separate pages; each
numbered chapter starts on a new page.

Files
  main.tex                 Primary document
  preamble.tex, cover.tex  Formatting and cover
  abstract.tex             Abstract
  chapter1.tex-chapter6.tex Introduction, model, theory, methods, results,
                           and discussion/conclusion
  biblio.bib               Eight scholarly references and the course handout
  figures/uom_banner.pdf   University of Melbourne logo from the template
  generated/               Figures, tables and numeric definitions
  main.pdf                 Compiled report
  final_report.tex         Compatibility entry point that inputs main.tex

Build in this directory with Tectonic 0.17.0:
  tectonic -X compile main.tex

Alternatively, with standard LaTeX/BibTeX:
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
  bibtex main
  pdflatex -interaction=nonstopmode -halt-on-error main.tex
  pdflatex -interaction=nonstopmode -halt-on-error main.tex

The Tectonic build was tested from a fresh directory. The standard LaTeX
sequence is provided for other installations and was not tested on this host.
All figures, tables and numeric inputs required for compilation are included.
No simulation is needed to build the PDF. Experimental code and its run
instructions are distributed separately in COMP90072_Experiment_Code.zip.

Template: https://github.com/SuzieSheehy/FinalReport
Template commit: 671f572c1d5da799ae8b5064f71243c9c2df61e7
The template's BSD 3-Clause LICENSE is included.
