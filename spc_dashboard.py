"""
=============================================================================
SPC DASHBOARD — IN-PROCESS QUALITY CONTROL
Statistical Process Control for Relay Manufacturing

DISCLAIMER: ALL DATA IN THIS SCRIPT IS SIMULATED / DUMMY DATA GENERATED
FOR PORTFOLIO DEMONSTRATION PURPOSES ONLY. THIS IS NOT REAL PRODUCTION DATA
FROM PT OMRON MANUFACTURING OF INDONESIA OR ANY OTHER COMPANY.
=============================================================================

Products:   Omron G2R-1-E DC12 (Coil Resistance Spec: 100Ω ± 5%)
            Omron G5V-2-H1 DC5  (Coil Resistance Spec:  50Ω ± 5%)
Parameter:  Coil Resistance (Ω) — measured per IQC incoming inspection
Method:     X-bar & R Chart, p-Chart, Process Capability (Cp, Cpk)
Standards:  AIAG SPC Manual 2nd Ed. | Western Electric Rules
Author:     Naufal Suryo Saputro — Engineering Physics, UGM
"""

import numpy as np
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.patches import FancyBboxPatch
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

np.random.seed(2025)

# ─── COLOUR PALETTE ───────────────────────────────────────────────────────
C_NAVY   = "#1F3864"
C_BLUE   = "#2E75B6"
C_RED    = "#C00000"
C_GREEN  = "#375623"
C_ORANGE = "#ED7D31"
C_GRAY   = "#595959"
C_LGRAY  = "#F2F2F2"
C_YELLOW = "#FFD966"
C_WHITE  = "#FFFFFF"

FONT = "DejaVu Sans"
plt.rcParams.update({
    "font.family": FONT,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "axes.grid": True,
    "grid.alpha": 0.3,
    "grid.linestyle": "--",
})

DISCLAIMER = (
    "⚠  SIMULATED DATA — For Portfolio Demonstration Only\n"
    "Not real production data from PT Omron Manufacturing of Indonesia"
)

# ─── PRODUCT SPECIFICATIONS ───────────────────────────────────────────────
products = {
    "G2R-1-E DC12": {
        "nominal": 100.0,   # Ω
        "usl":     105.0,   # +5%
        "lsl":      95.0,   # -5%
        "process_mean":  100.8,
        "process_std":    1.2,
        "color":   C_BLUE,
        "defect_base": 0.04,
    },
    "G5V-2-H1 DC5": {
        "nominal":  50.0,
        "usl":      52.5,
        "lsl":      47.5,
        "process_mean":  50.3,
        "process_std":   0.65,
        "color":   C_ORANGE,
        "defect_base": 0.05,
    },
}

# ─── DATA GENERATION ──────────────────────────────────────────────────────
N_SUBGROUPS = 25
SUBGROUP_SIZE = 5
N_BATCHES = 20

def generate_xbar_r_data(spec, inject_ooc=True):
    """
    Generate subgroup data for X-bar & R chart.
    Injects deliberate out-of-control signals for realism.
    """
    mu  = spec["process_mean"]
    sig = spec["process_std"]
    data = []
    for i in range(N_SUBGROUPS):
        shift = 0
        # Inject OOC: mean shift at subgroup 14-16 (tool wear simulation)
        if inject_ooc and 13 <= i <= 15:
            shift = 2.2 * sig
        subgroup = np.random.normal(mu + shift, sig, SUBGROUP_SIZE)
        data.append(subgroup)
    return np.array(data)   # shape (25, 5)

def compute_xbar_r_limits(data):
    """Compute control limits using AIAG SPC constants for n=5."""
    # Control chart constants for n=5
    A2 = 0.577
    D3 = 0.0
    D4 = 2.114

    xbar = data.mean(axis=1)
    R    = data.max(axis=1) - data.min(axis=1)

    xbar_bar = xbar.mean()
    R_bar    = R.mean()

    ucl_xbar = xbar_bar + A2 * R_bar
    lcl_xbar = xbar_bar - A2 * R_bar
    ucl_r    = D4 * R_bar
    lcl_r    = D3 * R_bar   # = 0 for n≤6

    return xbar, R, xbar_bar, R_bar, ucl_xbar, lcl_xbar, ucl_r, lcl_r

