"""The report's PNG charts (session M3.0). Layout and colours come from layout.yaml.

Every image written while the results are mock carries a red banner across the top and a large diagonal
watermark, and records the banner text in the PNG's metadata so a test can check it.
"""

import matplotlib

matplotlib.use("Agg")      # draw to files only; no window
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import Rectangle  # noqa: E402

from analysis.results_schema import OPTION_C_POLICIES, RELEASED, UPTAKE, comparison_sides, num  # noqa: E402

plt.rcParams.update({"font.family": "DejaVu Sans", "font.size": 9, "hatch.linewidth": 0.8})


def save(fig, path, banner):
    """Write a figure. With a banner (mock results), stamp it on the image and in the PNG metadata.

    A release banner (Clarification 31: v0.1) comes as {"text", "colour"}: a band across the top and the same
    PNG metadata, without the mock watermark.
    """
    if isinstance(banner, dict):
        fig.text(0.5, 0.995, banner["text"], ha="center", va="top", fontsize=11, color="white", weight="bold",
                 bbox={"facecolor": banner["colour"], "edgecolor": "none", "pad": 4}, zorder=101)
        fig.savefig(path, dpi=130, metadata={"Description": banner["text"]})
        plt.close(fig)
        return
    if banner:
        fig.text(0.5, 0.5, banner, rotation=28, ha="center", va="center", fontsize=34, color="#C00000",
                 alpha=0.16, weight="bold", zorder=100)
        fig.text(0.5, 0.995, banner, ha="center", va="top", fontsize=12, color="white", weight="bold",
                 bbox={"facecolor": "#C00000", "edgecolor": "none", "pad": 4}, zorder=101)
    fig.savefig(path, dpi=130, metadata={"Description": banner or "results"})
    plt.close(fig)


def bw_copy(path):
    """A greyscale copy, so anyone can check a chart still reads in black and white."""
    img = plt.imread(path)[..., :3]
    grey = img @ np.array([0.299, 0.587, 0.114])
    out = path.with_name(path.stem + "_bw.png")
    plt.imsave(out, grey, cmap="gray", vmin=0, vmax=1)
    return out


def _marker_x(stigma_grid, value):
    """Where a stigma value falls on the evenly spaced grid columns (the grid itself is uneven)."""
    return float(np.interp(value, stigma_grid, np.arange(len(stigma_grid))))


def tradeoff_figure(rows, vocab, layout, marker, title, path, banner):
    """One panel per comparison: supervision (rows) x market stigma (columns)."""
    t = layout["tradeoff"]
    pol = layout["policy_labels"]
    stig, sup = vocab["stigma"], vocab["supervision"]
    comps = t["comparisons"]
    fig, axes = plt.subplots(4, 2, figsize=(15, 19))
    fig.subplots_adjust(top=0.91 if marker else 0.93, bottom=0.03, left=0.11, right=0.98, hspace=0.5, wspace=0.34)
    fig.suptitle(title, fontsize=14, y=0.965)
    by_key = {(r["comparison"], float(r["stigma"]), r["supervision"]): r for r in rows}
    for ax, comp in zip(axes.flat, comps):
        x, y = (pol[s] for s in comparison_sides(comp))
        names = {"x_leads": f"{x} leads", "y_leads": f"{y} leads", "tie": "tie", "trade_off": "trade-off"}
        for i, u in enumerate(sup):
            for j, s in enumerate(stig):
                r = by_key[(comp, float(s), u)]
                lab = r["label"]
                ax.add_patch(Rectangle((j, i), 1, 1, facecolor=t["colours"][lab], hatch=t["hatch"][lab] or None,
                                       edgecolor="#555555", linewidth=0.6))
                cost = num(r["cost_diff_m"])
                # Text sits on a patch of the cell's own colour (white on hatched cells) so hatching and the
                # marker line never run through the words.
                ax.text(j + 0.5, i + 0.5, f"{names[lab]}\n{cost:+.0f} $m", ha="center", va="center", fontsize=7,
                        color=t["text_colour"][lab], zorder=5,
                        bbox={"facecolor": "white" if t["hatch"][lab] else t["colours"][lab], "edgecolor": "none", "pad": 0.6})
        ax.set_xlim(0, len(stig))
        ax.set_ylim(len(sup), 0)
        ax.set_xticks(np.arange(len(stig)) + 0.5, [f"{s:g}" for s in stig])
        ax.set_yticks(np.arange(len(sup)) + 0.5, [t["supervision_labels"][u] for u in sup])
        ax.set_xlabel("Market stigma: chance a known draw is read as distress")
        ax.set_title(f"{x} vs {y}   (cost difference = {x} minus {y}, $m per bank per year)", fontsize=10,
                     pad=30 if marker else 18)
        if marker:
            mx = _marker_x(stig, marker["stigma"]) + 0.5
            ax.axvline(mx, color=t["marker_colour"], linestyle="--", linewidth=2, zorder=3)
            # Two lines, ending at the marker line, so a long label stays inside the panel (display only;
            # amendments note of 2026-10-09 under Amendment 8).
            first, _, rest = marker["label"].partition(" (")
            text = f"{first}\n({rest} ({marker['stigma']:g}) ▼" if rest else f"{first} ({marker['stigma']:g}) ▼"
            ax.text(mx, 1.005, text, ha="right", va="bottom", multialignment="right",
                    fontsize=8, weight="bold", transform=ax.get_xaxis_transform())
    legend = axes.flat[-1]
    legend.axis("off")
    for k, (lab, text) in enumerate([("x_leads", "X leads (first-named policy)"), ("y_leads", "Y leads (second-named policy)"),
                                     ("tie", "Tie"), ("trade_off", "Trade-off against cost")]):
        legend.add_patch(Rectangle((0.05, 0.8 - k * 0.17), 0.12, 0.12, facecolor=t["colours"][lab],
                                   hatch=t["hatch"][lab] or None, edgecolor="#555555", transform=legend.transAxes))
        legend.text(0.22, 0.86 - k * 0.17, text, va="center", fontsize=11, transform=legend.transAxes)
    legend.text(0.05, 0.1, "Leads: at least as good on survival and shortfall, with at least one\n90% interval "
                "excluding zero (contract 4). No dollar value per failure.", fontsize=9, transform=legend.transAxes)
    if not marker:
        legend.text(0.05, -0.05, t["no_marker_note"], fontsize=9, style="italic", transform=legend.transAxes, wrap=True)
    save(fig, path, banner)


