"""
Figures for the report (PNG, results/figures/). No API calls; reads the result tables only.

  fig1_primary_contrasts.png   the 12 pre-registered contrasts with Bonferroni-adjusted CIs, in option steps
  fig2_effect_matrix.png       every intervention x measure, mode none vs high (targeting and spillover)
  fig3_reason_groups.png       stated rule (label group) by condition, item type and mode
  fig4_execution.png           reasons stating an EV rule: share of valid responses whose behavior is EV-consistent

Inputs: results/tables/main_contrasts.csv, results/reasons/step4/t1_labels_by_cell.csv,
results/reasons/step4/t4_behavior_by_label.csv.

Colors: the validated reference palette of the dataviz method (categorical slots in fixed order; a
blue-gray-red diverging scale for signed effects). Mode none / high are always slot 1 / slot 2.

Usage:
  python src/make_figures.py
"""

import csv
import math

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt                     # noqa: E402
from matplotlib.colors import LinearSegmentedColormap, TwoSlopeNorm   # noqa: E402
from matplotlib.patches import Patch, Rectangle     # noqa: E402

from llm import ROOT                                # noqa: E402

SURFACE, INK, INK2, MUTED, GRID = "#fcfcfb", "#0b0b0b", "#52514e", "#898781", "#e1e0d9"
SLOT = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4", "#008300"]
MODE_COLOR = {"none": SLOT[0], "high": SLOT[1]}
MODE_NAME = {"none": "reasoning none", "high": "reasoning high"}
STEP = {"rp_range": 1 / 11, "log_ratio": math.log(10) / 11}
CONDITIONS = ["direct_risk_tech", "direct_risk_plain", "oneshot_gain", "direct_loss_tech", "direct_loss_plain",
              "oneshot_loss", "oneshot_mixed", "cot", "ev_hint"]
MEASURES = [("gain", "rp_range", "Gain RP"), ("loss", "rp_range", "Loss RP"), ("mixed", "log_ratio", "Mixed ratio")]
TARGET = {"direct_risk_tech": "gain", "direct_risk_plain": "gain", "oneshot_gain": "gain",
          "direct_loss_tech": "mixed", "direct_loss_plain": "mixed", "oneshot_loss": "loss", "oneshot_mixed": "mixed"}
GROUPS = ["EV", "risk averse", "loss averse", "risk seeking", "vague tradeoff", "other"]
OUT = ROOT / "results" / "figures"

plt.rcParams.update({
    "figure.facecolor": SURFACE, "axes.facecolor": SURFACE, "savefig.facecolor": SURFACE,
    "font.size": 9, "axes.edgecolor": GRID, "axes.labelcolor": INK2, "axes.titlecolor": INK,
    "xtick.color": MUTED, "ytick.color": INK2, "axes.titlesize": 10, "axes.titleweight": "bold",
    "axes.spines.top": False, "axes.spines.right": False, "legend.frameon": False,
})


def read(path):
    with open(path, encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def save(fig, name):
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / name, dpi=200, bbox_inches="tight")
    plt.close(fig)
    print("wrote", (OUT / name).relative_to(ROOT))


