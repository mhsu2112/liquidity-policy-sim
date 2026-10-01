"""Write outputs/tuning_report.html from the M1.10 tuning results (run by `make tune`).

One self-contained page: model outflows day by day against the 2023 figures, the
frozen values, the fit on each target, how many other settings fit almost as well,
which settings the SVB pattern does not identify, and a plain-English note on what
did not fit. Policy A, SVB validation bank, S1 only.
"""

import html
import json

from engine.write_banks import ROOT, git_commit, settings_hash
from validation.tune import OUT_RESULT, TUNING_PATH, load_tuning

OUT_HTML = ROOT / "outputs" / "tuning_report.html"
LABELS = {"a": "Depositor sensitivity a", "theta": "Tolerance level θ (part of depositor sensitivity)",
          "c": "Coordination strength", "roll": "Wholesale roll threshold",
          "lag": "Slow-depositor lag (half-days)", "impact": "Fire-sale price impact (× Clarification 5 values)"}

CSS = """
:root { --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --rule:#dddcd6; --model:#2a78d6; --actual:#eb6834;
        --warn-bg:#fff4e0; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7; --rule:#3a3a37; --model:#3987e5; --actual:#d95926;
  --warn-bg:#3a2e17; } }
:root[data-theme="dark"] { --surface:#1a1a19; --ink:#ffffff; --ink-2:#c3c2b7; --rule:#3a3a37; --model:#3987e5;
  --actual:#d95926; --warn-bg:#3a2e17; }
body { background:var(--surface); color:var(--ink); font:16px/1.5 system-ui, sans-serif; margin:0; }
main { max-width:860px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:1.6rem; margin:0 0 4px; } h2 { font-size:1.15rem; margin:32px 0 8px; }
.sub, .stamp { color:var(--ink-2); } .stamp { font-size:.8rem; margin-top:40px; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--rule); } td.n, th.n { text-align:right; }
.note { background:var(--warn-bg); padding:12px 16px; border-radius:6px; }
.legend span { display:inline-flex; align-items:center; gap:6px; margin-right:16px; color:var(--ink-2); }
.legend i { width:12px; height:12px; border-radius:2px; display:inline-block; }
svg text { fill:var(--ink-2); font-size:12px; } svg .val { fill:var(--ink); }
.wrap { overflow-x:auto; }
"""


def bars(model_day, actual_day):
    """Grouped bars: model vs 2023, deposit outflows on day 1 and day 2 ($bn). Hover shows the value."""
    w, h, pad, top = 520, 240, 40, 16
    vmax = max(model_day + actual_day) * 1.15
    y = lambda v: top + (h - top - pad) * (1 - v / vmax)   # noqa: E731
    out = [f'<svg viewBox="0 0 {w} {h}" width="100%" role="img" aria-label="Deposit outflows by day, model and 2023">']
    for tick in range(0, int(vmax) + 1, 20):
        out.append(f'<line x1="{pad}" x2="{w - 8}" y1="{y(tick):.1f}" y2="{y(tick):.1f}" stroke="var(--rule)"/>'
                   f'<text x="{pad - 6}" y="{y(tick) + 4:.1f}" text-anchor="end">{tick}</text>')
    group = (w - pad - 8) / 2
    for d, (m, a) in enumerate(zip(model_day, actual_day)):
        x0 = pad + d * group + group * 0.2
        for k, (v, colour, who) in enumerate(((m, "var(--model)", "Model"), (a, "var(--actual)", "2023"))):
            x = x0 + k * (group * 0.3 + 2)
            out.append(f'<rect x="{x:.1f}" y="{y(v):.1f}" width="{group * 0.3:.1f}" height="{y(0) - y(v):.1f}" '
                       f'rx="4" fill="{colour}"><title>{who}, day {d + 1}: ${v:.1f}bn</title></rect>'
                       f'<text class="val" x="{x + group * 0.15:.1f}" y="{y(v) - 4:.1f}" text-anchor="middle">'
                       f'{v:.0f}</text>')
        out.append(f'<text x="{x0 + group * 0.3:.1f}" y="{h - pad + 18}" text-anchor="middle">Day {d + 1}</text>')
    out.append(f'<text x="{pad}" y="{top - 4}">$bn withdrawn</text></svg>')
    return "".join(out)


