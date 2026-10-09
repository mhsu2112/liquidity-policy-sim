"""Build the M3 report from one results folder (session M3.0; Clarification 28).

    python -m analysis.report.build RESULTS_FOLDER OUT_FOLDER [--no-marker-preview OTHER_RESULTS_FOLDER]

The report reads only the results folder (in the schema of analysis/results_schema.md) plus the project's
own documents (README disclosure, docs/hypotheses.md) and its layout files. It never imports the engine.
The same code draws mock results now and real results in M3; only the folder changes.
"""

import argparse
import hashlib
import re
import shutil
import sys
from pathlib import Path

import yaml

from analysis.report import charts
from analysis.report.html import ROOT, e, md_inline, page
from analysis.results_schema import (COMPARISONS, FEATURES, HYPOTHESIS_PARTS, OPTION_C_DEFAULTS, OUTCOMES,
                                     TIMING_BANDS, EXTRA_VERDICTS, VERDICTS, comparison_sides, load, metric_applies,
                                     num, validate, vocabulary)

HERE = Path(__file__).resolve().parent
LAYOUT = HERE / "layout.yaml"
LIMITS = HERE / "limits.yaml"
HYPOTHESES = ROOT / "docs" / "hypotheses.md"


AMENDMENTS = ROOT / "docs" / "amendments.md"
RECORD = re.compile(r"layout fingerprint: `?([0-9a-f]{16})`?", re.I)


def load_layout():
    return yaml.safe_load(LAYOUT.read_text())


def layout_fingerprint(path=LAYOUT):
    """SHA-256 of layout.yaml, cut to 16 characters. Clarification 28 records it; a change needs a new entry."""
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()[:16]


def recorded_layout_fingerprints(path=AMENDMENTS):
    return RECORD.findall(Path(path).read_text())


# ---------- small formatting helpers ----------

def chart_banner(meta, layout):
    """What the charts stamp: the mock banner, or the release banner (Clarification 31: v0.1), or nothing."""
    if meta["mock"]:
        return layout["mock_banner"]
    if meta.get("release"):
        return {"text": meta["release"]["banner"], "colour": layout["release_banner_colour"]}
    return ""


def fmt_value(v, kind):
    if v is None:
        return ""
    return {"pct": f"{v:.1%}", "num0": f"{v:,.0f}", "num1": f"{v:,.1f}", "num2": f"{v:.2f}", "count": f"{v:,.0f}"}[kind]


def fmt_diff(v, kind):
    if kind == "pct":
        return f"{v * 100:+.1f} pp"
    return {"num0": f"{v:+,.0f}", "num1": f"{v:+,.1f}", "num2": f"{v:+.2f}"}.get(kind, f"{v:+g}")


def with_ci(d, lo, hi, kind, prefix="Δ vs A "):
    return f'<span class="ci">{prefix}{fmt_diff(d, kind)} [{fmt_diff(lo, kind)}, {fmt_diff(hi, kind)}]</span>'


def groups(vocab, layout):
    """Every scenario x bank type, with an anchor id and a heading."""
    for s in vocab["scenarios"]:
        for b in vocab["bank_types"]:
            yield s, b, f"{s}-{b}", f"{layout['scenario_labels'][s]} — {vocab['bank_labels'][b]}"


def toc(vocab, layout):
    return '<div class="toc">' + "".join(f'<a href="#{a}">{e(h)}</a>' for _, _, a, h in groups(vocab, layout)) + "</div>"


# ---------- pages ----------

