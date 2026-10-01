"""Write outputs/validation_report.html from outputs/validation_results.json (run by `make validate`).

Each check's result against Clarification 16's criteria (pass or fail, with the numbers), every
choice Clarification 16 left open, and the model's known limits. Policy A only.
"""

import html
import json

from engine.write_banks import ROOT, git_commit, settings_hash
from validation.checks import CHECKS_PATH, OUT as RESULTS, SCENARIOS_PATH

OUT_HTML = ROOT / "outputs" / "validation_report.html"
NAMES = {"svb_like": "SVB-like", "diversified_regional": "Diversified regional", "regional_cat3": "Regional (Cat. III)",
         "gsib": "GSIB / large bank"}

CSS = """
:root { --surface:#fcfcfb; --ink:#0b0b0b; --ink-2:#52514e; --rule:#dddcd6; --pass:#008300; --fail:#c62828;
        --note:#fff4e0; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) {
  --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --rule:#3a3a37; --pass:#4caf50; --fail:#ef6b6b; --note:#3a2e17; } }
:root[data-theme="dark"] { --surface:#1a1a19; --ink:#fff; --ink-2:#c3c2b7; --rule:#3a3a37; --pass:#4caf50;
  --fail:#ef6b6b; --note:#3a2e17; }
body { background:var(--surface); color:var(--ink); font:16px/1.5 system-ui, sans-serif; margin:0; }
main { max-width:900px; margin:0 auto; padding:24px 16px 48px; }
h1 { font-size:1.6rem; margin:0 0 4px; } h2 { font-size:1.15rem; margin:32px 0 8px; } h3 { font-size:1rem; margin:20px 0 6px; }
.sub, .stamp { color:var(--ink-2); } .stamp { font-size:.8rem; margin-top:40px; }
table { border-collapse:collapse; width:100%; font-variant-numeric:tabular-nums; margin:6px 0 10px; }
th, td { text-align:left; padding:6px 8px; border-bottom:1px solid var(--rule); vertical-align:top; }
td.n, th.n { text-align:right; }
.badge { font-weight:700; white-space:nowrap; } .pass { color:var(--pass); } .fail { color:var(--fail); }
.note { background:var(--note); padding:12px 16px; border-radius:6px; }
.wrap { overflow-x:auto; }
"""


def badge(ok):
    return f"<span class='badge {'pass' if ok else 'fail'}'>{'✓ PASS' if ok else '✗ FAIL'}</span>"


def crit_table(rows):
    body = "".join(f"<tr><td>{c}</td><td>{need}</td><td class='n'>{got}</td><td>{badge(ok)}</td></tr>"
                   for c, need, got, ok in rows)
    return (f"<div class='wrap'><table><tr><th>Criterion</th><th>Needed</th><th class='n'>Model</th><th></th></tr>"
            f"{body}</table></div>")


def main():
    r = json.loads(RESULTS.read_text())
    s, f, fa, ns = r["signature"], r["first_republic"], r["false_alarm"], r["no_shock"]
    e = html.escape
    summary = "".join(f"<tr><td>{name}</td><td>{badge(x['pass'])}</td></tr>" for name, x in [
        ("1. Signature-like bank, S1", s), ("2. First Republic-like bank, S1 + $30bn on day 5", f),
        ("3. False alarm (S2, shock 0.45), all 40 banks", fa), ("4. No shock, all 40 banks", ns)])
    fa_rows = "".join(
        f"<tr><td>{NAMES[a]}{'' if v['scored'] else ' (reported, not scored)'}</td>"
        f"<td class='n'>{v['survive_share']:.1%}</td><td class='n'>{v['no_shortfall_share']:.1%}</td>"
        f"<td class='n'>{v['borrowed_share']:.1%}</td><td class='n'>{v['median_support_share']:.1%}</td>"
        f"<td class='n'>{v['median_outflow_share']:.1%}</td></tr>" for a, v in fa["by_archetype"].items())

    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>Out-of-Sample Validation</title>
<style>{CSS}</style></head><body><main>
<h1>Out-of-sample checks</h1>
<p class="sub">Session M1.11 · Clarification 16 · policy A only · tuning cell (stigma 0.35, neutral supervision,
s = 0.3, distress hit 0.25) · frozen settings, fingerprint <code>{e(r['fingerprint'])}</code> (unchanged) ·
{r['runs']} runs per check (per bank for the 40-bank checks) · S1 shock {r['shocks']['S1']}, S2 shock
{r['shocks']['S2']} (Amendment 5). No setting was adjusted after any check ran. Disclosure: the project's owner
previously supported a version of Option B (README).</p>