def main():
    r, cfg = json.loads(OUT_RESULT.read_text()), load_tuning()
    t, f, final = cfg["targets"], r["frozen"], r["final"]
    hd = final["half_day_bn"]
    model_day = [hd[0] + hd[1], hd[2] + hd[3]]
    actual_day = [t["day1_outflow_bn"], t["day2_cumulative_bn"] - t["day1_outflow_bn"]]
    impact = {k: v * f["impact"] for k, v in r["start_impact_per_bn"].items()}
    e = html.escape

    frozen_rows = "".join(
        f"<tr><td>{e(LABELS[n])}</td><td class='n'>{f[n]}</td><td>"
        f"{'tuned' if r['identified'][n] else 'not identified by SVB: kept at its pre-tuning value'}</td>"
        f"<td class='n'>{max(r['profiles'][n]['scores']) - min(r['profiles'][n]['scores']):.3f}</td></tr>"
        for n in LABELS)
    fit_rows = (
        f"<tr><td>Day-1 deposit outflow</td><td class='n'>${t['day1_outflow_bn']}bn</td>"
        f"<td class='n'>${final['D1']:.1f}bn</td><td class='n'>{final['D1'] / t['day1_outflow_bn'] - 1:+.0%}</td></tr>"
        f"<tr><td>Cumulative outflow through day 2</td><td class='n'>${t['day2_cumulative_bn']}bn</td>"
        f"<td class='n'>${final['C2']:.1f}bn</td><td class='n'>{final['C2'] / t['day2_cumulative_bn'] - 1:+.0%}</td></tr>"
        f"<tr><td>Runs failing by the end of day 2</td><td class='n'>all</td>"
        f"<td class='n'>{final['P']:.0%}</td><td class='n'>{final['P'] - 1:+.0%}</td></tr>")
    half_rows = "".join(f"<tr><td>Day {i // 2 + 1} {'morning' if i % 2 == 0 else 'afternoon'}</td>"
                        f"<td class='n'>{v:.1f}</td></tr>" for i, v in enumerate(hd))

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>SVB Tuning Report</title>
<style>{CSS}</style></head><body><main>
<h1>Tuning on SVB: parameters frozen</h1>
<p class="sub">Session M1.10 · policy A only · SVB validation bank (31 Dec 2022 balance sheet) · scenario S1
(news shock 0.50) · tuning cell: stigma 0.35, neutral supervision, s = 0.3, distress hit 0.25 ·
{cfg['runs_per_setting']} runs per setting, the same random draws for every setting. Disclosure: the project's
owner previously supported a version of Option B (README).</p>

<h2>Model against 2023, day by day</h2>
<p class="legend"><span><i style="background:var(--model)"></i>Model (frozen values, mean of
{cfg['runs_per_setting']} runs)</span><span><i style="background:var(--actual)"></i>2023 (Fed review; FDIC)</span></p>
<div class="wrap">{bars(model_day, actual_day)}</div>
<table><tr><th>Half-day (model)</th><th class="n">$bn withdrawn</th></tr>{half_rows}</table>

<h2>Fit on each target</h2>
<table><tr><th>Target (Clarification 15 item 4)</th><th class="n">2023</th><th class="n">Model</th>
<th class="n">Off by</th></tr>{fit_rows}</table>
<p>Fit score {r['final_score']:.3f} (0 = perfect; 0.01 ≈ 10% off on one target). Settings searched:
{r['settings_evaluated']:,} in two stages.</p>

<h2>Frozen values</h2>
<table><tr><th>Setting</th><th class="n">Frozen</th><th>How</th><th class="n">Score range over its grid</th></tr>
{frozen_rows}</table>
<p>Fire-sale price impact frozen at {impact['level1'] * 1e4:.0f} bp per $1bn sold for Level 1 and
{impact['level2a'] * 1e4:.0f} bp for Level 2A (Clarification 5 starting values). A setting whose score moves by
less than {cfg['identified_min_score_range']} across its whole grid is "not identified".</p>

<h2>How many other settings fit almost as well</h2>
<p><strong>{r['near_fit_count']:,}</strong> of {r['settings_evaluated']:,} settings have both outflow targets within
±{cfg['near_fit']['outflow_rel']:.0%} and at least {cfg['near_fit']['min_fail_share']:.0%} of runs failing by day 2.</p>

<h2>What did not fit, in plain English</h2>
<div class="note">
<p><strong>The model reproduces SVB's failure by day 2 and roughly its first day, but not the way the run
accelerated.</strong> In 2023 about $42bn left on 9 March and about $98bn more was requested for 10 March: the run
sped up. In the model the run slows down after the first morning ({hd[0]:.0f}, {hd[1]:.0f}, {hd[2]:.0f},
{hd[3]:.0f} $bn per half-day), so cumulative outflows through day 2 reach ${final['C2']:.0f}bn, not $140bn.</p>
<p><strong>Why.</strong> SVB's unrealized losses had wiped out 95% of its book equity on a mark-to-market basis.
Under the confidence rule (Clarification 8), that loss amplifies the news almost twofold (0.50 × 1.95), so
confidence falls to nearly zero in the very first half-day. Coordination then has no room to push it further, and
the news fades with its two-day half-life. A setting slow enough to give $42bn on day 1 cannot speed up on day 2:
across every setting searched, cumulative day-2 outflows are at most about twice day 1's; in 2023 they were
3.3 times.</p>
<p><strong>What this means.</strong> This is a limit of the model's structure, not of the search. Per the owner's
decision, the best fit is frozen and the limit is reported rather than the rule changed after seeing it. In the
model a fast run front-loads outflows into the first morning and is lighter than 2023 on day 2. The out-of-sample
checks (M1.11) show how much this matters. The wholesale roll threshold is not identified because this SVB build
has no runnable wholesale funding (its short-term borrowings are held as Home Loan Bank advances); fire-sale impact
is not identified because SVB's equity is already nearly gone on a mark-to-market basis.</p>
</div>

<p class="stamp">git commit {e(git_commit())} · config hash {settings_hash(TUNING_PATH)} · Jev estimate: not used ·
full grid in outputs/tuning_grid.csv</p>
</main></body></html>"""
    OUT_HTML.write_text(page)
    print(f"Wrote {OUT_HTML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