def front_page(d, vocab, layout, has_no_marker):
    readme = (ROOT / "README.md").read_text()
    rows = re.findall(r"^\| (A|B|C|C′|E) \| (.+?) \|$", readme, re.M)
    policies = "".join(f"<tr><td class=l><b>{e(k)}</b></td><td class=l>{md_inline(v)}</td></tr>" for k, v in rows)
    policies += ("<tr><td class=l><b>B′</b></td><td class=l>As B, but the ratio counts loans prepositioned at the Fed "
                 "only. Added after pre-registration (Amendment 3); exploratory, no hypothesis.</td></tr>")
    links = "".join(f'<tr><td class=l><a href="{p["file"]}">{e(p["title"])}</a></td><td class=l>{e(p["purpose"])}</td></tr>'
                    for p in layout["pages"] if p["id"] != "index")
    if has_no_marker:
        links += ('<tr><td class=l><a href="no-marker/tradeoff.html">Trade-off chart, no-marker version</a> · '
                  '<a href="no-marker/reversal.html">reversal, no-marker version</a></td>'
                  '<td class=l>What these pages show if the gold-set agreement test (M2.4) fails</td></tr>')
    m, s = d["meta.json"], d["meta.json"]["stamp"]
    marker = (f"{e(m['jev_marker']['label'])} at market stigma {m['jev_marker']['stigma']:g}" if m["jev_marker"]["available"]
              else "none (the sweep stands alone)")
    body = f"""
<h2>What the comparison is</h2>
<p>How a bank run plays out under six discount window readiness policies, and what each costs. Every policy faces
the same {len(vocab['bank_types']) * 10} synthetic banks ({", ".join(e(vocab['bank_labels'][b]) for b in vocab['bank_types'])}),
the same two scenarios (S1 fast run, S2 false alarm) and the same random draws: {m['runs_per_cell']} paired runs per bank
in each of the 7 market-stigma × 5 supervision cells (contract 4–5; Clarification 14).</p>
<div class="scroll"><table><tr><th class=l>Policy</th><th class=l>Rule</th></tr>{policies}</table></div>
<p><b>How a policy "leads"</b> (contract 4): at least as good on both survival and liquidity shortfall, with the 90%
interval for at least one excluding zero. Otherwise the cell is a tie, or a trade-off against cost. Every comparison
is a paired difference with a 90% interval. There is no composite score and no dollar value per failure.</p>
<h2>Pages</h2>
<div class="scroll"><table>{links}</table></div>
<h2>Stamp</h2>
<div class="scroll"><table>
<tr><td class=l>Git commit</td><td class=l><code>{e(s['git_commit'])}</code></td></tr>
<tr><td class=l>Config hash</td><td class=l><code>{e(s['config_hash'])}</code></td></tr>
<tr><td class=l>Frozen settings fingerprint</td><td class=l><code>{e(s['params_fingerprint'])}</code></td></tr>
<tr><td class=l>Jev estimate version</td><td class=l><code>{e(s['jev_estimate_version'])}</code></td></tr>
<tr><td class=l>Jev model (pinned)</td><td class=l><code>{e(s['jev_model'])}</code></td></tr>
<tr><td class=l>Jev marker</td><td class=l>{marker}</td></tr>
<tr><td class=l>Results written</td><td class=l>{e(m['generated_at'])}</td></tr>
</table></div>"""
    return page(layout, m, "index", "Liquidity Policy Simulator — M3 report", body)