<h2>Results</h2>
<table><tr><th>Check</th><th>Result</th></tr>{summary}</table>
<p>Three of four checks pass. A failure is reported as a model limit, not fixed by retuning (Clarification 16).</p>

<h3>1. Signature-like bank (S1)</h3>
{crit_table([
    ("Runs failing by the end of day 3", "≥ 80%", f"{s['fail_by_day3_share']:.0%}", s["criteria"]["fail_by_day3"]),
    ("Median day-1 deposit outflow", "10–40% of deposits (2023: 20%)",
     f"{s['median_day1_outflow_share']:.1%} (${s['median_day1_outflow_bn']:.1f}bn)", s["criteria"]["day1_outflow"])])}
<p>Median failure day: day {s['median_end_day']:.0f}. In 2023 Signature was closed on day 3 (12 March), after the
run on 10 March. In the model it fails on the first day: its same-day sources (reserves above the floor, its repo
line and its Home Loan Bank line) don't cover the first day's withdrawals, and its capital-call and CRE loans can't be
used at the window.</p>

<h3>2. First Republic-like bank (S1, plus $30bn of consortium deposits on day 5)</h3>
{crit_table([
    ("Runs surviving past day 5", "≥ 80%", f"{f['survive_past_day5_share']:.1%}", f["criteria"]["survive_past_day5"]),
    ("Median peak official support (window + Home Loan Bank)", "> 25% of assets (2023: ~$109bn at the window)",
     f"{f['median_support_share']:.1%} (${f['median_support_bn']:.1f}bn: window ${f['median_window_bn']:.1f}bn, "
     f"Home Loan Bank ${f['median_fhlb_bn']:.1f}bn)", f["criteria"]["support_above_25pct"]),
    ("Median cumulative deposit outflow by day 10", "$48–144bn (2023: $96bn)",
     f"${f['median_outflow_day10_bn']:.1f}bn", f["criteria"]["outflow_by_day10_in_band"])])}
<p>The bank survives, as First Republic did through March, but its run by day 10 is
{f['median_outflow_day10_bn'] / 96:.0%} of 2023's $96bn, and its peak support is
{f['median_support_bn'] / 109:.0%} of First Republic's ~$109bn at the window. {f['fail_within_30_share']:.1%} of runs
fail within 30 days (not required either way).</p>

<h3>3. False alarm (S2) on all 40 banks</h3>
{crit_table([
    ("Category III and GSIB banks surviving to day 30 with no shortfall", "≥ 90% of the 20 banks",
     f"{fa['scored_banks_passing']} of {fa['scored_banks']} (pooled runs: {fa['pooled_run_share']:.2%})",
     fa["criteria"]["banks_surviving_no_shortfall"]),
    ("Their median official support (window)", "< 5% of assets", f"{fa['median_support_share_scored']:.1%}",
     fa["criteria"]["median_support_below_5pct"])])}
<div class="wrap"><table><tr><th>Bank type</th><th class="n">Survive</th><th class="n">No shortfall</th>
<th class="n">Borrowed at all</th><th class="n">Median support</th><th class="n">Median outflow (share of deposits)</th>
</tr>{fa_rows}</table></div>
<p>SVB-like banks are reported, not scored (Clarification 16). They are solvent, with positive mark-to-market equity,
but their unrealized losses amplify the rumor until it lands about as hard as S1, so S2 is not a false alarm for them
(corrected wording, Clarification 17). Almost all of them fail.</p>

<h3>4. No shock on all 40 banks</h3>
{crit_table([("Banks stable with no outflows in every run", "all 40", f"{ns['banks_stable']} of 40 "
              f"(largest outflow ${ns['max_outflow_bn']:.0f}bn; stabilized day {ns['median_stabilized_day']:.0f})",
              ns["criteria"]["all_40_stable_no_outflow"])])}