def western_electric_violations(xbar, ucl, lcl, center):
    """
    Apply Western Electric Rules to detect out-of-control signals.
    Returns dict of {subgroup_index: rule_violated}.
    """
    violations = {}
    n = len(xbar)
    sigma_est = (ucl - center) / 3

    for i in range(n):
        # Rule 1: Point beyond 3σ
        if xbar[i] > ucl or xbar[i] < lcl:
            violations[i] = "Rule 1: Beyond 3σ"
            continue
        # Rule 2: 9 consecutive points same side of centerline
        if i >= 8:
            run = xbar[i-8:i+1]
            if all(x > center for x in run) or all(x < center for x in run):
                violations[i] = "Rule 2: 9-point run"
                continue
        # Rule 3: 6 points continuously increasing or decreasing
        if i >= 5:
            run = xbar[i-5:i+1]
            if all(run[j] < run[j+1] for j in range(5)) or \
               all(run[j] > run[j+1] for j in range(5)):
                violations[i] = "Rule 3: 6-point trend"
                continue
        # Rule 4: 2 of 3 consecutive points beyond 2σ
        if i >= 2:
            run = xbar[i-2:i+1]
            beyond_2sig = sum(1 for x in run if abs(x - center) > 2*sigma_est)
            if beyond_2sig >= 2:
                violations[i] = "Rule 4: 2/3 beyond 2σ"

    return violations

def generate_pchart_data(spec):
    """Generate batch-level defect rate data for p-chart."""
    base = spec["defect_base"]
    n_inspected = np.random.randint(80, 120, N_BATCHES)
    # Inject spike at batch 11
    defect_rates = []
    for i in range(N_BATCHES):
        if i == 10:
            rate = base * 2.8
        elif i == 11:
            rate = base * 2.1
        else:
            rate = np.random.beta(base*10, (1-base)*10)
        defect_rates.append(min(rate, 0.99))
    n_defects = np.array([int(r*n) for r,n in zip(defect_rates, n_inspected)])
    return n_inspected, n_defects

def compute_pchart_limits(n_inspected, n_defects):
    """Compute p-chart control limits (variable sample size)."""
    p_bar = n_defects.sum() / n_inspected.sum()
    p_i   = n_defects / n_inspected
    ucl   = p_bar + 3 * np.sqrt(p_bar * (1-p_bar) / n_inspected)
    lcl   = np.maximum(0, p_bar - 3 * np.sqrt(p_bar * (1-p_bar) / n_inspected))
    return p_i, p_bar, ucl, lcl

def compute_capability(data_flat, spec):
    """Compute Cp, Cpk, sigma level, and expected PPM defects."""
    mu  = data_flat.mean()
    sig = data_flat.std(ddof=1)
    usl = spec["usl"]
    lsl = spec["lsl"]

    cp  = (usl - lsl) / (6 * sig)
    cpu = (usl - mu)  / (3 * sig)
    cpl = (mu  - lsl) / (3 * sig)
    cpk = min(cpu, cpl)

    # Sigma level (short-term, no 1.5σ shift for simplicity)
    sigma_level = cpk * 3

    # Expected PPM defects
    p_above = 1 - stats.norm.cdf(usl, mu, sig)
    p_below = stats.norm.cdf(lsl, mu, sig)
    ppm = (p_above + p_below) * 1_000_000

    return cp, cpk, cpu, cpl, sigma_level, ppm, mu, sig

# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 1 — X-bar & R Charts (both products)
# ═════════════════════════════════════════════════════════════════════════════
def plot_xbar_r(ax_xbar, ax_r, data, spec, product_name):
    xbar, R, xbar_bar, R_bar, ucl_x, lcl_x, ucl_r, lcl_r = compute_xbar_r_limits(data)
    violations = western_electric_violations(xbar, ucl_x, lcl_x, xbar_bar)
    color = spec["color"]
    x = np.arange(1, N_SUBGROUPS+1)

    # ── X-bar chart ──
    ax_xbar.fill_between(x, lcl_x, ucl_x, alpha=0.08, color=color, label="Control band")
    ax_xbar.axhline(xbar_bar, color=color, lw=1.8, label=f"X̄̄ = {xbar_bar:.2f}Ω")
    ax_xbar.axhline(ucl_x, color=C_RED, lw=1.2, ls="--", label=f"UCL = {ucl_x:.2f}Ω")
    ax_xbar.axhline(lcl_x, color=C_RED, lw=1.2, ls="--", label=f"LCL = {lcl_x:.2f}Ω")
    ax_xbar.axhline(spec["usl"], color=C_GREEN, lw=1.0, ls=":", label=f"USL = {spec['usl']:.1f}Ω")
    ax_xbar.axhline(spec["lsl"], color=C_GREEN, lw=1.0, ls=":", label=f"LSL = {spec['lsl']:.1f}Ω")

    # Plot points
    normal_idx = [i for i in range(N_SUBGROUPS) if i not in violations]
    ooc_idx    = list(violations.keys())
    ax_xbar.plot(x[normal_idx], xbar[normal_idx], "o-", color=color, ms=5, lw=1.5, zorder=3)
    ax_xbar.plot(x[ooc_idx],    xbar[ooc_idx],    "D",  color=C_RED, ms=7, zorder=4,
                 label=f"OOC signal ({len(ooc_idx)} pts)")
    # Annotate OOC
    for i in ooc_idx:
        rule = violations[i].split(":")[0]
        ax_xbar.annotate(rule, (x[i], xbar[i]),
                        textcoords="offset points", xytext=(0, 10),
                        fontsize=6.5, color=C_RED, ha="center",
                        arrowprops=dict(arrowstyle="-", color=C_RED, lw=0.8))

    ax_xbar.set_title(f"{product_name} — X-bar Chart (Subgroup Mean, n={SUBGROUP_SIZE})",
                      fontsize=10, fontweight="bold", color=C_NAVY, pad=6)
    ax_xbar.set_ylabel("Coil Resistance (Ω)", fontsize=9)
    ax_xbar.legend(fontsize=7.5, loc="upper left", framealpha=0.85, ncol=3)
    ax_xbar.set_xticks(x)
    ax_xbar.tick_params(labelbottom=False)

    # ── R chart ──
    ax_r.fill_between(x, lcl_r, ucl_r, alpha=0.08, color=color)
    ax_r.axhline(R_bar,  color=color, lw=1.8, label=f"R̄ = {R_bar:.3f}Ω")
    ax_r.axhline(ucl_r,  color=C_RED, lw=1.2, ls="--", label=f"UCL = {ucl_r:.3f}Ω")
    ax_r.axhline(lcl_r,  color=C_GRAY, lw=1.0, ls="--", label=f"LCL = {lcl_r:.3f}Ω")

    r_ooc = [i for i in range(len(R)) if R[i] > ucl_r]
    r_normal = [i for i in range(len(R)) if i not in r_ooc]
    ax_r.plot(x[r_normal], R[r_normal], "s-", color=color, ms=4, lw=1.5)
    if r_ooc:
        ax_r.plot(x[r_ooc], R[r_ooc], "D", color=C_RED, ms=7, label="OOC")

    ax_r.set_title(f"{product_name} — R Chart (Subgroup Range)",
                   fontsize=10, fontweight="bold", color=C_NAVY, pad=6)
    ax_r.set_ylabel("Range (Ω)", fontsize=9)
    ax_r.set_xlabel("Subgroup Number", fontsize=9)
    ax_r.legend(fontsize=7.5, loc="upper left", framealpha=0.85, ncol=3)
    ax_r.set_xticks(x)

    return violations

print("Generating data...")
data_g2r = generate_xbar_r_data(products["G2R-1-E DC12"])
data_g5v = generate_xbar_r_data(products["G5V-2-H1 DC5"])

# ── Figure 1: X-bar & R ──
print("Plotting Figure 1: X-bar & R Charts...")
fig1, axes = plt.subplots(4, 1, figsize=(14, 14),
                           gridspec_kw={"hspace": 0.38, "height_ratios": [2,1,2,1]})
fig1.patch.set_facecolor(C_WHITE)

viol_g2r = plot_xbar_r(axes[0], axes[1], data_g2r, products["G2R-1-E DC12"], "Omron G2R-1-E DC12 (100Ω spec)")
viol_g5v = plot_xbar_r(axes[2], axes[3], data_g5v, products["G5V-2-H1 DC5"],  "Omron G5V-2-H1 DC5 (50Ω spec)")

# Main title + disclaimer
fig1.suptitle("X-bar & R Control Charts — Relay Coil Resistance Inspection",
              fontsize=13, fontweight="bold", color=C_NAVY, y=0.98)
fig1.text(0.5, 0.005, DISCLAIMER, ha="center", fontsize=8.5,
          color=C_RED, style="italic",
          bbox=dict(boxstyle="round,pad=0.4", facecolor=C_YELLOW, alpha=0.8, edgecolor=C_ORANGE))

plt.savefig("/home/claude/spc_dashboard/output/01_xbar_r_chart.png",
            dpi=150, bbox_inches="tight", facecolor=C_WHITE)
plt.close()
print("  ✓ Saved 01_xbar_r_chart.png")

# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 2 — p-Charts (both products)
# ═════════════════════════════════════════════════════════════════════════════
print("Plotting Figure 2: p-Charts...")
fig2, axes2 = plt.subplots(2, 1, figsize=(14, 9),
                            gridspec_kw={"hspace": 0.42})