def scorecard_page(d, vocab, layout):
    cols, pol = layout["scorecard_columns"], layout["policy_labels"]
    sc = {(r["policy"], r["scenario"], r["bank_type"], r["metric"]): r for r in d["scorecard.csv"]}
    bands = {(r["policy"], r["scenario"], r["bank_type"], r["band"]): r for r in d["timing_bands.csv"]}
    out = [f'<p class="note">Scope: {e(d["meta.json"]["scorecard_scope"])}. Each cell: the policy\'s own level, then the '
           'paired difference against A with its 90% interval. "—" means the metric does not apply. '
           'Official support is the discount window only; window loans are not repaid within an episode, so peak equals '
           'total. Home Loan Bank advances are in <a href="scorecard_extra.csv">scorecard_extra.csv</a> (Clarification 31). '
           '<a href="scorecard.csv">Download the scorecard CSV</a>.</p>', toc(vocab, layout)]
    for s, b, anchor, heading in groups(vocab, layout):
        head = "".join(f'<th{" class=grace" if c["metric"] == "timing_only_upper_bound" else ""}>{e(c["label"])}</th>' for c in cols)
        body = ""
        for p in vocab["policies"]:
            cells = ""
            for c in cols:
                m, k = c["metric"], c["format"]
                if not metric_applies(m, p, s):
                    cells += '<td class=na title="does not apply">—</td>'
                    continue
                r = sc[(p, s, b, m)]
                if m == "timing_only_upper_bound":
                    fails = round(int(r["n_runs"]) * (1 - num(sc[(p, s, b, "survival_rate")]["value"])))
                    cells += f'<td class=grace>≤ {fmt_value(num(r["value"]), k)}<span class="ci">of {fails:,} failures</span></td>'
                    continue
                ci = with_ci(num(r["diff_vs_a"]), num(r["diff_lo"]), num(r["diff_hi"]), k) if r["diff_vs_a"] else ""
                cells += f"<td>{fmt_value(num(r['value']), k)}{ci}</td>"
            body += f"<tr><td class=l><b>{e(pol[p])}</b></td>{cells}</tr>"
        note = ""
        if s == "S2" and b == "svb_like":
            note = ('<p class="note">SVB-like banks under S2: reported as a <b>rumor-triggered run</b>, not as needless '
                    'borrowing, and not scored for H8 (Clarification 17 item 3).</p>')
        out.append(f'<h2 id="{anchor}">{e(heading)}</h2><div class="scroll"><table><tr><th class=l>Policy</th>{head}</tr>'
                   f"{body}</table></div>{note}")
    out.append("<h2>Timing bands: why failed runs failed (Clarification 18 item 2)</h2>"
               '<p class="note">Share of each policy\'s failed runs in each band. Reported, not scored.</p>')
    for s, b, anchor, heading in groups(vocab, layout):
        head = "".join(f"<th>{e(layout['timing_band_labels'][t])}</th>" for t in TIMING_BANDS)
        rows = ""
        for p in vocab["policies"]:
            rs = [bands[(p, s, b, t)] for t in TIMING_BANDS]
            n = sum(int(r["failures"]) for r in rs)
            rows += (f"<tr><td class=l><b>{e(pol[p])}</b></td><td>{n:,}</td>"
                     + "".join(f"<td>{fmt_value(num(r['share']), 'pct') or '—'}</td>" for r in rs) + "</tr>")
        out.append(f'<h3>{e(heading)}</h3><div class="scroll"><table><tr><th class=l>Policy</th><th>Failed runs</th>{head}'
                   f"</tr>{rows}</table></div>")
    return page(layout, d["meta.json"], "scorecard", "Scorecard", "\n".join(out))


def tradeoff_page(d, vocab, layout, out, prefix=""):
    meta = d["meta.json"]
    marker = meta["jev_marker"] if meta["jev_marker"]["available"] else None
    banner = chart_banner(meta, layout)
    img_dir = out / "img"
    img_dir.mkdir(parents=True, exist_ok=True)
    parts = ['<p class="note">One panel per comparison. Rows: supervisory treatment of borrowing. Columns: market stigma. '
             'Each cell names who leads (or tie / trade-off) and the annual cost difference, first-named policy minus '
             'second, $m per bank per year. Colours: blue = first-named policy leads; orange with dots = second-named '
             'leads; grey = tie; hatched white = trade-off. Every cell also says it in words, so the chart reads in '
             'black and white.</p>']
    marker_line = (f"Marker: {e(marker['label'])} at stigma {marker['stigma']:g}." if marker
                   else e(layout["tradeoff"]["no_marker_note"]))
    parts.append(f"<p><b>{marker_line}</b></p>")
    parts.append(toc(vocab, layout))
    for s, b, anchor, heading in groups(vocab, layout):
        rows = [r for r in d["tradeoff.csv"] if r["scenario"] == s and r["bank_type"] == b]
        path = img_dir / f"tradeoff_{anchor}.png"
        charts.tradeoff_figure(rows, vocab, layout, marker, heading, path, banner)
        bw = charts.bw_copy(path) if s == vocab["scenarios"][0] else None
        bw_link = f' · <a href="img/{bw.name}">black-and-white check</a>' if bw else ""
        parts.append(f'<h2 id="{anchor}">{e(heading)}</h2><p class="note"><a href="img/{path.name}">full size</a>{bw_link}</p>'
                     f'<img class="chart" src="img/{path.name}" alt="Trade-off grid, {e(heading)}">')
    title = "Trade-off chart" + ("" if marker or not prefix else " (no-marker version)")
    return page(layout, meta, "tradeoff", title, "\n".join(parts), prefix)


