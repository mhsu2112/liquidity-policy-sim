"""Report the v0.1 model-to-model check: Jev against the AI labels (Clarification 30, Part A).

Reads jev_answers.csv, labels_AI.csv, the private key (source type and period; only counts are
reported) and the owner's practice labels. Writes outputs/v0.1/gold_set_check.html with the v0.1
banner, and prints a short summary. Wording: "model-to-model agreement", never "validation".

Run: python -m signals.gold_set.check_report   (or: make gold-check)
"""

import csv
import html
from pathlib import Path

import yaml

from signals.gold_set.agreement import summarize
from signals.gold_set.draw import KEY_PATH
from signals.gold_set.labels import WORD_TO_CODE, to_word

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
OUT = ROOT / "outputs" / "v0.1" / "gold_set_check.html"
PRACTICE_PATH = HERE / "incoming" / "gold_set_L1_practice.csv"
REFERENCE_ALPHA = 0.60          # Clarification 19's threshold, shown for reference only (no gate in v0.1)
TYPE_NAMES = {"news": "News", "analyst_note": "Analyst notes", "official_statement": "Official statements",
              "speech_testimony": "Speeches and testimony", "filing": "Filings"}
PERIOD_NAMES = {"S-A": "2007–09", "S-B": "2010–19", "S-C": "2020–21", "S-D": "2022–24"}
LEVEL_NAMES = ["Reassuring", "Routine", "Some Concern", "Clear Distress"]


def _read(path):
    with open(path, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def pairs():
    """Main-round (AI code, Jev label, AI unsure, type, period) for passages the AI did not mark Not Applicable."""
    jev = {r["ID"]: int(r["label"]) for r in _read(HERE / "jev_answers.csv")}
    key = {k["gold_id"]: k for k in _read(KEY_PATH)}
    out = []
    for r in _read(HERE / "labels_AI.csv"):
        if r["Code"] == "N":
            continue
        out.append((int(r["Code"]), jev[r["ID"]], r["Unsure"] == "Y", key[r["ID"]]["source_type"], key[r["ID"]]["stratum"]))
    return out


def practice_pairs():
    """(owner's human code, Jev label) for practice passages the owner did not mark Not Applicable."""
    if not PRACTICE_PATH.exists():
        return []
    jev = {r["ID"]: int(r["label"]) for r in _read(HERE / "jev_answers.csv") if r["round"] == "practice"}
    out = []
    for r in _read(PRACTICE_PATH):
        code = WORD_TO_CODE.get(to_word(r["Answer"] or ""))
        if code and code != "N":
            out.append((int(code), jev[r["ID"]]))
    return out


def compute():
    p = pairs()
    sub = lambda keep: summarize([x[0] for x in p if keep(x)], [x[1] for x in p if keep(x)])
    pr = practice_pairs()
    return {
        "all": sub(lambda x: True),
        "not_unsure": sub(lambda x: not x[2]),
        "by_type": {t: sub(lambda x, t=t: x[3] == t) for t in TYPE_NAMES},
        "by_period": {s: sub(lambda x, s=s: x[4] == s) for s in PERIOD_NAMES},
        "practice": summarize([a for a, _ in pr], [b for _, b in pr]),
        "excluded_na": sum(1 for r in _read(HERE / "labels_AI.csv") if r["Code"] == "N"),
    }


def _fmt(s):
    a = "n/a" if s["alpha"] != s["alpha"] else f"{s['alpha']:.2f}"
    lo, hi = s["interval"]
    ci = "n/a" if lo != lo else f"{lo:.2f} to {hi:.2f}"
    ex = "n/a" if s["exact"] != s["exact"] else f"{s['exact']:.0%}"
    return a, ci, ex


def _row(name, s):
    a, ci, ex = _fmt(s)
    return f"<tr><td>{html.escape(name)}</td><td>{s['n']}</td><td>{a}</td><td>{ci}</td><td>{ex}</td></tr>"


def _confusion(s, row_label):
    head = "".join(f"<th>Jev: {n}</th>" for n in LEVEL_NAMES)
    body = "".join(f"<tr><th>{row_label}: {LEVEL_NAMES[i]}</th>" + "".join(f"<td>{v}</td>" for v in s["confusion"][i]) + "</tr>"
                   for i in range(4))
    return f"<table><tr><th></th>{head}</tr>{body}</table>"


def render(r, banner):
    a = r["all"]
    clears = a["alpha"] >= REFERENCE_ALPHA
    table = lambda rows: ("<table><tr><th>Group</th><th>Passages</th><th>α (ordinal)</th><th>90% interval</th>"
                          "<th>Exact agreement</th></tr>" + "".join(rows) + "</table>")
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>Gold-set model-to-model check (v0.1)</title>
<style>body{{font-family:-apple-system,Segoe UI,sans-serif;max-width:900px;margin:2em auto;padding:0 16px;color:#222}}
.banner{{background:#fff3cd;border:2px solid #b8860b;padding:12px;font-weight:bold}}
table{{border-collapse:collapse;margin:1em 0}}td,th{{border:1px solid #ccc;padding:4px 8px;text-align:right}}
th:first-child,td:first-child{{text-align:left}}.note{{color:#555}}</style></head><body>
<div class="banner">{html.escape(banner)}</div>
<h1>Gold-set check: model-to-model agreement (v0.1)</h1>
<p>Jev (<code>jev-1.13.0</code>) read each of the 278 gold-set passages once and placed it on the labeling guide's
four-level scale (Reassuring, Routine, Some Concern, Clear Distress). Its answers are compared with labels from
another AI model, GPT-6.1 Sol (high), which the owner filled in and reviewed by eye (Amendment 7). This measures how
far two AI models read the passages alike. <strong>It says nothing about how people read them.</strong>
{r['excluded_na']} passage(s) the AI marked Not Applicable are left out.</p>
<h2>Main result</h2>
{table([_row("All passages", a), _row("Passages the AI did not mark Unsure", r["not_unsure"])])}
<p>For reference only: Clarification 19 set 0.60 as the bar for human agreement. α(Jev, AI) =
{_fmt(a)[0]}, which {'is at or above' if clears else 'is below'} 0.60. v0.1 has no pass/fail gate.</p>
<h3>Answers side by side (all passages)</h3>{_confusion(a, "AI")}
<h2>By source type</h2>{table([_row(TYPE_NAMES[t], s) for t, s in r["by_type"].items()])}
<h2>By period</h2>{table([_row(PERIOD_NAMES[p], s) for p, s in r["by_period"].items()])}
<h2>Jev against the owner's human practice labels (illustrative only, n=15)</h2>
<p class="note">Fifteen practice passages, one human labeler (the owner), not locked. Far too few to support any
conclusion; shown only to illustrate.</p>
{table([_row("Practice passages (owner's labels)", r["practice"])])}
<p class="note">Method: Krippendorff's alpha, ordinal, levels 1–4; 90% interval from 2,000 resamples of passages
(seed 20260923); Jev's label is its most likely level. Configuration fixed in Clarification 30 before any call.
Groups with few passages have wide intervals or none.</p>
</body></html>"""


def run():
    with open(ROOT / "config" / "release.yaml") as f:
        banner = yaml.safe_load(f)["banner"]
    r = compute()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(render(r, banner))
    print(f"wrote {OUT.relative_to(ROOT)}")
    return r


if __name__ == "__main__":
    run()