<h2>Choices Clarification 16 left open (fixed before any check ran)</h2>
<ul>
<li><strong>Balance sheets.</strong> Every value not stated in Clarification 16 is the archetype's range midpoint
(contract 1b), sized to the stated total assets: SVB-like midpoints for the Signature-like bank and
diversified-regional midpoints for the First Republic-like bank. So the First Republic-like bank, like the
archetype, has no LCR requirement, a 40% fast-depositor share and a 3% same-day repo line.</li>
<li><strong>Signature's unusable loans.</strong> The $18bn of capital-call loans are treated as C&amp;I loans. They
and every CRE loan are taken out of both window pools (prepositioned and unpledged), so the window can't lend
against them during the episode. Home Loan Bank pledges keep Clarification 4's 40% of each loan type.</li>
<li><strong>The consortium deposits.</strong> $30bn arrives as reserves at the start of day 5. It's held as
uninsured deposits that never run, because the banks committed them for 120 days (FDIC OIG).</li>
<li><strong>Tested status.</strong> Drawn as in every policy-A run, at the voluntary rate 0.1 (about 10% of runs
tested).</li>
<li><strong>Outflows and support.</strong> "Outflow" is deposits withdrawn, counted only up to each run's end
(Clarification 10). For the First Republic check, support is peak window lending plus peak Home Loan Bank
advances, as Clarification 16 states. For the false alarm, official support is window lending only
(Clarification 10).</li>
<li><strong>Scoring the false alarm.</strong> A bank "survives to day 30 with no shortfall" if more than half its runs
(its median run) do, and "no shortfall" means nothing owed at the end of any half-day. The pass test counts banks
(at least 18 of the 20). The pooled share of runs is shown alongside.</li>
<li><strong>Stable, for the no-shock check.</strong> The bank stabilizes (Clarification 10) and loses no deposits, in
every one of its runs.</li>
</ul>

<h2>Known limits</h2>
<div class="note"><ul>
<li><strong>Runs slow down after the first morning.</strong> Under the confidence rule (Clarification 8),
unrealized losses amplify the news at once, so confidence falls furthest on the first half-day, and the news then
fades. The model can't produce a run that accelerates the way SVB's did on day 2 (tuning fit −37% on cumulative
outflows; outputs/tuning_report.html). The same shape shows here: the First Republic-like run is too mild, and
the Signature-like bank fails on day 1 rather than day 3.</li>
<li><strong>The wholesale roll threshold and fire-sale price impact are not identified.</strong> SVB's pattern
doesn't pin them down, so they keep their pre-tuning values (0.6; 10 and 30 bp per $10bn). Results that depend
on wholesale refusals or securities sales rest on those starting values.</li>
<li><strong>No weekends, no BTFP, no contagion between banks.</strong> Every half-day is a business day, so a bank
never gets a weekend to mobilize collateral, as First Republic did between 10 and 13 March 2023. The Fed's Bank Term
Funding Program (par-value lending on securities, from 12 March 2023) isn't modeled. One bank's failure never moves
depositors at another. Check 2 fails partly for these reasons (docs/notes/check2-first-republic-diagnostic.md); no
fix was built (owner's decision).</li>
<li><strong>No weekends (Amendment 6).</strong> There is no weekend calendar in v1: every half-day is a business day,
so no bank gets two quiet days to mobilize collateral. This is a stated limit, not a model result.</li>
<li><strong>The grace count is an upper bound.</strong> Every failure in the model happens on a half-day when funding
already agreed was on its way (docs/notes/funding-timing-and-failure-rule.md). M3 reports, for each policy and cell,
how many failures would be timing-only: covered by cash arriving by the next morning, with equity ≥ 0 (Amendment 6).
That count is an <em>upper bound on timing-only failures</em>, because the bank's own decisions assume the strict
failure rule. It's never used to decide which policy leads, and no hypothesis is scored against it.</li>
<li><strong>Disclosures move no one.</strong> Scheduled ratio disclosures (B's five-day ratio, the LCR including C's
credit) have no effect on depositors or lenders in v1 (Clarification 15 item 6). C's reported LCR neither
reassures nor misleads observers, and keeping B's ratio private has no effect by construction.</li>
<li><strong>Cliff-edge dynamics may produce ties.</strong> A bank either stays above the tolerance level θ = 0.6 and
nobody leaves, or falls below it and runs. Banks well clear of the edge behave the same under every policy, so
many paired comparisons may come out as ties because nothing a policy changes is reached, not because the
policies are equivalent. Under S2 this shows as near-total survival for sound banks, and near-total failure for
SVB-like banks, whose losses push them over the edge.</li>
</ul></div>

<p class="stamp">git commit {e(git_commit())} · config hash {settings_hash(CHECKS_PATH, SCENARIOS_PATH)} ·
Jev estimate: not used · numbers in outputs/validation_results.json</p>
</main></body></html>"""
    OUT_HTML.write_text(page)
    print(f"Wrote {OUT_HTML.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