def frontier_page(d, vocab, layout, out):
    banner = chart_banner(d["meta.json"], layout)
    parts = ['<p class="note">Each point is a policy: survival and shortfall are means over the runs of that bank type, '
             'pooled over the 35 cells, with 90% intervals across runs; cost is the mean across the banks of that type, '
             'with a 90% interval across banks (Clarification 31). Cost is relative to A, so A sits at zero. Up and left is better on survival; down and left on '
             'shortfall. No dollar value per failure is assumed, so the frontier is shown, not collapsed.</p>']
    for s in vocab["scenarios"]:
        path = out / "img" / f"frontier_{s}.png"
        charts.frontier_figure([r for r in d["frontier.csv"] if r["scenario"] == s], vocab, layout,
                               f"Cost frontier — {layout['scenario_labels'][s]}", path, banner)
        parts.append(f'<h2>{e(layout["scenario_labels"][s])}</h2><img class="chart" src="img/{path.name}" alt="Cost frontier {s}">')
    return page(layout, d["meta.json"], "frontier", "Cost frontier", "\n".join(parts))


def option_c_page(d, vocab, layout, out):
    banner = chart_banner(d["meta.json"], layout)
    parts = [f'<p class="note">C and C′ across voluntary uptake and the share of HQLA released. Defaults: uptake '
             f'{OPTION_C_DEFAULTS["uptake"]:.0%}, released {OPTION_C_DEFAULTS["hqla_released"]:.0%} (contract 2d). '
             f'Cells off the cross are {e(layout["option_c"]["not_run_note"])}. Each run cell shows survival against A (paired, '
             f'90% interval) on the 9 mid-range cells, the grid every point of the cross was run on. Under current LCR scope, the Category IV '
             'diversified regional bank gets no LCR credit under C or C′ (contract 1c), but C\'s routine-borrowing rate '
             '(r = uptake × 2.5) applies to every bank (contract 3a), so it still lowers that bank\'s effective stigma '
             '(corrected 2026-10-09, Amendment 8). C\'s cost saving and '
             'its buffer gap are the same money: see the scorecard, where they sit side by side.</p>']
    for s in vocab["scenarios"]:
        path = out / "img" / f"option_c_{s}.png"
        charts.option_c_figure([r for r in d["option_c.csv"] if r["scenario"] == s], vocab, layout,
                               f"Option C panel — {layout['scenario_labels'][s]}", path, banner)
        parts.append(f'<h2>{e(layout["scenario_labels"][s])}</h2><img class="chart" src="img/{path.name}" alt="Option C panel {s}">')
    return page(layout, d["meta.json"], "option_c", "Option C panel", "\n".join(parts))


def reversal_page(d, vocab, layout, prefix=""):
    meta = d["meta.json"]
    if not meta["jev_marker"]["available"]:
        body = (f"<p><b>{e(layout['tradeoff']['no_marker_note'])}</b></p><p>Reversal distances are measured from the "
                "marker, so there are none to show. The trade-off chart's full stigma sweep is the result.</p>")
        return page(layout, meta, "reversal", "Reversal distances (no-marker version)", body, prefix)
    pol, t = layout["policy_labels"], layout["tradeoff"]
    rv = {(r["comparison"], r["scenario"], r["bank_type"], r["supervision"]): r for r in d["reversal.csv"]}

    def name(comp, lab):
        x, y = (pol[s] for s in comparison_sides(comp))
        return {"x_leads": f"{x} leads", "y_leads": f"{y} leads", "tie": "tie", "trade_off": "trade-off"}[lab]

    def move(r, side, comp):
        dist = num(r[f"{side}_distance"])
        return "no change on the grid" if dist is None else f"{dist:.2f} → {name(comp, r[side + '_label'])}"

    parts = [f'<p class="note">For each comparison and supervision setting: the cell at the {e(meta["jev_marker"]["label"])} '
             f'(stigma {meta["jev_marker"]["stigma"]:g}), and how far market stigma must move down or up from it before '
             'the cell changes, with what it changes to. The cell "at the marker" is the nearest grid point (Clarification 31).</p>',
             implied_s_table(d, layout), toc(vocab, layout)]
    for s, b, anchor, heading in groups(vocab, layout):
        rows = ""
        for comp in COMPARISONS:
            for u in vocab["supervision"]:
                r = rv[(comp, s, b, u)]
                x, y = (pol[k] for k in comparison_sides(comp))
                rows += (f"<tr><td class=l>{e(x)} vs {e(y)}</td><td class=l>{e(t['supervision_labels'][u])}</td>"
                         f"<td class=l>{e(name(comp, r['label_at_marker']))}</td><td class=l>{e(move(r, 'down', comp))}</td>"
                         f"<td class=l>{e(move(r, 'up', comp))}</td></tr>")
        parts.append(f'<h2 id="{anchor}">{e(heading)}</h2><div class="scroll"><table><tr><th class=l>Comparison</th>'
                     "<th class=l>Supervision</th><th class=l>At the marker</th><th class=l>Stigma moves down</th>"
                     f"<th class=l>Stigma moves up</th></tr>{rows}</table></div>")
    return page(layout, meta, "reversal", "Reversal distances", "\n".join(parts), prefix)