def fig1(contrasts):
    rows = sorted([r for r in contrasts if r["primary"]], key=lambda r: int(r["primary"][1:]))
    fig, ax = plt.subplots(figsize=(7.2, 4.6))
    ax.axvspan(-0.5, 0.5, color=GRID, alpha=0.6, lw=0, zorder=0)
    ax.axvline(0, color=MUTED, lw=1, zorder=1)
    for i, r in enumerate(rows):
        step = STEP[r["outcome"]]
        lo, hi, est = float(r["ci_adj_low"]) / step, float(r["ci_adj_high"]) / step, float(r["estimate_steps"])
        c = MODE_COLOR[r["mode"]]
        ax.plot([lo, hi], [i, i], color=c, lw=2, solid_capstyle="round", zorder=2)
        ax.scatter([est], [i], s=36, color=c, edgecolor=SURFACE, linewidth=1.5, zorder=3)
        ax.text(max(hi, est) + 0.15, i, r["conclusion"].replace("effect as predicted", "as predicted"),
                va="center", fontsize=7.5, color=INK2)
    labels = [f"{r['primary']}  {r['condition']} · {dict((m[0], m[2]) for m in MEASURES)[r['item_type']]}"
              for r in rows]
    ax.set_yticks(range(len(rows)), labels)
    ax.invert_yaxis()
    ax.tick_params(axis="y", length=0)
    ax.set_xlim(-2.3, 7.2)
    ax.set_xlabel("Change vs. baseline (option steps); shaded: within half a step")
    ax.grid(axis="x", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.set_title("Pre-registered contrasts (Bonferroni-adjusted 99.6% CI)", loc="left")
    ax.legend(handles=[Patch(color=MODE_COLOR[m], label=MODE_NAME[m]) for m in ("none", "high")],
              loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=8, ncol=2)
    save(fig, "fig1_primary_contrasts.png")


def text_color(rgba):
    r, g, b = rgba[:3]
    return INK if 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.55 else "#ffffff"


def fig2(contrasts):
    cmap = LinearSegmentedColormap.from_list("div", ["#1c5cab", "#86b6ef", "#f0efec", "#f19a98", "#c0302f"])
    norm = TwoSlopeNorm(vmin=-4, vcenter=0, vmax=4)
    est = {(r["mode"], r["condition"], r["item_type"]): float(r["estimate_steps"])
           for r in contrasts if r["outcome"] in ("rp_range", "log_ratio") and r["estimate_steps"]}
    concl = {(r["mode"], r["condition"], r["item_type"]): r["conclusion"]
             for r in contrasts if r["outcome"] in ("rp_range", "log_ratio")}
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 4.8), sharey=True)
    for ax, mode in zip(axes, ("none", "high")):
        conds = [c for c in CONDITIONS if c != "ev_hint" or mode == "none"]
        for i, cond in enumerate(conds):
            for j, (itype, _, _) in enumerate(MEASURES):
                v = est.get((mode, cond, itype))
                if v is None:
                    ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=SURFACE, edgecolor=GRID, lw=0.8))
                    ax.text(j, i, "not run", ha="center", va="center", fontsize=7, color=MUTED)
                    continue
                col = cmap(norm(max(-4, min(4, v))))
                ax.add_patch(Rectangle((j - 0.5, i - 0.5), 1, 1, facecolor=col, edgecolor=SURFACE, lw=2))
                weak = concl.get((mode, cond, itype)) in ("no meaningful effect", "inconclusive")
                ax.text(j, i, f"{v:+.1f}" + ("" if not weak else "*"), ha="center", va="center", fontsize=8,
                        color=text_color(col), fontweight="normal" if weak else "bold")
            if cond in TARGET:
                j = [m[0] for m in MEASURES].index(TARGET[cond])
                ax.add_patch(Rectangle((j - 0.47, i - 0.47), 0.94, 0.94, fill=False, edgecolor=INK, lw=1.4))
        ax.set_xlim(-0.5, 2.5)
        ax.set_ylim(len(CONDITIONS) - 0.5, -0.5)
        ax.set_xticks(range(3), [m[2] for m in MEASURES])
        ax.set_yticks(range(len(CONDITIONS)), CONDITIONS)
        ax.tick_params(length=0)
        for s in ax.spines.values():
            s.set_visible(False)
        ax.set_title(MODE_NAME[mode], loc="left")
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    cb = fig.colorbar(sm, ax=axes, fraction=0.03, pad=0.02, ticks=[-4, -2, 0, 2, 4])
    cb.set_label("Change vs. baseline (option steps; capped at ±4)", color=INK2)
    cb.outline.set_visible(False)
    fig.suptitle("Effects of each intervention on every measure", x=0.02, ha="left", fontweight="bold", color=INK)
    fig.text(0.02, -0.02, "Outlined: the measure the intervention targets. * = no meaningful effect or "
             "inconclusive (95% CI; adjusted CI for the 12 primary contrasts).", fontsize=7.5, color=INK2)
    save(fig, "fig2_effect_matrix.png")


def group_shares(row):
    s = {k: float(row[k]) for k in ("EV", "EV + risk averse", "risk averse", "loss averse", "risk seeking",
                                    "vague tradeoff", "other")}
    mixed = row["item_type"] == "mixed"
    return {"EV": s["EV"], "risk averse": s["EV + risk averse"] + s["risk averse"] + (0 if mixed else s["loss averse"]),
            "loss averse": s["loss averse"] if mixed else 0.0, "risk seeking": s["risk seeking"],
            "vague tradeoff": s["vague tradeoff"], "other": s["other"]}