fig2.patch.set_facecolor(C_WHITE)

for ax, (pname, spec) in zip(axes2, products.items()):
    n_insp, n_def = generate_pchart_data(spec)
    p_i, p_bar, ucl_p, lcl_p = compute_pchart_limits(n_insp, n_def)

    x = np.arange(1, N_BATCHES+1)
    ooc = [i for i in range(N_BATCHES) if p_i[i] > ucl_p[i] or p_i[i] < lcl_p[i]]
    normal = [i for i in range(N_BATCHES) if i not in ooc]

    ax.fill_between(x, lcl_p, ucl_p, alpha=0.10, color=spec["color"], label="Control band (variable)")
    ax.axhline(p_bar, color=spec["color"], lw=1.8, label=f"p̄ = {p_bar:.3f} ({p_bar*100:.1f}%)")
    ax.plot(x, ucl_p, color=C_RED, lw=1.2, ls="--", label="UCL (variable)")
    ax.plot(x, lcl_p, color=C_RED, lw=1.0, ls="--", label="LCL (variable)")

    ax.plot(x[normal], p_i[normal], "o-", color=spec["color"], ms=5, lw=1.5)
    if ooc:
        ax.plot(np.array(x)[ooc], p_i[ooc], "D", color=C_RED, ms=8,
                label=f"OOC batch ({len(ooc)} pts)", zorder=4)
        for i in ooc:
            ax.annotate(f"Batch {x[i]}\n{p_i[i]*100:.1f}%",
                       (x[i], p_i[i]), textcoords="offset points", xytext=(8, 6),
                       fontsize=7, color=C_RED,
                       bbox=dict(boxstyle="round,pad=0.2", fc="white", ec=C_RED, alpha=0.8))

    # Sample size annotation on secondary axis note
    ax.set_title(f"{pname} — p-Chart (Batch Defect Rate, n≈{int(n_insp.mean())} per batch)",
                 fontsize=10, fontweight="bold", color=C_NAVY, pad=6)
    ax.set_ylabel("Defect Rate (p)", fontsize=9)
    ax.set_xlabel("Batch Number", fontsize=9)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v*100:.1f}%"))
    ax.legend(fontsize=8, loc="upper right", framealpha=0.85, ncol=2)
    ax.set_xticks(x)

fig2.suptitle("p-Chart — Batch Defect Rate Monitoring (Incoming Inspection)",
              fontsize=13, fontweight="bold", color=C_NAVY, y=0.99)
fig2.text(0.5, 0.002, DISCLAIMER, ha="center", fontsize=8.5,
          color=C_RED, style="italic",
          bbox=dict(boxstyle="round,pad=0.4", facecolor=C_YELLOW, alpha=0.8, edgecolor=C_ORANGE))

plt.savefig("/home/claude/spc_dashboard/output/02_pchart.png",
            dpi=150, bbox_inches="tight", facecolor=C_WHITE)
plt.close()
print("  ✓ Saved 02_pchart.png")

# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 3 — Process Capability (Cp, Cpk)
# ═════════════════════════════════════════════════════════════════════════════
print("Plotting Figure 3: Process Capability...")