def implied_s_table(d, layout):
    """Clarification 31 A2: each policy's own Jev marker and the s it implies against A. Exploratory."""
    rows = d.get("implied_s.csv", [])
    if not rows:
        return ""
    body = "".join(f"<tr><td class=l><b>{e(layout['policy_labels'][r['policy']])}</b></td><td>{e(r['marker'])}</td>"
                   f"<td>{e(r['spread_low'])}–{e(r['spread_high'])}</td><td>{e(r['r'])}</td>"
                   f"<td>{e(r['implied_s']) or '—'}</td><td class=l>{e(r['note'])}</td></tr>" for r in rows)
    return ('<h2>Side table: each policy\'s Jev marker and the s it implies (exploratory)</h2><p class="note">Only A\'s '
            'marker is placed on the axis, which is market stigma before the routine-borrowing effect. B\'s and C\'s '
            'readings already include that effect, which the model applies through s. Implied s = −ln(marker_P / marker_A) / '
            '(r_P − r_A), with the contract\'s r (C at 75% uptake). Labelled exploratory (Clarification 31).</p>'
            '<div class="scroll"><table><tr><th class=l>Policy</th><th>Marker</th><th>Spread</th><th>r (per quarter)</th>'
            f'<th>Implied s</th><th class=l>Note</th></tr>{body}</table></div>')


DIAGNOSTICS = [   # Amendment 9: the session v0.1-D diagnostics, shown as sensitivities (file, heading)
    ("1_grace_survival.csv", "Sensitivity 1 — grace count (upper bound): survival under the strict rule and counting "
                             "timing-only failures as survivals"),
    ("1_grace_labels.csv", "Sensitivity 1 — grace count (upper bound): label counts over the 35 cells"),
    ("2_s0_labels.csv", "Sensitivity 2 — no routine-borrowing effect (s = 0): label counts over the 9 mid-range cells"),
    ("3_hesitation.csv", "Sensitivity 3 — hesitation gap: share of runs borrowing a day or more after first seeing a shortfall"),
    ("4_owed_levels_S1.csv", "Sensitivity 4 — S1 shortfall as the largest amount still owed (alternative definition, not "
                             "the scored one)"),
    ("4_owed_labels_S1.csv", "Sensitivity 4 — S1 label counts with the largest amount still owed (alternative definition, "
                             "not the scored one)"),
]


def diagnostics_section(folder):
    """Amendment 9: the v0.1-D diagnostics as labelled sensitivities, read from their CSVs; empty if absent."""
    if folder is None or not Path(folder).exists():
        return ""
    import csv
    parts = ['<h2 id="diagnostics">Diagnostic sensitivities (session v0.1-D)</h2><p class="note">Sensitivities, not scored. '
             'Computed from the saved v0.1 runs; no scored result changes (Amendment 9). Sensitivity 1 is an upper bound: a '
             'run that fails for timing alone stops there, so whether it would have failed later is never seen. '
             'Sensitivity 2 covers the 9 mid-range cells, where s was varied. Sensitivity 4 uses a re-run of the S1 main '
             'grid that reproduced every saved field exactly.</p>']
    for name, heading in DIAGNOSTICS:
        path = Path(folder) / name
        if not path.exists():
            continue
        rows = list(csv.reader(open(path, newline="")))
        head = "".join(f"<th>{e(h)}</th>" for h in rows[0])
        body = "".join("<tr>" + "".join(f"<td{' class=l' if i < 3 else ''}>{e(c)}</td>" for i, c in enumerate(r)) + "</tr>"
                       for r in rows[1:])
        parts.append(f'<h3>{e(heading)}</h3><p class="note"><a href="diagnostics/{e(name)}">{e(name)}</a></p>'
                     f'<div class="scroll"><table><tr>{head}</tr>{body}</table></div>')
    return "\n".join(parts)