def fig3(t1):
    cells = {(r["mode"], r["condition"], r["item_type"]): group_shares(r) for r in t1}
    conds = ["baseline"] + CONDITIONS
    fig, axes = plt.subplots(2, 3, figsize=(8.6, 6.0), sharex=True, sharey=True)
    for a, mode in enumerate(("none", "high")):
        for b, (itype, _, name) in enumerate(MEASURES):
            ax = axes[a][b]
            for i, cond in enumerate(conds):
                sh = cells.get((mode, cond, itype))
                if sh is None:
                    ax.text(0.01, i, "not run", va="center", fontsize=7, color=MUTED)
                    continue
                left = 0.0
                for g, col in zip(GROUPS, SLOT):
                    w = sh[g]
                    if w > 0:
                        ax.barh(i, w, left=left, height=0.7, color=col, edgecolor=SURFACE, linewidth=1)
                    left += w
            ax.set_ylim(len(conds) - 0.5, -0.5)
            ax.set_xlim(0, 1)
            ax.set_yticks(range(len(conds)), conds)
            ax.set_xticks([0, 0.5, 1], ["0%", "50%", "100%"])
            ax.tick_params(axis="y", length=0)
            ax.spines["left"].set_visible(False)
            ax.set_title(f"{name.split()[0]} items · {MODE_NAME[mode]}", loc="left", fontsize=9)
    fig.legend(handles=[Patch(color=c, label=g) for g, c in zip(GROUPS, SLOT)], loc="lower center",
               ncol=6, fontsize=8, bbox_to_anchor=(0.5, -0.03))
    fig.suptitle("Stated decision rule (LLM-labeled Reason line), share of responses", x=0.02, ha="left",
                 fontweight="bold", color=INK)
    fig.text(0.02, -0.07, "risk averse includes EV + risk averse and, on gain/loss items, 'loss averse' "
             "wording. other = no usable rule (unreliable label, < 0.2% of responses).", fontsize=7.5, color=INK2)
    fig.tight_layout()
    save(fig, "fig3_reason_groups.png")


def fig4(t4):
    vals = {(r["mode"], r["item_type"]): (float(r["share_ev_consistent"]), int(r["n"]))
            for r in t4 if r["label"] == "EV"}
    fig, ax = plt.subplots(figsize=(5.6, 3.2))
    width = 0.36
    for k, mode in enumerate(("none", "high")):
        for j, (itype, _, name) in enumerate(MEASURES):
            share, n = vals[(mode, itype)]
            x = j + (k - 0.5) * width
            ax.bar(x, share, width=width - 0.04, color=MODE_COLOR[mode], edgecolor=SURFACE, linewidth=1)
            ax.text(x, share + 0.02, f"{share:.0%}", ha="center", va="bottom", fontsize=8, color=INK)
            ax.text(x, 0.02, f"n={n}", ha="center", va="bottom", fontsize=6.5,
                    color="#ffffff" if mode == "none" else INK)
    ax.set_xticks(range(3), [f"{m[2].split()[0]} items" for m in MEASURES])
    ax.set_ylim(0, 1.08)
    ax.set_yticks([0, 0.5, 1], ["0%", "50%", "100%"])
    ax.grid(axis="y", color=GRID, lw=0.6)
    ax.set_axisbelow(True)
    ax.tick_params(axis="x", length=0)
    ax.legend(handles=[Patch(color=MODE_COLOR[m], label=MODE_NAME[m]) for m in ("none", "high")],
              loc="upper center", bbox_to_anchor=(0.5, -0.12), fontsize=8, ncol=2)
    ax.set_title("Reasons stating an EV rule: behavior consistent with EV", loc="left")
    fig.text(0.0, -0.14, "Valid responses only. EV-consistent: the switch interval contains the expected value.",
             fontsize=7.5, color=INK2)
    save(fig, "fig4_execution.png")


def main():
    contrasts = read(ROOT / "results" / "tables" / "main_contrasts.csv")
    fig1(contrasts)
    fig2(contrasts)
    fig3(read(ROOT / "results" / "reasons" / "step4" / "t1_labels_by_cell.csv"))
    fig4(read(ROOT / "results" / "reasons" / "step4" / "t4_behavior_by_label.csv"))


if __name__ == "__main__":
    main()