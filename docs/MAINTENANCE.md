# Maintenance guide

This document is for whoever maintains `qdvc-gioia-diagram` next — human or AI. It
explains how the project is organised, how the one script works internally, how to make
changes safely, and the conventions this repository follows.

> Filename note: the task that requested this guide asked for `docs/MAINTENACE.md`
> (missing an "N"). It has been created as `docs/MAINTENANCE.md` with the correct
> spelling. If a link to the misspelled name is needed for compatibility, add a
> redirect or stub rather than renaming this file.

## 1. What this project is

A single-purpose command-line tool that renders a Gioia-style "data structure" diagram
from a three-column CSV. It is intentionally small ("quick and dirty, vibe-coded").
The entire implementation lives in one file, `gioia.py`, and depends only on
`matplotlib`.

Keep it small. Resist the urge to turn it into a framework. New capabilities should
earn their place; when in doubt, prefer a flag with a sensible default over changing
existing behaviour.

## 2. Repository layout

```
gioia.py              The whole program (CLI + layout engine).
requirements.txt      Runtime dependency (matplotlib).
example.csv           Sample dataset used in the README's "Try it out" section.
README.md             User-facing cover page.
docs/MAINTENANCE.md   This file.
vibe-coding/          Chronological transcript of how the tool was built.
.gitignore            Ignores __pycache__, .venv, and local test I/O (input.csv, output.pdf).
```

There is no package, no module split, no test suite, and no CI. That is by design for a
tool this size. If the project grows, sections 7 and 8 below note where that would
change.

## 3. Environment setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

`matplotlib` is pinned to `>=3.5`; the APIs used (`TextPath`, `patheffects`,
`FancyBboxPatch`, `Ellipse`) have been stable well below that floor. The script forces
the non-interactive `Agg` backend, so it runs headless with no display.

## 4. How `gioia.py` works

The program has two phases: **load** the CSV into an ordered hierarchy, then **draw**
it. Everything is done in matplotlib "axis units" where the x-axis nominally spans
0–100; a single constant, `PTS_PER_AXIS`, converts axis units to typographic points so
that text measurement and layout stay in one consistent coordinate system.

Read the code in this order:

1. **`load(csv_path)`** — reads the CSV into a nested `OrderedDict`:
   `dim -> theme -> [concepts]`. Order is preserved, which is what fixes the
   top-to-bottom order in the figure. Uses `utf-8-sig` so a BOM in the CSV is tolerated.

2. **Text helpers** (module level, so they are cacheable and testable):
   - `_text_width_pts(s, fontsize, weight, family)` — measures the rendered width of a
     string in points via `TextPath`. **Memoised** in `_WIDTH_CACHE` because this is
     the hot path; measuring the same strings repeatedly during width search would
     otherwise dominate runtime.
   - `_hard_break_word(...)` — splits a single word too wide to fit, so nothing ever
     bleeds past a box edge.
   - `wrap(...)` — greedy word wrap to a points width, with an optional narrower
     `first_max_pts` for hanging-indent first lines.
   - `wrap_enumerated(...)` — builds the first-order lines as font-tagged *runs*. The
     enumeration (`"1A"`) can be in one font (e.g. monospace) and the concept body in
     another. Returns visual lines as `(indent_pts, [(text, family, pre_gap_pts), ...])`.
     This is what lets `--mono-enum` affect only the enumeration, and what produces the
     small gap between `1A` and `.` and the larger gap before the concept name.
   - `letters(i)` — index to `A..Z`, cycling.

3. **`Progress`** — a tiny callable that prints timed messages when `--verbose` is on.