def sensitivity_page(d, vocab, layout, diagnostics=None):
    """Clarification 31 B5: each one-at-a-time sensitivity against the default."""
    pol, sl = layout["policy_labels"], layout["scenario_labels"]
    rows = d.get("sensitivity.csv", [])
    labs = d.get("sensitivity_labels.csv", [])
    parts = ['<p class="note">One setting at a time, around the defaults (Clarification 14 item 3), on the 9 mid-range '
             'cells (C uptake: all 35). For each rerun policy: its survival and shortfall at that point, and the paired '
             'difference from the same policy at the default, with 90% intervals. Below each, how many of the 9 mid-range '
             'cells change label for each comparison. Policies a setting cannot affect reuse their default runs.</p>']
    extra = diagnostics_section(diagnostics)
    if extra:
        parts = [extra, '<h2 id="one-at-a-time">One-at-a-time sensitivities (run plan)</h2>'] + parts
    if not rows:
        parts.append("<p>No sensitivity results in this folder.</p>")
    for name in dict.fromkeys(r["sensitivity"] for r in rows):
        mine = [r for r in rows if r["sensitivity"] == name]
        body = "".join(
            f"<tr><td class=l>{e(r['point'])}</td><td class=l>{e(sl[r['scenario']])}</td><td class=l>"
            f"{e(vocab['bank_labels'][r['bank_type']])}</td><td class=l>{e(pol[r['policy']])}</td>"
            f"<td>{fmt_value(num(r['survival']), 'pct')}{with_ci(num(r['survival_diff']), num(r['survival_lo']), num(r['survival_hi']), 'pct', 'Δ vs default ')}</td>"
            f"<td>{fmt_value(num(r['shortfall_bn']), 'num1')}{with_ci(num(r['shortfall_diff']), num(r['shortfall_lo']), num(r['shortfall_hi']), 'num1', 'Δ vs default ')}</td></tr>"
            for r in mine)
        ch = [r for r in labs if r["sensitivity"] == name]
        chg = "".join(f"<tr><td class=l>{e(r['point'])}</td><td class=l>{e(sl[r['scenario']])}</td><td class=l>"
                      f"{e(vocab['bank_labels'][r['bank_type']])}</td><td class=l>{e(' vs '.join(pol[k] for k in comparison_sides(r['comparison'])))}</td>"
                      f"<td>{e(r['cells_changed'])} of {e(r['cells'])}</td></tr>" for r in ch if r["cells_changed"] != "0")
        parts.append(f'<h2 id="{e(name)}">{e(name.replace("_", " "))}</h2><div class="scroll"><table><tr><th class=l>Point</th>'
                     f"<th class=l>Scenario</th><th class=l>Bank type</th><th class=l>Policy</th><th>Survival</th>"
                     f"<th>Shortfall ($bn)</th></tr>{body}</table></div>"
                     + (f'<p class="note">Labels that change on the mid-range cells (comparisons with no change are omitted):</p>'
                        f'<div class="scroll"><table><tr><th class=l>Point</th><th class=l>Scenario</th><th class=l>Bank type</th>'
                        f"<th class=l>Comparison</th><th>Cells changed</th></tr>{chg}</table></div>" if chg
                        else '<p class="note">No comparison changes label on any mid-range cell.</p>'))
    return page(layout, d["meta.json"], "sensitivity", "Sensitivities", "\n".join(parts))


def attribution_page(d, vocab, layout):
    at = {(r["feature"], r["scenario"], r["bank_type"], r["outcome"]): r for r in d["attribution.csv"]}
    kinds = {"survival_rate": "pct", "liquidity_shortfall_bn": "num1"}
    parts = ['<p class="note">What each switch contributes to survival and shortfall, with 90% intervals, from the '
             'feature-switch runs on the 9 mid-range cells (Clarification 14 item 5: 12 distinct setups, because the '
             'five-day ratio always prepositions). Method (Clarification 31 B6): Shapley values over the 16 switch combinations, '
             'each mapped to the setup it builds; the four contributions add up to the effect of switching all four on, '
             'against A. Survival in percentage points, shortfall in $bn.</p>']
    for s in vocab["scenarios"]:
        head1 = "".join(f"<th colspan={len(OUTCOMES)}>{e(vocab['bank_labels'][b])}</th>" for b in vocab["bank_types"])
        head2 = "".join(f"<th>{e(layout['outcome_labels'][o])}</th>" for _ in vocab["bank_types"] for o in OUTCOMES)
        rows = ""
        for f in FEATURES:
            cells = ""
            for b in vocab["bank_types"]:
                for o in OUTCOMES:
                    r = at[(f, s, b, o)]
                    cells += f"<td>{fmt_diff(num(r['contribution']), kinds[o])}{with_ci(num(r['contribution']), num(r['lo']), num(r['hi']), kinds[o], prefix='')}</td>"
            rows += f"<tr><td class=l><b>{e(layout['feature_labels'][f])}</b></td>{cells}</tr>"
        parts.append(f'<h2>{e(layout["scenario_labels"][s])}</h2><div class="scroll"><table><tr><th class=l rowspan=2>Feature</th>'
                     f"{head1}</tr><tr>{head2}</tr>{rows}</table></div>")
    return page(layout, d["meta.json"], "attribution", "Feature attribution", "\n".join(parts))


