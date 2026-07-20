#!/usr/bin/env python3
"""Generate a Gioia-style data structure diagram (Gioia et al. 2013) from a CSV.

CSV columns: first_order_concept,second_order_theme,aggregate_dimension
Hierarchy is M:1 .. M:1.

Usage: python gioia.py input.csv output.pdf
"""

import csv
import sys
from collections import OrderedDict

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, Ellipse, PathPatch
from matplotlib.path import Path
from matplotlib.patheffects import withSimplePatchShadow
from matplotlib.textpath import TextPath
from matplotlib.transforms import IdentityTransform


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
def _text_width_pts(s, fontsize, weight):
    """Width of a string in points (TextPath size is in points)."""
    if not s:
        return 0.0
    tp = TextPath((0, 0), s, size=fontsize, prop={"weight": weight})
    return tp.get_extents().width


def _hard_break_word(word, fontsize, weight, max_pts):
    """Break a single word that is wider than max_pts into pieces that fit."""
    pieces, cur = [], ""
    for ch in word:
        if _text_width_pts(cur + ch, fontsize, weight) <= max_pts or not cur:
            cur += ch
        else:
            pieces.append(cur)
            cur = ch
    if cur:
        pieces.append(cur)
    return pieces


def wrap(text, fontsize, weight, max_pts):
    """Greedy word wrap to a width given in points. Returns list of lines.

    Words wider than max_pts are hard-broken so text never bleeds outside
    its container.
    """
    words = text.split()
    if not words:
        return [""]
    # Pre-split any word too wide to ever fit on one line.
    tokens = []
    for w in words:
        if _text_width_pts(w, fontsize, weight) > max_pts:
            tokens.extend(_hard_break_word(w, fontsize, weight, max_pts))
        else:
            tokens.append(w)

    lines, cur = [], tokens[0]
    for w in tokens[1:]:
        trial = cur + " " + w
        if _text_width_pts(trial, fontsize, weight) <= max_pts:
            cur = trial
        else:
            lines.append(cur)
            cur = w
    lines.append(cur)
    return lines


def letters(i):
    """0->A, 1->B ... cycles A..Z."""
    return chr(ord("A") + (i % 26))


