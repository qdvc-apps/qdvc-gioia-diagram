#!/usr/bin/env python3
"""Generate a Gioia-style data structure diagram (Gioia et al. 2013) from a CSV.

CSV columns: first_order_concept,second_order_theme,aggregate_dimension
Hierarchy is M:1 .. M:1.

Usage: python gioia.py input.csv output.pdf [--mono-enum] [--verbose]
"""

import argparse
import csv
import time
from collections import OrderedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, PathPatch
from matplotlib.path import Path
from matplotlib.patheffects import withSimplePatchShadow
from matplotlib.textpath import TextPath


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------
def load(csv_path):
    """Return ordered structure:
       dims: OrderedDict[dim] -> OrderedDict[theme] -> [concepts]
    """
    dims = OrderedDict()
    with open(csv_path, newline="", encoding="utf-8-sig") as fh:
        for row in csv.DictReader(fh):
            foc = row["first_order_concept"].strip()
            theme = row["second_order_theme"].strip()
            dim = row["aggregate_dimension"].strip()
            dims.setdefault(dim, OrderedDict()).setdefault(theme, [])
            if foc:
                dims[dim][theme].append(foc)
    return dims


# ---------------------------------------------------------------------------
# Text wrapping helpers (measure with matplotlib for accuracy)
# ---------------------------------------------------------------------------
# Measuring glyph widths via TextPath is accurate but slow, and the panel-2
# width search re-measures the same strings many times. Cache by the exact
# arguments that affect width so repeated measurements are effectively free.
_WIDTH_CACHE = {}


def _text_width_pts(s, fontsize, weight, family=None):
    """Width of a string in points (TextPath size is in points)."""
    if not s:
        return 0.0
    key = (s, fontsize, weight, family)
    cached = _WIDTH_CACHE.get(key)
    if cached is not None:
        return cached
    prop = {"weight": weight}
    if family:
        prop["family"] = family
    tp = TextPath((0, 0), s, size=fontsize, prop=prop)
    width = tp.get_extents().width
    _WIDTH_CACHE[key] = width
    return width


def _hard_break_word(word, fontsize, weight, max_pts, family=None):
    """Break a single word that is wider than max_pts into pieces that fit."""
    pieces, cur = [], ""
    for ch in word:
        if _text_width_pts(cur + ch, fontsize, weight, family) <= max_pts \
                or not cur:
            cur += ch
        else:
            pieces.append(cur)
            cur = ch
    if cur:
        pieces.append(cur)
    return pieces


def wrap(text, fontsize, weight, max_pts, family=None, first_max_pts=None):
    """Greedy word wrap to a width given in points. Returns list of lines.

    Words wider than max_pts are hard-broken so text never bleeds outside
    its container. If ``first_max_pts`` is given, the first line is wrapped to
    that (typically narrower) width and subsequent lines to ``max_pts`` — used
    for hanging indents where an enumeration prefix occupies the first line.
    """
    words = text.split()
    if not words:
        return [""]
    # Pre-split any word too wide to ever fit on one line.
    tokens = []
    for w in words:
        if _text_width_pts(w, fontsize, weight, family) > max_pts:
            tokens.extend(_hard_break_word(w, fontsize, weight, max_pts, family))
        else:
            tokens.append(w)

    lines, cur = [], tokens[0]
    for w in tokens[1:]:
        trial = cur + " " + w
        limit = first_max_pts if (first_max_pts is not None and not lines) \
            else max_pts
        if _text_width_pts(trial, fontsize, weight, family) <= limit:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def letters(i):
    """0->A, 1->B ... cycles A..Z."""
    return chr(ord("A") + (i % 26))


def wrap_enumerated(prefix, body, fontsize, weight, max_pts,
                    prefix_family=None, body_family=None):
    """Wrap an enumerated concept, keeping the prefix in its own font.

    ``prefix`` (e.g. "1A. ") is rendered in ``prefix_family`` and the concept
    ``body`` in ``body_family``. Returns a list of visual lines; each line is
    ``(indent_pts, runs)`` where ``runs`` is a list of ``(text, family)`` and
    ``indent_pts`` is the left hanging indent (0 for the first line, the prefix
    width for continuation lines so body text stays aligned under itself).

    ``max_pts`` is the full text width available inside the box.
    """
    prefix_pts = _text_width_pts(prefix, fontsize, weight, prefix_family)
    # First line has less room (prefix sits before the body); continuation
    # lines hang-indent by the prefix width and use the full remaining width.
    body_lines = wrap(body, fontsize, weight, max_pts - prefix_pts,
                      body_family, first_max_pts=max_pts - prefix_pts)
    lines = []
    for k, bl in enumerate(body_lines):
        if k == 0:
            lines.append((0.0, [(prefix, prefix_family), (bl, body_family)]))
        else:
            lines.append((prefix_pts, [(bl, body_family)]))
    return lines