def replay_page(d, vocab, layout):
    """Schema 1.1: a list of replays (Clarification 31 B8), each with its own log; anchors are per replay."""
    pol = layout["policy_labels"]
    checks = {None: "support check: not run", "supported": "support check: supported", "flagged": "support check: FLAGGED"}
    reps = d["replay.json"]
    parts = ['<p class="note">Each sentence says what an actor saw (and through which information route), what it did, or '
             'why. Each links to the log line it rests on, and Jev was asked whether the log supports it (M3.5). Flags are '
             'shown as they came out.</p>']
    if not reps:
        parts.append("<p>No replay in this folder.</p>")
    parts.append('<div class="toc">' + "".join(f'<a href="#R{i}">{e(layout["scenario_labels"][rp["scenario"]])} — policy '
                                                f'{e(pol[rp["policy"]])}</a>' for i, rp in enumerate(reps)) + "</div>")
    for i, rp in enumerate(reps):
        flags = sum(en["support_check"] == "flagged" for day in rp["days"] for en in day["entries"])
        parts.append(f'<h2 id="R{i}">{e(layout["scenario_labels"][rp["scenario"]])} under policy {e(pol[rp["policy"]])}</h2>'
                     f'<p>Bank {e(rp["bank_id"])} · run {rp["run"]} · {e(rp["selection"])} · flagged sentences: {flags}</p>')
        for day in rp["days"]:
            items = ""
            for en in day["entries"]:
                route = f" · via {e(en['route'])}" if en["route"] else ""
                items += (f'<li><b>{e(en["actor"])}</b> <span class="note">({e(en["half"])}, {e(en["kind"])}{route})</span> '
                          f'{e(en["text"])} <a href="#R{i}L{en["log_line"]}">log {en["log_line"]}</a> '
                          f'<span class="slot">{checks[en["support_check"]]}</span></li>')
            parts.append(f"<h3>Day {day['day']}</h3><ul>{items}</ul>")
        log = "".join(f'<tr id="R{i}L{x["line"]}"><td>{x["line"]}</td><td class=l><code>{e(x["text"])}</code></td></tr>'
                      for x in rp["log"])
        parts.append(f'<details><summary>Log ({len(rp["log"])} lines)</summary><div class="scroll"><table><tr><th>Line</th>'
                     f'<th class=l>Entry</th></tr>{log}</table></div></details>')
    return page(layout, d["meta.json"], "replay", "Episode replays", "\n".join(parts))


def parse_hypotheses(path=HYPOTHESES):
    """H1–H8 from docs/hypotheses.md: title and bullet lines, word for word."""
    found = {}
    for block in re.split(r"\n(?=## H\d)", path.read_text())[1:]:
        m = re.match(r"## (H\d)\. (.+)", block)
        bullets = re.findall(r"^- \*\*(.+?):\*\* (.+?)(?=\n- \*\*|\n\n|\n---|\Z)", block, re.M | re.S)
        found[m.group(1)] = {"title": m.group(2).strip(), "bullets": [(k, " ".join(v.split())) for k, v in bullets]}
    return found