def plot_capability(ax, data_flat, spec, product_name):
    cp, cpk, cpu, cpl, sigma_level, ppm, mu, sig = compute_capability(data_flat, spec)
    usl = spec["usl"]; lsl = spec["lsl"]; color = spec["color"]

    # Histogram
    counts, bins, patches = ax.hist(data_flat, bins=22, density=True,
                                     color=color, alpha=0.55, edgecolor="white",
                                     linewidth=0.6, label="Measured data")
    # Colour bars outside spec red
    for patch, left, right in zip(patches, bins[:-1], bins[1:]):
        if right <= lsl or left >= usl:
            patch.set_facecolor(C_RED); patch.set_alpha(0.7)

    # Normal distribution fit
    x_range = np.linspace(data_flat.min()-0.5, data_flat.max()+0.5, 400)
    pdf = stats.norm.pdf(x_range, mu, sig)
    ax.plot(x_range, pdf, color=color, lw=2.2, label=f"Normal fit (μ={mu:.2f}, σ={sig:.3f})")

    # Spec lines
    ax.axvline(usl, color=C_GREEN, lw=2, ls="-",  label=f"USL = {usl:.1f}Ω")
    ax.axvline(lsl, color=C_GREEN, lw=2, ls="-",  label=f"LSL = {lsl:.1f}Ω")
    ax.axvline(mu,  color=C_NAVY,  lw=1.5, ls="--", label=f"Mean = {mu:.2f}Ω")

    # Shade out-of-spec regions
    x_above = x_range[x_range >= usl]
    x_below = x_range[x_range <= lsl]
    if len(x_above): ax.fill_between(x_above, stats.norm.pdf(x_above, mu, sig),
                                     alpha=0.25, color=C_RED, label="Out-of-spec")
    if len(x_below): ax.fill_between(x_below, stats.norm.pdf(x_below, mu, sig),
                                     alpha=0.25, color=C_RED)

    # ── Capability annotation box ──
    def cpk_interpret(cpk_val):
        if cpk_val >= 1.67: return "Excellent ✓✓"
        if cpk_val >= 1.33: return "Capable ✓"
        if cpk_val >= 1.00: return "Marginal ⚠"
        return "Incapable ✗"

    ann_text = (
        f"PROCESS CAPABILITY REPORT\n"
        f"{'─'*28}\n"
        f"  Cp   = {cp:.3f}   (potential)\n"
        f"  Cpk  = {cpk:.3f}   (actual)\n"
        f"  Cpu  = {cpu:.3f}   (upper)\n"
        f"  Cpl  = {cpl:.3f}   (lower)\n"
        f"{'─'*28}\n"
        f"  σ Level  = {sigma_level:.2f}σ\n"
        f"  PPM exp. = {ppm:.0f} ppm\n"
        f"  Status   : {cpk_interpret(cpk)}\n"
        f"{'─'*28}\n"
        f"  Target Cpk ≥ 1.33\n"
        f"  Target PPM < 64"
    )
    ax.text(0.975, 0.97, ann_text, transform=ax.transAxes,
            fontsize=8, va="top", ha="right", family="monospace",
            bbox=dict(boxstyle="round,pad=0.55", facecolor=C_LGRAY,
                      edgecolor=C_NAVY, alpha=0.95, linewidth=1.2))

    ax.set_title(f"{product_name} — Process Capability Analysis (Cp, Cpk)",
                 fontsize=10, fontweight="bold", color=C_NAVY, pad=6)
    ax.set_xlabel("Coil Resistance (Ω)", fontsize=9)
    ax.set_ylabel("Probability Density", fontsize=9)
    ax.legend(fontsize=8, loc="upper left", framealpha=0.85, ncol=2)

    return cp, cpk, ppm

fig3, axes3 = plt.subplots(2, 1, figsize=(14, 11), gridspec_kw={"hspace": 0.42})
fig3.patch.set_facecolor(C_WHITE)

cp_g2r, cpk_g2r, ppm_g2r = plot_capability(
    axes3[0], data_g2r.flatten(), products["G2R-1-E DC12"], "Omron G2R-1-E DC12 (100Ω ±5%)")
cp_g5v, cpk_g5v, ppm_g5v = plot_capability(
    axes3[1], data_g5v.flatten(), products["G5V-2-H1 DC5"],  "Omron G5V-2-H1 DC5 (50Ω ±5%)")

fig3.suptitle("Process Capability Analysis — Relay Coil Resistance",
              fontsize=13, fontweight="bold", color=C_NAVY, y=0.99)
fig3.text(0.5, 0.002, DISCLAIMER, ha="center", fontsize=8.5,
          color=C_RED, style="italic",
          bbox=dict(boxstyle="round,pad=0.4", facecolor=C_YELLOW, alpha=0.8, edgecolor=C_ORANGE))

plt.savefig("/home/claude/spc_dashboard/output/03_capability.png",
            dpi=150, bbox_inches="tight", facecolor=C_WHITE)
plt.close()
print("  ✓ Saved 03_capability.png")

# ═════════════════════════════════════════════════════════════════════════════
# FIGURE 4 — Full Summary Dashboard (1 page)
# ═════════════════════════════════════════════════════════════════════════════
print("Plotting Figure 4: Summary Dashboard...")

fig4 = plt.figure(figsize=(18, 22))
fig4.patch.set_facecolor(C_WHITE)

gs = gridspec.GridSpec(
    5, 4,
    figure=fig4,
    hspace=0.52, wspace=0.38,
    left=0.07, right=0.97,
    top=0.93, bottom=0.07
)

# ── Header ──
ax_title = fig4.add_subplot(gs[0, :])
ax_title.axis("off")
ax_title.text(0.5, 0.78,
    "SPC DASHBOARD — IN-PROCESS QUALITY CONTROL",
    transform=ax_title.transAxes, ha="center", va="center",
    fontsize=17, fontweight="bold", color=C_NAVY)
