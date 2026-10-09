"""M2.5: one provisional market-stigma marker per policy (Clarification 30 Part B; release v0.1).

The contract defines market stigma as "the chance a known draw is read as distress". Jev reads each
disclosure template in its original wording and each paraphrase (placeholders filled from
config/templates_fill.yaml), from three vantage points, asked both ways:
  reading = mean of P(read as distress) and 1 - P(read as sound)
A policy's marker is the equal-weight mean, over its draw-revealing templates, of each template's
mean over wordings and vantage points; the spread is the range of the readings averaged. The other
templates are read and reported as context only. Arithmetic is all here, never in a prompt.

Writes signals/markers_readings.csv and signals/markers.csv (frozen later by signals/freeze.py).
Run: python -m signals.markers   (or: make markers)
"""

import csv
from collections import defaultdict
from pathlib import Path

import yaml

from signals.gold_set.labels import ai_lock_holds
from signals.jev_client import ask, noul, settings
from signals.templates.load import load_templates

ROOT = Path(__file__).resolve().parents[1]
READINGS_PATH = ROOT / "signals" / "markers_readings.csv"
MARKERS_PATH = ROOT / "signals" / "markers.csv"
READING_FIELDS = ["template", "wording", "vantage", "p_distress", "p_sound", "reading", "pair_flag", "sibling_flag",
                  "model_version"]


def config():
    with open(ROOT / "config" / "markers.yaml") as f:
        return yaml.safe_load(f)


def texts():
    """[(template ID, wording ID, filled text)]: each original, then its paraphrases."""
    with open(ROOT / "config" / "templates_fill.yaml") as f:
        fill = yaml.safe_load(f)
    with open(ROOT / "signals" / "templates" / "paraphrases.csv", newline="") as f:
        paras = list(csv.DictReader(f))
    out = []
    for t in load_templates():
        out.append((t["id"], f"{t['id']}-orig", " ".join(t["text"].split()).format(**fill)))
        out += [(t["id"], p["paraphrase_id"], p["text"].format(**fill)) for p in paras if p["template"] == t["id"]]
    return out


def questions(cfg):
    """Six one-judgment questions: each vantage point, asked both ways."""
    return {f"{v}|{way}": noul(cfg["questions"][way].format(vantage=desc))
            for v, desc in cfg["vantage_points"].items() for way in ("distress", "sound")}


# ---------- arithmetic (pure functions; tested on made-up numbers) ----------

def reading(p_distress, p_sound):
    return (p_distress + (1 - p_sound)) / 2


def pair_flag(p_distress, p_sound, limit):
    return abs(p_distress - (1 - p_sound)) > limit


def sibling_flags(rows, limit):
    """Flag a wording whose reading differs from the mean of the same template's other wordings
    (same vantage point) by more than `limit`."""
    groups = defaultdict(list)
    for r in rows:
        groups[(r["template"], r["vantage"])].append(r)
    for members in groups.values():
        for r in members:
            others = [m["reading"] for m in members if m is not r]
            r["sibling_flag"] = bool(others) and abs(r["reading"] - sum(others) / len(others)) > limit
    return rows


def policy_templates(cfg, templates):
    """{policy: [draw-revealing template IDs]} from each template's `policies`, plus B′ and C′."""
    base = {p: [t["id"] for t in templates if p in t["policies"] and t["id"] in cfg["draw_templates"]]
            for p in ("A", "B", "C", "E")}
    for name, v in cfg["variants"].items():
        base[name] = [t for t in base[v["base"]] if t not in v["drop"]]
    return {p: base[p] for p in cfg["policies"]}


def markers(rows, members):
    """{policy: (marker, low, high, n readings)}: equal-weight mean over templates of each template's mean."""
    by_template = defaultdict(list)
    for r in rows:
        by_template[r["template"]].append(r["reading"])
    out = {}
    for policy, tids in members.items():
        means = [sum(by_template[t]) / len(by_template[t]) for t in tids]
        values = [x for t in tids for x in by_template[t]]
        out[policy] = (sum(means) / len(means), min(values), max(values), len(values))
    return out


# ---------- the run ----------

def run():
    if settings()["model"] != "jev-1.13.0" or not ai_lock_holds():
        raise SystemExit("Not started: needs the jev-1.13.0 pin and release v0.1 with the AI labels locked")
    cfg = config()
    qs = questions(cfg)
    done = {}
    if READINGS_PATH.exists():                           # resume: never re-ask a wording already read
        with open(READINGS_PATH, newline="") as f:
            for r in csv.DictReader(f):
                done.setdefault(r["wording"], []).append(r)
    rows = []
    for tid, wid, text in texts():
        if wid in done:
            rows += [{**r, "p_distress": float(r["p_distress"]), "p_sound": float(r["p_sound"]),
                      "reading": float(r["reading"])} for r in done[wid]]
            continue
        res = ask(text, qs, mock=False, tag="M2.5-v0.1")
        for v in cfg["vantage_points"]:
            pd, ps = res["answers"][f"{v}|distress"]["value"], res["answers"][f"{v}|sound"]["value"]
            rows.append({"template": tid, "wording": wid, "vantage": v, "p_distress": pd, "p_sound": ps,
                         "reading": reading(pd, ps), "pair_flag": pair_flag(pd, ps, cfg["pair_flag"]),
                         "model_version": res["model"]})
        _write_readings(rows, cfg)                       # keep progress after every call
    _write_readings(rows, cfg)
    members = policy_templates(cfg, load_templates())
    result = markers(rows, members)
    with open(MARKERS_PATH, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["policy", "marker", "spread_low", "spread_high", "readings", "templates", "status"])
        for p, (m, lo, hi, n) in result.items():
            w.writerow([p, round(m, 4), round(lo, 4), round(hi, 4), n, " ".join(members[p]), "provisional"])
    print(f"wrote {MARKERS_PATH.name} and {READINGS_PATH.name} ({len(rows)} readings)")
    return result, rows


def _write_readings(rows, cfg):
    sibling_flags(rows, cfg["sibling_flag"])
    with open(READINGS_PATH, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=READING_FIELDS, extrasaction="ignore")
        w.writeheader()
        w.writerows({**r, "p_distress": round(float(r["p_distress"]), 4), "p_sound": round(float(r["p_sound"]), 4),
                     "reading": round(float(r["reading"]), 4)} for r in rows)


if __name__ == "__main__":
    run()