def hypotheses_page(d, vocab, layout):
    text = parse_hypotheses()
    results = {h["id"]: h for h in d["hypotheses.json"]}
    parts = ['<p class="note">Word for word from <code>docs/hypotheses.md</code>, frozen at <code>pre-registration-v1</code>. '
             f'Verdict slots: {e(layout["verdict_slots"])}. H8 is scored as Clarifications 17–18 set out.</p>']
    for hid in HYPOTHESIS_PARTS:
        h = text[hid]
        bl = "".join(f"<li><b>{e(k)}:</b> {md_inline(v)}</li>" for k, v in h["bullets"])
        allowed = " · ".join(VERDICTS[1:] + EXTRA_VERDICTS.get(hid, []))
        rows = "".join(f'<tr><td class=l>{e(p["part"])}</td><td class=l><span class="slot">{e(p["result"])}</span></td>'
                       f'<td class=l><span class="slot">{e(p["verdict"])}</span></td><td class="l note">{e(allowed)}</td></tr>'
                       for p in results[hid]["parts"])
        parts.append(f'<h2 id="{hid}">{hid}. {e(h["title"])}</h2><ul>{bl}</ul><div class="scroll"><table><tr><th class=l>Part</th>'
                     f"<th class=l>Result</th><th class=l>Verdict</th><th class=l>Allowed verdicts</th></tr>{rows}</table></div>")
    return page(layout, d["meta.json"], "hypotheses", "Hypotheses", "\n".join(parts))


def limits_page(d, vocab, layout):
    limits = yaml.safe_load(LIMITS.read_text())["limits"]
    items = "".join(f"<li><b>{e(x['title'])}.</b> {e(x['text'])} <span class='note'>({e(x['source'])})</span></li>" for x in limits)
    return page(layout, d["meta.json"], "limits", "Limits", f"<p>The v1 limits recorded so far.</p><ol>{items}</ol>")


# ---------- the build ----------

def build(results, out, no_marker_results=None):
    """Validate the results folder, then write every page and chart to out. Returns the pages written."""
    for folder in [results] + ([no_marker_results] if no_marker_results else []):
        problems = validate(folder)
        if problems:
            raise ValueError(f"{folder} does not match analysis/results_schema.md:\n  " + "\n  ".join(problems[:20]))
    out = Path(out)
    if out.exists():
        shutil.rmtree(out)
    (out / "img").mkdir(parents=True)
    layout, vocab, d = load_layout(), vocabulary(), load(results)
    diagnostics = Path(results).parent / "diagnostics"          # Amendment 9: e.g. outputs/v0.1/diagnostics
    diagnostics = diagnostics if (diagnostics / "1_grace_survival.csv").exists() else None
    pages = {
        "index": front_page(d, vocab, layout, bool(no_marker_results)),
        "scorecard": scorecard_page(d, vocab, layout),
        "tradeoff": tradeoff_page(d, vocab, layout, out),
        "frontier": frontier_page(d, vocab, layout, out),
        "option_c": option_c_page(d, vocab, layout, out),
        "reversal": reversal_page(d, vocab, layout),
        "sensitivity": sensitivity_page(d, vocab, layout, diagnostics),
        "attribution": attribution_page(d, vocab, layout),
        "replay": replay_page(d, vocab, layout),
        "hypotheses": hypotheses_page(d, vocab, layout),
        "limits": limits_page(d, vocab, layout),
    }
    written = []
    for p in layout["pages"]:
        (out / p["file"]).write_text(pages[p["id"]])
        written.append(out / p["file"])
    shutil.copy(Path(results) / "scorecard.csv", out / "scorecard.csv")
    if diagnostics:
        shutil.copytree(diagnostics, out / "diagnostics", ignore=shutil.ignore_patterns("*.html"))
    for extra in ("scorecard_extra.csv", "hypotheses_memo.md"):
        if (Path(results) / extra).exists():
            shutil.copy(Path(results) / extra, out / extra)
    if no_marker_results:
        alt, dn = out / "no-marker", load(no_marker_results)
        (alt / "img").mkdir(parents=True)
        (alt / "tradeoff.html").write_text(tradeoff_page(dn, vocab, layout, alt, prefix="../"))
        (alt / "reversal.html").write_text(reversal_page(dn, vocab, layout, prefix="../"))
        written += [alt / "tradeoff.html", alt / "reversal.html"]
    return written


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("results")
    ap.add_argument("out")
    ap.add_argument("--no-marker-preview", default=None)
    a = ap.parse_args(argv)
    try:
        written = build(a.results, a.out, a.no_marker_preview)
    except ValueError as err:
        sys.exit(str(err))
    print(f"Wrote {len(written)} pages. Open {Path(a.out) / 'index.html'}")


if __name__ == "__main__":
    main()
