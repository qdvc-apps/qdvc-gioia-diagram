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
def _text_width_px(fig, s, fontsize, weight):
    tp = TextPath((0, 0), s, size=fontsize, prop={"weight": weight})
    return tp.get_extents().width


def wrap(fig, text, fontsize, weight, max_px):
    """Greedy word wrap to a pixel width. Returns list of lines."""
    words = text.split()
    if not words:
        return [""]
    lines, cur = [], words[0]
    for w in words[1:]:
        trial = cur + " " + w
        if _text_width_px(fig, trial, fontsize, weight) <= max_px:
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
    # width available for wrapped text inside a panel box (pixels)
    def px_per_axis_x(panel_w_axis):
        # convert axis-x units to pixels: fig width px * (panel_w/100)
        return FIG_W * DPI * (panel_w_axis / 100.0)

    foc_text_px = px_per_axis_x(P1_W) - px_per_axis_x(2 * BOX_PAD_X)
    theme_text_px = px_per_axis_x(P2_W) - px_per_axis_x(2 * BOX_PAD_X)
    dim_text_px = px_per_axis_x(P3_W) - px_per_axis_x(2 * BOX_PAD_X)

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
                foc_lines.extend(wrap(fig, label, FS_FOC, "normal", foc_text_px))
            theme_lines = wrap(fig, theme, FS_THEME, "bold", theme_text_px)

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

    # ---- Helper: rounded box with centered wrapped text ----
    def box(x, y_top, w, h, lines, fontsize, weight):
        p = FancyBboxPatch(
            (x, y_top - h), w, h,
            boxstyle="round,pad=0,rounding_size=0.6",
            facecolor="white", edgecolor="black", linewidth=1.0, zorder=3)
        p.set_path_effects([SHADOW])
        ax.add_patch(p)
        cy = y_top - h / 2
        block_h = len(lines) * LINE_H
        start = cy + block_h / 2 - LINE_H / 2
        for k, ln in enumerate(lines):
            ax.text(x + w / 2, start - k * LINE_H, ln, ha="center", va="center",
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
            # first-order concept box (panel 1)
            box(P1_X, top, P1_W, h, b["foc_lines"], FS_FOC, "normal")
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
    for (dim, dim_cy, theme_y_centers), grp in zip(dim_centers, blocks):
        dim_lines = wrap(fig, dim, FS_DIM, "bold", dim_text_px)
        span = theme_y_centers[0] - theme_y_centers[-1]
        oval_h = max(len(dim_lines) * LINE_H + 3.0, span * 0.6 + 3.0)
        cx = P3_X + P3_W / 2
        el = Ellipse((cx, dim_cy), P3_W - 1.0, oval_h,
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