4. **`draw(dims, out_path, mono_enum, progress)`** — the layout engine. Its stages,
   in order (each marked with a `# ----` banner comment):
   - **Layout constants**: panel positions/widths, per-panel padding
     (`PANEL_PAD_L/_R`), box padding, line heights (`LH_*` derived from font size ×
     `LINE_SPACING`), the em-based right inset, and the enumeration separator gap.
   - **Measure text**: wrap every first-order concept and second-order theme; compute
     each block's height. First-order and second-order boxes in a row share the taller
     height (the "equal height" rule).
   - **Tighten panel 1**: shrink panel 1 to the widest first-order line actually
     present (never wider than the original).
   - **Tighten panel 2**: search progressively narrower widths, re-wrapping themes,
     stopping when any theme would need more than `MAX_THEME_LINES` lines; pick the
     narrowest width that still fits.
   - **Reflow x-positions**: place the three panels so the *visible grey gaps* between
     them are equal (the box-to-box gaps add back each panel's padding).
   - **Content height / extent**: total height, then set axis limits exactly to the
     content so `bbox_inches="tight"` plus a fixed `pad_inches` yields a uniform ~2 cm
     margin on all sides.
   - **Draw**: grey panels + headings; the `box()` helper (supports plain centred text
     and "rich" multi-run left-aligned text); the `grey_arrow()` helper; then the
     top-down pass that draws each first-order box, its theme box, and the connecting
     arrow; finally the aggregate ovals with `ellipse_point()` computing exact
     boundary contacts for the connector lines. Saves with `savefig`.

5. **`main()`** — `argparse` CLI: positional `input`/`output`, flags `-m/--mono-enum`
   and `-v/--verbose`.

### Coordinate model in one paragraph

Everything is laid out in axis units (x nominally 0–100, y growing upward). Text is
measured in points; `PTS_PER_AXIS = FIG_W * 72 / 100` converts between them. Widths and
gaps are computed in axis units; text-fit checks convert to points. Keeping this single
conversion correct is what prevents text bleed and keeps margins uniform, so be careful
when touching `FIG_W`, `PTS_PER_AXIS`, `set_xlim/ylim`, or `set_size_inches`.

## 5. Common maintenance tasks

- **Change fonts / sizes**: `FS_FOC`, `FS_THEME`, `FS_DIM`, `FS_HEAD` and
  `LINE_SPACING` near the top of `draw()`. Line heights recompute from these.
- **Change spacing between panels**: `GREY_GAP` in the reflow stage. Per-panel padding
  is `PANEL_PAD_L` / `PANEL_PAD_R`.
- **Change the page margin**: `PAD_INCHES` (currently 2 cm).
- **Change the enumeration style**: `wrap_enumerated` (the `1A` token, the dot, the
  half-dot gap, and the separator before the concept name).
- **Change how aggressively themes wrap**: `MAX_THEME_LINES` and the panel-2 search
  loop.
- **Colours / shadows**: `GREY_PANEL`, `SHADOW`, and the `facecolor` values in `box`,
  `grey_arrow`, and the oval-drawing block.

When adding a user-facing option, add it to `argparse` in `main()`, thread it into
`draw()` as a keyword argument with a default that preserves current behaviour, and
document it in the README's options table and `--help`.

## 6. Testing changes (there is no automated suite)

Verify by generating output and checking both the picture and the geometry:

```bash
python3 gioia.py example.csv /tmp/out.pdf            # default
python3 gioia.py example.csv /tmp/out_mono.png -m -v # mono enumeration + progress
```

Things to check after any layout change:

- **No text bleed**: text must stay inside every box/oval, including long single words
  (they should hard-break). Try a stress CSV with a very long concept and a very long
  single "word".
- **Uniform margins**: left/right/top margins should be roughly equal (~2 cm); the grey
  panels should reach the bottom with the same margin.
- **Equal panel gaps**: the grey gap between panels 1–2 should equal that between 2–3.
- **Connectors touch**: the arrow tip meets the panel-2 box edge; connector lines meet
  the oval boundary exactly.
- **Both modes**: run with and without `-m`; the default must look unchanged from before
  your edit unless the edit was specifically about the default.

Because there is no display, inspect output by rendering the PDF to PNG (e.g. with
`pdf2image`/`poppler`) or opening it directly. Geometry can also be checked
programmatically by monkeypatching `matplotlib.axes.Axes.text` to capture draw
coordinates — this is how several past rounds verified font assignment and spacing
without relying on eyeballing.

## 7. Coding conventions

- **One file, standard library + matplotlib only.** Do not add dependencies for
  cosmetic gains.
- **Keep helpers at module scope** where they are pure (the text helpers), and keep
  layout logic inside `draw()` where it needs the constants. `box`, `grey_arrow`,
  `ellipse_point` are nested in `draw()` on purpose — they close over the axis and
  constants.
- **Comment the "why", not the "what".** The `# ----` banner comments delimit the
  pipeline stages; keep them accurate if you reorder stages.
- **Behaviour-preserving refactors are welcome**, but confirm the rendered output is
  byte-for-byte or visually identical first.

## 8. Git and documentation conventions

This repo documents its own construction; keep that up.

- **Commit message prefixes**, in priority order — use the first that applies:
  `[feat]` (any new user-facing capability), then `[fix]` (bug/defect fix), then
  `[refactor]` (internal only, no user-facing change), then `[docs]` (documentation
  only), then `[chore]`. A commit that both adds a feature and fixes a bug is `[feat]`.
- **Commit messages** have a title line with the prefix, a body explaining the change,
  and a trailing `Co-authored-by:` line when an AI assistant contributed.
- **The `vibe-coding/` transcript** is part of the project's value, not clutter. If the
  project continues to be developed conversationally, keep appending rounds (user
  request, assistant response, and the resulting commit hash) so the build history
  stays auditable.
- **`.gitignore`** deliberately excludes local test inputs/outputs (`input.csv`,
  `output.pdf`) and `__pycache__`/`.venv`. Do not commit generated diagrams.

## 9. Known limitations and likely next asks

- **Runtime scales with text measurement.** The width cache keeps this manageable, but
  the very first wrap pass over all labels is unavoidable cold cost. If diagrams get
  large, consider caching wrap results (keyed by text+width+font), not just widths.
- **Column names are fixed**: `first_order_concept`, `second_order_theme`,
  `aggregate_dimension`. Making these configurable would be a reasonable `[feat]`.
- **26-concept cap per theme**: enumeration letters cycle `A..Z` (`letters()`); beyond
  26 first-order concepts in one theme the letters repeat. Revisit if that limit is hit.
- **No input validation to speak of.** Malformed CSVs will raise rather than explain.
  Friendlier errors would be a worthwhile, low-risk improvement.

If you are an AI worker picking this up: read the latest `vibe-coding/` transcript
entry first to understand the most recent intent, sync to the current `main`, make the
smallest change that satisfies the request, verify with section 6, and follow the
commit conventions in section 8.