# ---------------------------------------------------------------------------
# Main drawing
# ---------------------------------------------------------------------------
def draw(dims, out_path):
    # ---- Layout constants (in figure "data" units == points-ish) ----
    FIG_W = 13.0                     # inches
    DPI = 150

    # Column geometry (x in axis units 0..100)
    P1_X, P1_W = 2.0, 34.0           # first-order concepts panel
    P2_X, P2_W = 44.0, 22.0          # second-order themes panel
    P3_X, P3_W = 74.0, 22.0          # aggregate dimensions panel
    PANEL_PAD = 1.5

    BOX_PAD_X = 1.2                  # horizontal text inset (axis units)
    LINE_H = 2.1                     # per text line height (axis units)
    BLOCK_GAP = 1.6                  # vertical gap between theme-blocks
    DIM_GAP = 3.0                    # extra gap between dimension groups
    TOP_MARGIN = 6.0                 # below headings
    BOTTOM_MARGIN = 3.0

    FS_FOC = 8.5
    FS_THEME = 9.0
    FS_DIM = 9.5
    FS_HEAD = 12.0

    GREY_PANEL = "#e6e6e6"
    SHADOW = withSimplePatchShadow(offset=(2, -2), alpha=0.35)

    # figure setup (guess height, refine after measuring)
    fig = plt.figure(figsize=(FIG_W, 16), dpi=DPI)
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 100)
    ax.axis("off")

    # ---- Measure text -> compute each theme block's line lists & heights ----
    # The x-axis spans 100 units over FIG_W inches (= FIG_W * 72 points).
    # Convert an available axis-x width into points so wrap() (which measures
    # glyphs in points via TextPath) is unit-consistent -> no bleed.
    PTS_PER_AXIS_X = FIG_W * 72.0 / 100.0

    def text_budget_pts(panel_w_axis, pad_axis):
        return (panel_w_axis - 2 * pad_axis) * PTS_PER_AXIS_X

    foc_text_pts = text_budget_pts(P1_W, BOX_PAD_X)
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
            # first-order concept lines with enumeration
            foc_lines = []
            for j, c in enumerate(concepts):
                label = f"{theme_seq}{letters(j)}. {c}"
                foc_lines.extend(wrap(label, FS_FOC, "normal", foc_text_pts))
            theme_lines = wrap(theme, FS_THEME, "bold", theme_text_pts)

            h_foc = len(foc_lines) * LINE_H + 1.6
            h_theme = len(theme_lines) * LINE_H + 1.6
            h = max(h_foc, h_theme)   # equal height rule
            dim_blocks.append({
                "theme": theme,
                "theme_lines": theme_lines,
                "foc_lines": foc_lines,
                "h": h,
            })
        blocks.append({"dim": dim, "theme_blocks": dim_blocks})

    # ---- Compute total content height ----
    total_h = 0.0
    for i, grp in enumerate(blocks):
        for b in grp["theme_blocks"]:
            total_h += b["h"] + BLOCK_GAP
        total_h += DIM_GAP
    total_h += TOP_MARGIN + BOTTOM_MARGIN

    # set y-limits and refine figure height to keep boxes square-ish
    ax.set_ylim(0, total_h)
    fig_h = FIG_W * (total_h / 100.0) * (100.0 / 100.0)
    # scale figure height proportional to content
    fig_h = FIG_W * total_h / (P1_W + P2_W + P3_W + 20)
    fig_h = max(6.0, total_h * FIG_W / 100.0)
    fig.set_size_inches(FIG_W, fig_h)

    # ---- Panels ----
    panels = [
        (P1_X - PANEL_PAD, P1_W + 2 * PANEL_PAD, "First-order concepts"),
        (P2_X - PANEL_PAD, P2_W + 2 * PANEL_PAD, "Second-order themes"),
        (P3_X - PANEL_PAD, P3_W + 2 * PANEL_PAD, "Aggregate dimensions"),
    ]
    for px, pw, head in panels:
        ax.add_patch(plt.Rectangle((px, 0), pw, total_h,
                                   facecolor=GREY_PANEL, edgecolor="none", zorder=0))
        ax.text(px + pw / 2, total_h - TOP_MARGIN / 2 + 1.0, head,
                ha="center", va="center", fontsize=FS_HEAD, fontweight="bold",
                zorder=5)

    # ---- Helper: rounded box with wrapped text (centered or left-aligned) ----
    def box(x, y_top, w, h, lines, fontsize, weight, align="center"):
        p = FancyBboxPatch(
            (x, y_top - h), w, h,
            boxstyle="round,pad=0,rounding_size=0.6",
            facecolor="white", edgecolor="black", linewidth=1.0, zorder=3)
        p.set_path_effects([SHADOW])
        ax.add_patch(p)
        cy = y_top - h / 2
        block_h = len(lines) * LINE_H
        start = cy + block_h / 2 - LINE_H / 2
        if align == "left":
            tx, ha = x + BOX_PAD_X, "left"
        else:
            tx, ha = x + w / 2, "center"
        for k, ln in enumerate(lines):
            ax.text(tx, start - k * LINE_H, ln, ha=ha, va="center",
                    fontsize=fontsize, fontweight=weight, zorder=4)
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
    y = total_h - TOP_MARGIN
    dim_centers = []   # (dim_name, y_center, span_top, span_bottom)

    for grp in blocks:
        grp_top = y
        theme_y_centers = []
        for b in grp["theme_blocks"]:
            h = b["h"]
            top = y
            # first-order concept box (panel 1) — left-aligned text
            box(P1_X, top, P1_W, h, b["foc_lines"], FS_FOC, "normal",
                align="left")
            # second-order theme box (panel 2)
            box(P2_X, top, P2_W, h, b["theme_lines"], FS_THEME, "bold")
            # grey arrow from panel1 -> panel2
            grey_arrow(P1_X + P1_W + 0.5, top - h / 2, P2_X - 0.5)
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
    dim_line_map = {dim: wrap(dim, FS_DIM, "bold", dim_text_pts)
                    for (dim, _, _) in dim_centers}
    OVAL_W = P3_W - 1.0
    # Height accommodates the wordiest label; kept identical for every oval.
    max_dim_lines = max(len(lines) for lines in dim_line_map.values())
    oval_h = max(max_dim_lines * LINE_H + 4.0, 8.0)

    for (dim, dim_cy, theme_y_centers), grp in zip(dim_centers, blocks):
        dim_lines = dim_line_map[dim]
        cx = P3_X + P3_W / 2
        el = Ellipse((cx, dim_cy), OVAL_W, oval_h,
                     facecolor="black", edgecolor="black", zorder=3)
        el.set_path_effects([SHADOW])
        ax.add_patch(el)
        block_h = len(dim_lines) * LINE_H
        start = dim_cy + block_h / 2 - LINE_H / 2
        for k, ln in enumerate(dim_lines):
            ax.text(cx, start - k * LINE_H, ln, ha="center", va="center",
                    color="white", fontsize=FS_DIM, fontweight="bold", zorder=4)
        # connectors: theme right edge -> oval left edge
        for ty in theme_y_centers:
            ax.plot([P2_X + P2_W, P3_X], [ty, dim_cy],
                    color="black", linewidth=1.0, zorder=2)

    fig.savefig(out_path, dpi=DPI, bbox_inches="tight")
    plt.close(fig)


def main():
    if len(sys.argv) != 3:
        print("Usage: python gioia.py input.csv output.pdf")
        sys.exit(1)
    dims = load(sys.argv[1])
    draw(dims, sys.argv[2])
    print(f"Wrote {sys.argv[2]}")


if __name__ == "__main__":
    main()

