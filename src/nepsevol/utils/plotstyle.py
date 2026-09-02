"""Figure style for journal submission.

Colours come from a validated categorical palette (CVD-safe: worst adjacent
protan dE 9.1, normal-vision dE 19.6). Every series also carries a distinct
linestyle and marker, so identity never rests on colour alone -- which satisfies
the accessibility rule and keeps the figures legible in the greyscale printing
many finance journals still use.
"""
import matplotlib as mpl
import matplotlib.pyplot as plt

SERIES = {
    "blue":    "#2a78d6",
    "orange":  "#eb6834",
    "aqua":    "#1baf7a",
    "yellow":  "#eda100",
    "magenta": "#e87ba4",
    "green":   "#008300",
    "violet":  "#4a3aa7",
    "red":     "#e34948",
}
INK        = "#0b0b0b"
INK_SOFT   = "#52514e"
INK_MUTED  = "#8a8880"
GRID       = "#e3e2dd"
SURFACE    = "#fcfcfb"

# estimator -> (colour, linestyle, marker). Fixed order, never cycled.
STYLE = {
    "Close-to-close":   (SERIES["blue"],    "-",   "o"),
    "Parkinson":        (SERIES["orange"],  "--",  "s"),
    "Garman-Klass":     (SERIES["aqua"],    "-.",  "^"),
    "Rogers-Satchell":  (SERIES["yellow"],  ":",   "D"),
    "GKYZ":             (SERIES["magenta"], (0,(3,1,1,1)), "v"),
    "Yang-Zhang":       (SERIES["green"],   (0,(5,1)),     "P"),
}


def apply():
    mpl.rcParams.update({
        "figure.facecolor": SURFACE, "axes.facecolor": SURFACE,
        "savefig.facecolor": SURFACE, "savefig.bbox": "tight", "savefig.dpi": 300,
        "font.family": "sans-serif",
        "font.sans-serif": ["Helvetica Neue", "Helvetica", "Arial", "DejaVu Sans"],
        "font.size": 9, "axes.titlesize": 10, "axes.labelsize": 9,
        "legend.fontsize": 8, "xtick.labelsize": 8, "ytick.labelsize": 8,
        "axes.edgecolor": INK_MUTED, "axes.linewidth": 0.6,
        "axes.labelcolor": INK, "text.color": INK,
        "xtick.color": INK_SOFT, "ytick.color": INK_SOFT,
        "xtick.major.width": 0.6, "ytick.major.width": 0.6,
        "axes.grid": True, "grid.color": GRID, "grid.linewidth": 0.5, "grid.alpha": 1.0,
        "axes.spines.top": False, "axes.spines.right": False,
        "legend.frameon": False, "lines.linewidth": 1.6, "lines.markersize": 4.5,
        "figure.autolayout": False,
    })


def finish(ax, title=None, sub=None, xlabel=None, ylabel=None):
    """Title block above the plot, in ink tokens rather than series colour."""
    if title:
        ax.set_title(title, loc="left", pad=14 if sub else 8,
                     fontweight="bold", color=INK)
    if sub:
        ax.text(0, 1.015, sub, transform=ax.transAxes, ha="left", va="bottom",
                fontsize=8, color=INK_SOFT)
    if xlabel: ax.set_xlabel(xlabel)
    if ylabel: ax.set_ylabel(ylabel)
    ax.set_axisbelow(True)


def header(fig, title, sub=None, top=0.84):
    """Figure-level title block that never collides with the axes.

    Reserves space via tight_layout(rect=...) first, then places the text in the
    reserved band -- rather than letting suptitle and a text call fight for the
    same y.
    """
    fig.tight_layout(rect=[0, 0, 1, top])
    y = 0.995
    fig.text(0.0, y, title, ha="left", va="top",
             fontsize=10.5, fontweight="bold", color=INK)
    if sub:
        fig.text(0.0, y - (1 - top) * 0.42, sub, ha="left", va="top",
                 fontsize=8, color=INK_SOFT)


def plain_log_axis(ax, which="x"):
    """Plain numerals on a log axis (1, 10, 100) instead of 10^0, 10^1."""
    import matplotlib.ticker as mt
    axis = ax.xaxis if which == "x" else ax.yaxis
    axis.set_major_formatter(mt.FuncFormatter(lambda v, _: f"{v:,.0f}" if v >= 1 else f"{v:g}"))
    axis.set_minor_formatter(mt.NullFormatter())