def frontier_figure(rows, vocab, layout, title, path, banner):
    """Survival and shortfall against annual cost, one point per policy with its interval, per bank type."""
    st, pol = layout["policy_style"], layout["policy_labels"]
    types = vocab["bank_types"]
    fig, axes = plt.subplots(2, len(types), figsize=(17, 9))
    fig.subplots_adjust(top=0.86, bottom=0.12, left=0.06, right=0.98, hspace=0.35, wspace=0.28)
    fig.suptitle(title, fontsize=14, y=0.94)
    for col, b in enumerate(types):
        for row, (k, lo, hi, ylabel) in enumerate((("survival", "survival_lo", "survival_hi", "Survival rate"),
                                                   ("shortfall_bn", "shortfall_lo", "shortfall_hi", "Liquidity shortfall ($bn)"))):
            ax = axes[row, col]
            for r in (r for r in rows if r["bank_type"] == b):
                p = r["policy"]
                cx, cy = num(r["cost_m"]), num(r[k])
                ax.errorbar(cx, cy, xerr=[[cx - num(r["cost_lo"])], [num(r["cost_hi"]) - cx]],
                            yerr=[[cy - num(r[lo])], [num(r[hi]) - cy]], fmt=st[p]["marker"], color=st[p]["colour"],
                            markersize=8, markeredgecolor="black", capsize=3, label=pol[p])
                ax.annotate(pol[p], (cx, cy), textcoords="offset points", xytext=(7, 5), fontsize=9, weight="bold")
            ax.axvline(0, color="#999999", linewidth=0.8)
            ax.set_xlabel("Annual cost vs A ($m per bank per year)")
            ax.set_ylabel(ylabel)
            ax.set_title(vocab["bank_labels"][b], fontsize=10)
            ax.grid(alpha=0.3)
    handles, labels = axes[0, 0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="lower center", ncol=len(labels), frameon=False, fontsize=10)
    save(fig, path, banner)


def option_c_figure(rows, vocab, layout, title, path, banner):
    """Uptake x HQLA released for C and C′: survival difference vs A in each run cell, cost below it."""
    pol, oc = layout["policy_labels"], layout["option_c"]
    types = vocab["bank_types"]
    fig, axes = plt.subplots(len(OPTION_C_POLICIES), len(types), figsize=(17, 9))
    fig.subplots_adjust(top=0.86, bottom=0.1, left=0.07, right=0.93, hspace=0.45, wspace=0.3)
    fig.suptitle(title, fontsize=14, y=0.94)
    vals = [abs(num(r["survival_diff"])) for r in rows if r["run"] == "true"]
    lim = max(vals) if vals else 1
    cmap = plt.get_cmap(oc["colour_map"])
    for i, p in enumerate(OPTION_C_POLICIES):
        for j, b in enumerate(types):
            ax = axes[i, j]
            for r in (r for r in rows if r["policy"] == p and r["bank_type"] == b):
                xi, yi = UPTAKE.index(float(r["uptake"])), RELEASED.index(float(r["hqla_released"]))
                if r["run"] == "true":
                    d = num(r["survival_diff"])
                    ax.add_patch(Rectangle((xi, yi), 1, 1, facecolor=cmap(0.5 + 0.5 * d / lim), edgecolor="black"))
                    ax.text(xi + 0.5, yi + 0.5, f"{d:+.2f}\n[{num(r['survival_lo']):+.2f}, {num(r['survival_hi']):+.2f}]\n"
                            f"cost {num(r['cost_m']):+.0f} $m", ha="center", va="center", fontsize=7,
                            bbox={"facecolor": "white", "edgecolor": "none", "alpha": 0.75, "pad": 1})
                else:
                    ax.add_patch(Rectangle((xi, yi), 1, 1, facecolor="#F2F2F2", hatch="xx", edgecolor="#AAAAAA"))
                    ax.text(xi + 0.5, yi + 0.5, "not run", ha="center", va="center", fontsize=8, color="#555555")
            ax.set_xlim(0, 3)
            ax.set_ylim(0, 3)
            ax.set_xticks(np.arange(3) + 0.5, [f"{u:.0%}" for u in UPTAKE])
            ax.set_yticks(np.arange(3) + 0.5, [f"{h:.0%}" for h in RELEASED])
            ax.set_xlabel("Voluntary uptake")
            ax.set_ylabel("HQLA released (share of credit)")
            ax.set_title(f"{pol[p]} — {vocab['bank_labels'][b]}", fontsize=10)
    fig.text(0.5, 0.02, "Each run cell: survival difference vs A [90% interval], and annual cost vs A. "
             + oc["not_run_note"][0].upper() + oc["not_run_note"][1:] + ".", ha="center", fontsize=9)
    save(fig, path, banner)
