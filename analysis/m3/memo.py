"""The hypotheses memo (M3.6): results set beside H1–H8 as pre-registered, unedited.

    python -m analysis.m3.memo [RESULTS_FOLDER]

The hypothesis text is quoted word for word from docs/hypotheses.md (the same parser the report uses). Each part
gets the result and verdict computed by analysis/m3/hypotheses.py: supported, not supported, untestable, or
reported (H2). Writes hypotheses_memo.md into the results folder. Banner and disclosure on top (Rule 7; Amendment 7).
"""

import json
import re
import sys
from pathlib import Path

from analysis.report.build import parse_hypotheses

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "outputs" / "results"


def disclosure():
    text = (ROOT / "README.md").read_text()
    return " ".join(re.search(r"\*\*Disclosure\.\*\*.*?(?=\n\s*\n)", text, re.S).group(0).split())


def write(folder=OUT):
    folder = Path(folder)
    meta = json.loads((folder / "meta.json").read_text())
    results = {h["id"]: h for h in json.loads((folder / "hypotheses.json").read_text())}
    text = parse_hypotheses()
    tally = {}
    lines = [f"> **{meta['release']['banner']}**", "", "# Hypotheses memo: v0.1 results against H1–H8 as pre-registered", "",
             disclosure(), "",
             f"Stamp: commit `{meta['stamp']['git_commit']}` · config `{meta['stamp']['config_hash']}` · frozen settings "
             f"`{meta['stamp']['params_fingerprint']}` · Jev `{meta['stamp']['jev_estimate_version']}` "
             f"({meta['stamp']['jev_model']}) · {meta['runs_per_cell']} paired runs per bank per cell.", "",
             "The hypothesis text below is quoted unedited from `docs/hypotheses.md` (frozen at `pre-registration-v1`). "
             "Where it leaves room, Clarification 31 B7 (recorded before any stress run of B, B′, C, C′ or E) fixes how "
             "it is scored; H8 follows Clarifications 17–18. Verdicts: supported, not supported, untestable, or reported "
             "(H2, which makes no prediction).", ""]
    for hid, h in text.items():
        lines += [f"## {hid}. {h['title']}", ""]
        lines += [f"- **{k}:** {v}" for k, v in h["bullets"]]
        lines += ["", "| Part | Result | Verdict |", "|---|---|---|"]
        for p in results[hid]["parts"]:
            lines.append(f"| {p['part']} | {p['result'].replace('|', '/')} | **{p['verdict']}** |")
            tally[p["verdict"]] = tally.get(p["verdict"], 0) + 1
        lines.append("")
    lines += ["## Note recorded after results (Amendment 8)", "",
              "`docs/hypotheses.md` says, under \"Not hypothesized\", that C has no effect on the diversified regional "
              "archetype by construction. The text above is left unedited. In the model, those banks get no LCR credit, but "
              "C's policy-wide routine-borrowing rate (contract 3a) lowers their effective stigma, so C can and does differ "
              "from A for them.", ""]
    lines += ["## Tally", "", ", ".join(f"{k}: {v}" for k, v in sorted(tally.items())) + " (counting each scored part).", ""]
    (folder / "hypotheses_memo.md").write_text("\n".join(lines))
    return folder / "hypotheses_memo.md"


if __name__ == "__main__":
    print(f"wrote {write(*(Path(x) for x in sys.argv[1:]))}")