ax_title.text(0.5, 0.50,
    "Relay Coil Resistance Monitoring  |  Omron G2R-1-E DC12 & G5V-2-H1 DC5  |  "
    f"n={SUBGROUP_SIZE} per subgroup  |  {N_SUBGROUPS} subgroups  |  {N_BATCHES} batches",
    transform=ax_title.transAxes, ha="center", va="center",
    fontsize=10, color=C_GRAY)
ax_title.text(0.5, 0.18, DISCLAIMER,
    transform=ax_title.transAxes, ha="center", va="center",
    fontsize=9, color=C_RED, style="italic",
    bbox=dict(boxstyle="round,pad=0.4", facecolor=C_YELLOW, alpha=0.9, edgecolor=C_ORANGE))
ax_title.set_facecolor(C_LGRAY)
for spine in ax_title.spines.values(): spine.set_visible(False)

# ── Row 1: X-bar charts ──
ax_xb1 = fig4.add_subplot(gs[1, :2])
ax_xb2 = fig4.add_subplot(gs[1, 2:])
# Dummy R axes (not shown in summary — use axes behind)
fig4_dummy1 = plt.figure(); ax_r1_dummy = fig4_dummy1.add_subplot(111); plt.close(fig4_dummy1)
fig4_dummy2 = plt.figure(); ax_r2_dummy = fig4_dummy2.add_subplot(111); plt.close(fig4_dummy2)

# Re-plot X-bar only (simplified)
for ax, data, spec, pname in [
    (ax_xb1, data_g2r, products["G2R-1-E DC12"], "G2R-1-E DC12 (100Ω)"),
    (ax_xb2, data_g5v, products["G5V-2-H1 DC5"],  "G5V-2-H1 DC5 (50Ω)"),
]:
    xbar, R, xbar_bar, R_bar, ucl_x, lcl_x, ucl_r, lcl_r = compute_xbar_r_limits(data)
    violations = western_electric_violations(xbar, ucl_x, lcl_x, xbar_bar)
    color = spec["color"]
    x = np.arange(1, N_SUBGROUPS+1)
    ooc_idx = list(violations.keys())
    normal_idx = [i for i in range(N_SUBGROUPS) if i not in violations]

    ax.fill_between(x, lcl_x, ucl_x, alpha=0.10, color=color)
    ax.axhline(xbar_bar, color=color, lw=1.6, label=f"X̄̄={xbar_bar:.2f}Ω")
    ax.axhline(ucl_x, color=C_RED, lw=1.1, ls="--", label=f"UCL={ucl_x:.2f}Ω")
    ax.axhline(lcl_x, color=C_RED, lw=1.1, ls="--", label=f"LCL={lcl_x:.2f}Ω")
    ax.axhline(spec["usl"], color=C_GREEN, lw=0.9, ls=":", label=f"USL={spec['usl']:.0f}Ω")
    ax.axhline(spec["lsl"], color=C_GREEN, lw=0.9, ls=":", label=f"LSL={spec['lsl']:.0f}Ω")
    ax.plot(x[normal_idx], xbar[normal_idx], "o-", color=color, ms=4, lw=1.3)
    if ooc_idx:
        ax.plot(np.array(x)[ooc_idx], xbar[np.array(ooc_idx)], "D",
                color=C_RED, ms=6, label=f"OOC ({len(ooc_idx)})", zorder=4)
    ax.set_title(f"X-bar Chart — {pname}", fontsize=9, fontweight="bold", color=C_NAVY)
    ax.set_ylabel("Resistance (Ω)", fontsize=8)
    ax.set_xlabel("Subgroup", fontsize=8)
    ax.legend(fontsize=7, loc="upper left", framealpha=0.85, ncol=3)
    ax.tick_params(labelsize=7)
    ax.grid(True, alpha=0.3, ls="--")