class Progress:
    """Lightweight verbose progress reporter with elapsed timing."""

    def __init__(self, enabled):
        self.enabled = enabled
        self.start = time.perf_counter()

    def __call__(self, msg):
        if self.enabled:
            elapsed = time.perf_counter() - self.start
            print(f"[{elapsed:6.2f}s] {msg}", flush=True)


# ---------------------------------------------------------------------------
# Main drawing
# ---------------------------------------------------------------------------
def draw(dims, out_path, mono_enum=False, progress=None):
    if progress is None:
        progress = Progress(False)
    # Font family for the first-order concept enumeration prefixes.
    ENUM_FAMILY = "monospace" if mono_enum else None

    # ---- Layout constants (in figure "data" units == points-ish) ----
    FIG_W = 13.0                     # inches
    DPI = 150

    # Column geometry (x in axis units 0..100)
    P1_X, P1_W = 2.0, 34.0           # first-order concepts panel
    P2_X, P2_W = 44.0, 22.0          # second-order themes panel
    P3_X, P3_W = 74.0, 22.0          # aggregate dimensions panel
    PANEL_PAD = 3.0                  # default horizontal padding inside panels
    # Panel 2 gets extra left padding so the arrowhead has clean grey space to
    # cross into and its tip meets the box edge without an awkward corner gap.
    PANEL_PAD_L = [PANEL_PAD, PANEL_PAD + 2.5, PANEL_PAD]
    PANEL_PAD_R = [PANEL_PAD, PANEL_PAD, PANEL_PAD]

    BOX_PAD_X = 1.2                  # horizontal text inset (axis units)
    BLOCK_GAP = 1.6                  # vertical gap between theme-blocks
    DIM_GAP = 3.0                    # extra gap between dimension groups
    TOP_MARGIN = 6.0                 # below headings
    BOTTOM_MARGIN = 3.0

    FS_FOC = 8.5
    FS_THEME = 9.0
    FS_DIM = 9.5
    FS_HEAD = 12.0

    LINE_SPACING = 1.2               # multiple of font size
    PTS_PER_AXIS = FIG_W * 72.0 / 100.0
    # Per-block line height in axis units (font size * spacing, in points).
    LH_FOC = FS_FOC * LINE_SPACING / PTS_PER_AXIS
    LH_THEME = FS_THEME * LINE_SPACING / PTS_PER_AXIS
    LH_DIM = FS_DIM * LINE_SPACING / PTS_PER_AXIS

    # Extra inset on the right edge of panel-1 boxes (~one lowercase 'm').
    em_pts = _text_width_pts("m", FS_FOC, "normal", ENUM_FAMILY)
    BOX_PAD_R_EXTRA = em_pts / PTS_PER_AXIS   # axis units

    GREY_PANEL = "#e6e6e6"
    SHADOW = withSimplePatchShadow(offset=(2, -2), alpha=0.35)
    PAD_INCHES = 2.0 / 2.54          # ~2 cm margin around the cropped diagram

    # figure setup (guess height, refine after measuring)
    fig = plt.figure(figsize=(FIG_W, 16), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.axis("off")

    # ---- Measure text -> compute each theme block's line lists & heights ----
    # The x-axis spans 100 units over FIG_W inches (= FIG_W * 72 points).
    # Convert an available axis-x width into points so wrap() (which measures
    # glyphs in points via TextPath) is unit-consistent -> no bleed.
    def text_budget_pts(panel_w_axis, pad_axis):
        return (panel_w_axis - 2 * pad_axis) * PTS_PER_AXIS

    def pts_to_axis(pts):
        return pts / PTS_PER_AXIS

    progress("Measuring text and wrapping labels...")
    # Panel-1 text budget reserves BOX_PAD_X left + (BOX_PAD_X + one em) right.
    foc_text_pts = (P1_W - 2 * BOX_PAD_X - BOX_PAD_R_EXTRA) * PTS_PER_AXIS
    theme_text_pts = text_budget_pts(P2_W, BOX_PAD_X)
    # Ovals taper, so reserve extra horizontal padding for panel-3 text.
    dim_text_pts = text_budget_pts(P3_W, BOX_PAD_X + 2.5)

    # theme counter is per-second-order-theme index (the "1", "2" ...)
    theme_seq = 0
    blocks = []   # list of dicts describing each theme block
    for dim, themes in dims.items():
        dim_blocks = []
        for theme, concepts in themes.items():
            theme_seq += 1
            # first-order concept lines: enumeration prefix in ENUM_FAMILY,
            # concept body always in the proportional font.
            foc_lines = []
            for j, c in enumerate(concepts):
                prefix = f"{theme_seq}{letters(j)}. "
                foc_lines.extend(
                    wrap_enumerated(prefix, c, FS_FOC, "normal", foc_text_pts,
                                    prefix_family=ENUM_FAMILY, body_family=None))
            theme_lines = wrap(theme, FS_THEME, "bold", theme_text_pts)

            h_foc = len(foc_lines) * LH_FOC + 1.6
            h_theme = len(theme_lines) * LH_THEME + 1.6
            h = max(h_foc, h_theme)   # equal height rule
            dim_blocks.append({
                "theme": theme,
                "theme_lines": theme_lines,
                "foc_lines": foc_lines,
                "h": h,
            })
        blocks.append({"dim": dim, "theme_blocks": dim_blocks})

    # ---- Tighten panel 1 to the widest first-order line actually present ----
    progress("Tightening panel 1 width...")

    def rich_line_width_pts(line):
        """Total rendered width (pts) of a rich line: indent + all runs."""
        indent, runs = line
        return indent + sum(_text_width_pts(t, FS_FOC, "normal", fam)
                            for (t, fam) in runs)

    all_foc_lines = [ln for grp in blocks for b in grp["theme_blocks"]
                     for ln in b["foc_lines"]]
    widest_foc_pts = max((rich_line_width_pts(ln) for ln in all_foc_lines),
                         default=0.0)
    needed_p1 = pts_to_axis(widest_foc_pts) + 2 * BOX_PAD_X + BOX_PAD_R_EXTRA
    P1_W = min(P1_W, max(needed_p1, 8.0))   # never widen beyond original

    # ---- Tighten panel 2: re-wrap themes to the narrowest width that still
    #      keeps every theme within a small line budget, then fit content. ----
    def rewrap_themes(target_pts):
        return {b["theme"]: wrap(b["theme"], FS_THEME, "bold", target_pts)
                for grp in blocks for b in grp["theme_blocks"]}

    all_themes = list({b["theme"] for grp in blocks
                       for b in grp["theme_blocks"]})

    MAX_THEME_LINES = 3
    best_p2 = P2_W
    candidates = [P2_W - d for d in range(0, int(P2_W) - 8)]
    progress(f"Tightening panel 2 width (testing {len(candidates)} "
             f"candidate widths, re-wrapping {len(all_themes)} themes each)...")
    # Try progressively narrower panel-2 widths.
    for idx, cand in enumerate(candidates, 1):
        progress(f"  panel 2: trying width {cand:.1f} "
                 f"({idx}/{len(candidates)})...")
        cand_pts = text_budget_pts(cand, BOX_PAD_X)
        wrapped = rewrap_themes(cand_pts)
        max_lines = max(len(v) for v in wrapped.values())
        if max_lines > MAX_THEME_LINES:
            progress(f"  panel 2: width {cand:.1f} needs {max_lines} lines "
                     f"(> {MAX_THEME_LINES} max); stopping search")
            break
        # ensure the widest resulting line still fits this candidate width
        widest = max(_text_width_pts(ln, FS_THEME, "bold")
                     for v in wrapped.values() for ln in v)
        if pts_to_axis(widest) + 2 * BOX_PAD_X <= cand:
            best_p2 = cand
    progress(f"  panel 2: selected width {best_p2:.1f}")
    P2_W = best_p2
    theme_text_pts = text_budget_pts(P2_W, BOX_PAD_X)

    # Recompute theme line-wrapping and block heights at the final widths.
    final_theme_lines = rewrap_themes(theme_text_pts)
    for grp in blocks:
        for b in grp["theme_blocks"]:
            b["theme_lines"] = final_theme_lines[b["theme"]]
            h_foc = len(b["foc_lines"]) * LH_FOC + 1.6
            h_theme = len(b["theme_lines"]) * LH_THEME + 1.6
            b["h"] = max(h_foc, h_theme)

    # ---- Reflow panel x-positions so tightened panels stay evenly spaced ----
    progress("Laying out panels...")
    LEFT = 2.0
    RIGHT = 98.0
    ARROW_GAP = 8.0           # room between panel 1 and 2 for the grey arrow
    COL_GAP = 8.0             # room between panel 2 and 3 for connector lines
    total_w = P1_W + P2_W + P3_W
    avail = RIGHT - LEFT
    if total_w + ARROW_GAP + COL_GAP > avail:
        # Shrink gaps proportionally if content is wide.
        slack = max(avail - total_w, 4.0)
        ARROW_GAP = COL_GAP = slack / 2
    P1_X = LEFT
    P2_X = P1_X + P1_W + ARROW_GAP
    P3_X = P2_X + P2_W + COL_GAP

    # ---- Compute total content height ----
    total_h = 0.0
    for i, grp in enumerate(blocks):
        for b in grp["theme_blocks"]:
            total_h += b["h"] + BLOCK_GAP
        total_h += DIM_GAP
    total_h += TOP_MARGIN + BOTTOM_MARGIN

    # ---- Content extent (used to set axis limits so margins stay uniform) ----
    content_left = P1_X - PANEL_PAD_L[0]
    content_right = P3_X + P3_W + PANEL_PAD_R[2]
    content_w = content_right - content_left

    # Map the axes exactly onto the content so bbox_inches="tight" + pad_inches
    # yields uniform margins (no stray whitespace on any side). Keep 1:1 aspect
    # so axis x-units and y-units share the same physical scale.
    ax.set_xlim(content_left, content_right)
    ax.set_ylim(0, total_h)
    fig_w = max(6.0, content_w * FIG_W / 100.0)
    fig_h = max(4.0, total_h * FIG_W / 100.0)
    fig.set_size_inches(fig_w, fig_h)

    # ---- Panels ----
    panel_x = [P1_X, P2_X, P3_X]
    panel_w = [P1_W, P2_W, P3_W]
    panel_heads = ["First-order concepts", "Second-order themes",
                   "Aggregate dimensions"]
    for i in range(3):
        px = panel_x[i] - PANEL_PAD_L[i]
        pw = panel_w[i] + PANEL_PAD_L[i] + PANEL_PAD_R[i]
        ax.add_patch(plt.Rectangle((px, 0), pw, total_h,
                                   facecolor=GREY_PANEL, edgecolor="none", zorder=0))
        ax.text(px + pw / 2, total_h - TOP_MARGIN / 2 + 1.0, panel_heads[i],
                ha="center", va="center", fontsize=FS_HEAD, fontweight="bold",
                zorder=5)

    # ---- Helper: rounded box with wrapped text (centered or left-aligned) ----
    def box(x, y_top, w, h, lines, fontsize, weight, line_h, align="center",
            family=None, rich=False):
        p = FancyBboxPatch(
            (x, y_top - h), w, h,
            boxstyle="round,pad=0,rounding_size=0.6",
            facecolor="white", edgecolor="black", linewidth=1.0, zorder=3)
        p.set_path_effects([SHADOW])
        ax.add_patch(p)
        cy = y_top - h / 2
        block_h = len(lines) * line_h
        start = cy + block_h / 2 - line_h / 2
        if rich:
            # Each line is (indent_pts, [(text, family), ...]); draw left-aligned,
            # laying runs out left-to-right in their own fonts.
            x0 = x + BOX_PAD_X
            for k, (indent_pts, runs) in enumerate(lines):
                yk = start - k * line_h
                cursor = x0 + indent_pts / PTS_PER_AXIS
                for (text, fam) in runs:
                    ax.text(cursor, yk, text, ha="left", va="center",
                            fontsize=fontsize, fontweight=weight, family=fam,
                            zorder=4)
                    cursor += _text_width_pts(text, fontsize, weight, fam) \
                        / PTS_PER_AXIS
            return (x, y_top - h, w, h)
        if align == "left":
            tx, ha = x + BOX_PAD_X, "left"
        else:
            tx, ha = x + w / 2, "center"
        for k, ln in enumerate(lines):
            ax.text(tx, start - k * line_h, ln, ha=ha, va="center",
                    fontsize=fontsize, fontweight=weight, family=family,
                    zorder=4)
        return (x, y_top - h, w, h)  # x, y_bottom, w, h

    def grey_arrow(x0, y, x1):
        """Large grey right-pointing arrow between panels, centred at y."""
        hh = 1.6   # half-height of shaft
        head = 2.6
        headw = 3.0
        verts = [
            (x0, y - hh), (x1 - head, y - hh), (x1 - head, y - headw),
            (x1, y), (x1 - head, y + headw), (x1 - head, y + hh),
            (x0, y + hh), (x0, y - hh)
        ]
        codes = [Path.MOVETO] + [Path.LINETO] * (len(verts) - 2) + [Path.CLOSEPOLY]
        pp = PathPatch(Path(verts, codes), facecolor="#b0b0b0",
                       edgecolor="none", zorder=1)
        ax.add_patch(pp)

    # ---- Draw content top-down ----
    progress("Drawing panel-1 and panel-2 boxes...")
    y = total_h - TOP_MARGIN
    dim_centers = []   # (dim_name, y_center, span_top, span_bottom)

    for grp in blocks:
        grp_top = y
        theme_y_centers = []
        for b in grp["theme_blocks"]:
            h = b["h"]
            top = y
            # first-order concept box (panel 1) — rich left-aligned text
            box(P1_X, top, P1_W, h, b["foc_lines"], FS_FOC, "normal",
                LH_FOC, align="left", rich=True)
            # second-order theme box (panel 2)
            box(P2_X, top, P2_W, h, b["theme_lines"], FS_THEME, "bold",
                LH_THEME)
            # grey arrow from panel1 -> panel2 (touching both boxes)
            grey_arrow(P1_X + P1_W, top - h / 2, P2_X)
            theme_y_centers.append(top - h / 2)
            y -= h + BLOCK_GAP
        grp_bottom = y + BLOCK_GAP

        # ---- aggregate dimension centre alignment ----
        n = len(theme_y_centers)
        if n % 2 == 1:
            dim_cy = theme_y_centers[n // 2]
        else:
            dim_cy = (theme_y_centers[n // 2 - 1] + theme_y_centers[n // 2]) / 2.0
        dim_centers.append((grp["dim"], dim_cy, theme_y_centers))
        y -= DIM_GAP

    # ---- Draw aggregate dimension ovals + connectors ----
    # All ovals share one width and one height for visual consistency.
    progress("Sizing aggregate-dimension ovals...")
    dim_text_pts = text_budget_pts(P3_W, BOX_PAD_X + 2.5)
    dim_line_map = {dim: wrap(dim, FS_DIM, "bold", dim_text_pts)
                    for (dim, _, _) in dim_centers}
    OVAL_W = P3_W - 1.0
    # Height accommodates the wordiest label; kept identical for every oval.
    max_dim_lines = max(len(lines) for lines in dim_line_map.values())
    oval_h = max(max_dim_lines * LH_DIM + 4.0, 8.0)
    rx, ry = OVAL_W / 2.0, oval_h / 2.0

    def ellipse_point(cx, cy, px, py):
        """Point where the segment (px,py)->(cx,cy) meets the ellipse edge."""
        dx, dy = px - cx, py - cy
        denom = (dx / rx) ** 2 + (dy / ry) ** 2
        if denom <= 0:
            return cx, cy
        t = 1.0 / (denom ** 0.5)   # scale so the point lands on the boundary
        return cx + dx * t, cy + dy * t

    progress("Drawing ovals and connectors...")
    for (dim, dim_cy, theme_y_centers), grp in zip(dim_centers, blocks):
        dim_lines = dim_line_map[dim]
        cx = P3_X + P3_W / 2
        el = Ellipse((cx, dim_cy), OVAL_W, oval_h,
                     facecolor="black", edgecolor="black", zorder=3)
        el.set_path_effects([SHADOW])
        ax.add_patch(el)
        block_h = len(dim_lines) * LH_DIM
        start = dim_cy + block_h / 2 - LH_DIM / 2
        for k, ln in enumerate(dim_lines):
            ax.text(cx, start - k * LH_DIM, ln, ha="center", va="center",
                    color="white", fontsize=FS_DIM, fontweight="bold", zorder=4)
        # connectors: panel-2 box right edge -> exact oval boundary (no gap)
        x_start = P2_X + P2_W
        for ty in theme_y_centers:
            ex, ey = ellipse_point(cx, dim_cy, x_start, ty)
            ax.plot([x_start, ex], [ty, ey],
                    color="black", linewidth=1.0, zorder=2)

    progress(f"Saving figure to {out_path}...")
    fig.savefig(out_path, dpi=DPI, bbox_inches="tight", pad_inches=PAD_INCHES)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser(
        description="Generate a Gioia-style data structure diagram from a CSV.")
    parser.add_argument("input", help="input CSV file")
    parser.add_argument("output", help="output file (e.g. diagram.pdf/.png/.svg)")
    parser.add_argument(
        "-m", "--mono-enum", action="store_true",
        help="render first-order concept text (incl. 1A, 1B ... enumerations) "
             "in a monospace font")
    parser.add_argument(
        "-v", "--verbose", action="store_true",
        help="print timed progress messages while the diagram is built")
    args = parser.parse_args()

    progress = Progress(args.verbose)
    progress(f"Loading {args.input}...")
    dims = load(args.input)
    progress("CSV loaded; starting layout...")
    draw(dims, args.output, mono_enum=args.mono_enum, progress=progress)
    progress("Done.")
    print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()

