# qdvc-gioia-diagram

Generate a **Gioia-style data structure diagram** (Gioia, Corley & Hamilton, 2013) from a
simple CSV file.

The tool takes a three-column CSV describing a hierarchy of first-order concepts,
second-order themes, and aggregate dimensions, and lays it out as the familiar
three-panel figure: first-order concepts on the left, feeding through a large grey
arrow into second-order themes in the middle, which connect to aggregate-dimension
ovals on the right. It handles text wrapping, box sizing, alignment, and spacing
automatically, and exports to PDF, PNG, SVG, or any other format matplotlib supports.

## What "QDVC" means

**QDVC = Quick and Dirty, Vibe-Coded.** This project was built rapidly and
conversationally with an AI assistant rather than through a formal engineering
process. It does one job and does it reasonably well, but it is deliberately small
in scope. Treat it as a handy utility, not as production-grade software.

"Vibe-coded" is not an excuse for an undocumented black box, though — see below.

## The vibe-coding process is documented

Every step of the conversational build is recorded in the [`vibe-coding/`](vibe-coding/)
folder. The transcript ([`vibe-coding/2026-07-20-claude.md`](vibe-coding/2026-07-20-claude.md))
captures the whole process so that anyone can see exactly how the code came to be:

- **Every round is preserved in order** — each user request is followed by the
  assistant's response, numbered sequentially from the very first prompt (the full
  original specification) through each round of refinements.
- **The original specification is kept verbatim**, so the design intent behind the
  layout rules (panel structure, enumeration scheme, alignment, drop shadows, and so
  on) is never lost.
- **Each committed round records its Git commit hash**, so any point in the
  transcript can be tied back to the exact state of the code at that time.
- **Design decisions, bugs, and fixes are visible**, including the reasoning behind
  changes such as adaptive panel widths, the monospace-enumeration option, the
  connector geometry, and the spacing tweaks — not just the final result.

The intent is that the "quick and dirty" origin is fully auditable rather than opaque.

## Installation

Requires Python 3 and matplotlib.

```bash
pip install -r requirements.txt
```

## Usage

```bash
python gioia.py INPUT.csv OUTPUT.pdf [options]
```

The input CSV must have exactly these three columns:

```csv
first_order_concept,second_order_theme,aggregate_dimension
```

The hierarchy is many-to-one at each level: many first-order concepts belong to one
second-order theme, and many second-order themes belong to one aggregate dimension.
Row order is preserved in the diagram, so order your rows the way you want them to
appear top-to-bottom.

The output format is inferred from the file extension you give
(`.pdf`, `.png`, `.svg`, ...).

### Options

| Option | Description |
| --- | --- |
| `-m`, `--mono-enum` | Render the enumeration labels (`1A`, `1B`, ...) in a monospace font. The concept text stays in the normal font. Off by default. |
| `-v`, `--verbose` | Print timed progress messages while the diagram is built (useful, since laying out larger diagrams can take a few seconds). |
| `-h`, `--help` | Show usage help. |

## Try it out

A ready-made sample dataset, [`example.csv`](example.csv), is included. It is a small
illustrative data structure loosely themed around videoconferencing fatigue. Generate
a diagram from it with:

```bash
python gioia.py example.csv example.pdf
```

or, to see the monospace enumeration variant with progress output:

```bash
python gioia.py example.csv example.png --mono-enum --verbose
```

Open the resulting file to see the three-panel Gioia layout the tool produces.

## About the Gioia data structure

The visual this tool draws is the "data structure" from the Gioia methodology:

> Gioia, D. A., Corley, K. G., & Hamilton, A. L. (2013). Seeking Qualitative Rigor in
> Inductive Research. *Organizational Research Methods, 16*(1), 15–31.
> https://doi.org/10.1177/1094428112452151

In that paper the data structure is described as perhaps the pivotal step of the
approach: it shows the progression from raw, informant-centric first-order codes, to
more abstract researcher-centric second-order themes, and finally to aggregate
theoretical dimensions. It is meant to make the analytical journey from data to theory
visible, and thereby to demonstrate rigor.

## A note on limitations — the data structure is not a formula

Producing a tidy data-structure diagram is easy to mistake for having done rigorous
qualitative analysis. It is not the same thing, and the diagram can flatter work that
has not really grappled with interpretation.

Even Gioia and colleagues cautioned against treating their approach as a rigid
template or "cookbook" to be reproduced formulaically rather than as a flexible
methodology. That concern has been developed further by:

> Mees-Buss, J., Welch, C., & Piekkari, R. (2020). From Templates to Heuristics: How
> and Why to Move Beyond the Gioia Methodology. *Organizational Research Methods,
> 25*(2), 405–429. https://doi.org/10.1177/1094428120967716

Mees-Buss and colleagues argue that using the Gioia methodology as a *template* does
not, on its own, address the genuine interpretive challenges of moving from field data
to theoretical understanding. They call for a shift from procedural rigor (following
the steps and producing the standard figure) toward interpretive rigor grounded in a
hermeneutic orientation, offering a set of heuristics rather than a fixed procedure.

**So: this tool draws the picture. It does not do the thinking.** Use the diagram as a
communication aid for analysis you have actually done, and read the two papers above
before leaning on the format as evidence of rigor in its own right.

## License and attribution

This is a quick, vibe-coded utility. It is not affiliated with or endorsed by any of
the authors cited above; those references are provided for scholarly context and
acknowledgement.