# ── Row 2: p-charts ──
ax_p1 = fig4.add_subplot(gs[2, :2])
ax_p2 = fig4.add_subplot(gs[2, 2:])
for ax, (pname, spec) in zip([ax_p1, ax_p2], products.items()):
    n_insp, n_def = generate_pchart_data(spec)
    p_i, p_bar, ucl_p, lcl_p = compute_pchart_limits(n_insp, n_def)
    x = np.arange(1, N_BATCHES+1)
    ooc = [i for i in range(N_BATCHES) if p_i[i] > ucl_p[i]]
    normal = [i for i in range(N_BATCHES) if i not in ooc]
    color = spec["color"]

    ax.fill_between(x, lcl_p, ucl_p, alpha=0.10, color=color)
    ax.axhline(p_bar, color=color, lw=1.6, label=f"p̄={p_bar*100:.1f}%")
    ax.plot(x, ucl_p, color=C_RED, lw=1.0, ls="--", label="UCL")
    ax.plot(x, lcl_p, color=C_RED, lw=0.8, ls="--", label="LCL")
    ax.plot(x[normal], p_i[normal], "o-", color=color, ms=4, lw=1.3)
    if ooc:
        ax.plot(np.array(x)[ooc], p_i[ooc], "D", color=C_RED, ms=6,
                label=f"OOC ({len(ooc)})", zorder=4)
    short = pname.split()[0]
    ax.set_title(f"p-Chart — {short} Batch Defect Rate", fontsize=9, fontweight="bold", color=C_NAVY)
    ax.set_ylabel("Defect Rate", fontsize=8)
    ax.set_xlabel("Batch", fontsize=8)
    ax.yaxis.set_major_formatter(plt.FuncFormatter(lambda v,_: f"{v*100:.1f}%"))
    ax.legend(fontsize=7, loc="upper right", framealpha=0.85, ncol=2)
    ax.tick_params(labelsize=7)

# ── Row 3: Capability histograms ──
ax_cap1 = fig4.add_subplot(gs[3, :2])
ax_cap2 = fig4.add_subplot(gs[3, 2:])
for ax, data, spec, pname in [
    (ax_cap1, data_g2r, products["G2R-1-E DC12"], "G2R-1-E DC12"),
    (ax_cap2, data_g5v, products["G5V-2-H1 DC5"],  "G5V-2-H1 DC5"),
]:
    cp, cpk, cpu, cpl, sigma_level, ppm, mu, sig = compute_capability(data.flatten(), spec)
    color = spec["color"]
    usl = spec["usl"]; lsl = spec["lsl"]
    x_range = np.linspace(data.min()-0.5, data.max()+0.5, 300)

    ax.hist(data.flatten(), bins=20, density=True, color=color,
            alpha=0.5, edgecolor="white", lw=0.5)
    ax.plot(x_range, stats.norm.pdf(x_range, mu, sig), color=color, lw=2)
    ax.axvline(usl, color=C_GREEN, lw=1.8, ls="-", label=f"USL={usl:.1f}Ω")
    ax.axvline(lsl, color=C_GREEN, lw=1.8, ls="-", label=f"LSL={lsl:.1f}Ω")
    ax.axvline(mu,  color=C_NAVY,  lw=1.3, ls="--", label=f"μ={mu:.2f}Ω")

    def cpk_color(v): return C_GREEN if v>=1.33 else (C_ORANGE if v>=1.0 else C_RED)
    ann = (f"Cp  = {cp:.3f}\nCpk = {cpk:.3f}\n{sigma_level:.1f}σ | {ppm:.0f} PPM")
    ax.text(0.97, 0.97, ann, transform=ax.transAxes, fontsize=8.5,
            va="top", ha="right", family="monospace",
            color=cpk_color(cpk),
            bbox=dict(boxstyle="round,pad=0.4", facecolor=C_LGRAY,
                      edgecolor=cpk_color(cpk), lw=1.5, alpha=0.95))

    ax.set_title(f"Process Capability — {pname}", fontsize=9, fontweight="bold", color=C_NAVY)
    ax.set_xlabel("Resistance (Ω)", fontsize=8)
    ax.set_ylabel("Density", fontsize=8)
    ax.legend(fontsize=7.5, loc="upper left", framealpha=0.85)
    ax.tick_params(labelsize=7)

# ── Row 4: KPI Summary Table ──
ax_kpi = fig4.add_subplot(gs[4, :])
ax_kpi.axis("off")

# Build summary table data
xbar_g2r, _, xb_bar_g2r, Rbar_g2r, ucl_x_g2r, lcl_x_g2r, _, _ = compute_xbar_r_limits(data_g2r)
xbar_g5v, _, xb_bar_g5v, Rbar_g5v, ucl_x_g5v, lcl_x_g5v, _, _ = compute_xbar_r_limits(data_g5v)
viol_g2r_sum = western_electric_violations(xbar_g2r, ucl_x_g2r, lcl_x_g2r, xb_bar_g2r)
viol_g5v_sum = western_electric_violations(xbar_g5v, ucl_x_g5v, lcl_x_g5v, xb_bar_g5v)

table_data = [
    ["Parameter", "G2R-1-E DC12", "G5V-2-H1 DC5", "Target", "Status"],
    ["Nominal Spec (Ω)", "100 ± 5%", "50 ± 5%", "—", "—"],
    ["Process Mean X̄ (Ω)", f"{xb_bar_g2r:.3f}", f"{xb_bar_g5v:.3f}", "= Nominal", "—"],
    ["Process Range R̄ (Ω)", f"{Rbar_g2r:.3f}", f"{Rbar_g5v:.3f}", "—", "—"],
    ["Cp", f"{cp_g2r:.3f}", f"{cp_g5v:.3f}", "≥ 1.33", f"{'✓' if cp_g2r>=1.33 else '⚠'}  {'✓' if cp_g5v>=1.33 else '⚠'}"],
    ["Cpk", f"{cpk_g2r:.3f}", f"{cpk_g5v:.3f}", "≥ 1.33", f"{'✓' if cpk_g2r>=1.33 else '⚠'}  {'✓' if cpk_g5v>=1.33 else '⚠'}"],
    ["Expected PPM", f"{ppm_g2r:.0f}", f"{ppm_g5v:.0f}", "< 64", f"{'✓' if ppm_g2r<64 else '⚠'}  {'✓' if ppm_g5v<64 else '⚠'}"],
    ["OOC Signals (WE Rules)", str(len(viol_g2r_sum)), str(len(viol_g5v_sum)), "0", f"{'✓' if not viol_g2r_sum else '⚠'}  {'✓' if not viol_g5v_sum else '⚠'}"],
    ["Subgroups / Sample Size", f"{N_SUBGROUPS}", f"{N_SUBGROUPS}", "25", "✓  ✓"],
]

col_w = [0.28, 0.18, 0.18, 0.16, 0.15]
col_x = [0.01, 0.30, 0.49, 0.68, 0.84]
row_h = 0.115
y_start = 0.97

for row_idx, row in enumerate(table_data):
    y = y_start - row_idx * row_h
    bg = C_NAVY if row_idx == 0 else (C_LGRAY if row_idx % 2 == 0 else C_WHITE)
    fg = C_WHITE if row_idx == 0 else "black"
    bold = row_idx == 0

    for col_idx, (cell, cx, cw) in enumerate(zip(row, col_x, col_w)):
        rect = FancyBboxPatch((cx, y - row_h + 0.01), cw - 0.01, row_h - 0.01,
                               transform=ax_kpi.transAxes,
                               boxstyle="round,pad=0.005",
                               facecolor=bg, edgecolor="white", lw=0.5, clip_on=False)
        ax_kpi.add_patch(rect)
        # Colour status cells
        cell_bg = bg
        cell_fg = fg
        if row_idx > 0 and col_idx == 4:
            if "✓" in str(cell) and "⚠" not in str(cell):
                cell_bg = "#E2EFDA"
                cell_fg = C_GREEN
            elif "⚠" in str(cell):
                cell_bg = "#FFF2CC"
                cell_fg = C_ORANGE
            rect.set_facecolor(cell_bg)

        ax_kpi.text(cx + cw/2, y - row_h/2,
                   str(cell), transform=ax_kpi.transAxes,
                   ha="center", va="center", fontsize=8.5,
                   color=cell_fg,
                   fontweight="bold" if bold else "normal",
                   family="monospace" if row_idx > 0 and col_idx > 0 else "sans-serif")

ax_kpi.set_xlim(0,1); ax_kpi.set_ylim(0,1)
ax_kpi.set_title("KPI Summary — Process Performance vs Target", fontsize=9,
                  fontweight="bold", color=C_NAVY, pad=4)

plt.savefig("/home/claude/spc_dashboard/output/04_summary_dashboard.png",
            dpi=150, bbox_inches="tight", facecolor=C_WHITE)
plt.close()
print("  ✓ Saved 04_summary_dashboard.png")

print("\n" + "="*52)
print("  ALL OUTPUTS GENERATED SUCCESSFULLY")
print("="*52)
print(f"  Output folder: spc_dashboard/output/")
for fname in ["01_xbar_r_chart.png","02_pchart.png",
              "03_capability.png","04_summary_dashboard.png"]:
    print(f"    ✓ {fname}")
print(f"\n  G2R: Cp={cp_g2r:.3f}, Cpk={cpk_g2r:.3f}, PPM={ppm_g2r:.0f}, OOC={len(viol_g2r_sum)}")
print(f"  G5V: Cp={cp_g5v:.3f}, Cpk={cpk_g5v:.3f}, PPM={ppm_g5v:.0f}, OOC={len(viol_g5v_sum)}")
