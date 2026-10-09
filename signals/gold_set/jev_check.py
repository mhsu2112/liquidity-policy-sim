"""Run Jev once on the gold set (v0.1 model-to-model check; Clarification 30, Part A).

Before any call it checks that the model is pinned to jev-1.13.0, that the AI labels are locked
and unchanged (Amendment 7), and that the question comes from the labeling guide at commit
a0f08db. One Score question per passage: the guide's question, its four level descriptions word
for word, and the passage text as the only state. Each passage is asked once; an interrupted run
continues without re-asking anything already answered.

Writes signals/gold_set/jev_answers.csv: ID, round, label (most likely level, 1-4), p1-p4,
expected score (1 + probability-weighted level), model version. No passage text.

Run: python -m signals.gold_set.jev_check   (or: make gold-check)
"""

import csv
import re
import subprocess
from pathlib import Path

from signals.corpus.build_corpus import PRIVATE_PATH
from signals.gold_set.draw import KEY_PATH
from signals.gold_set.labels import ai_lock_holds
from signals.jev_client import ask, score, settings

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
ANSWERS_PATH = HERE / "jev_answers.csv"
GUIDE_COMMIT = "a0f08dbd2f1a55b861874ad6d855b08166cee4ee"   # Clarification 30, Part A, item 1
PINNED = "jev-1.13.0"                                       # Clarification 27
LEVEL_WORDS = ["Reassuring", "Routine", "Some Concern", "Clear Distress"]
FIELDS = ["ID", "round", "label", "p1", "p2", "p3", "p4", "expected_score", "model_version"]


class NotReady(Exception):
    """A start check failed; nothing has been sent to Jev."""


def guide_question(commit=GUIDE_COMMIT):
    """(instructions, four level texts) copied word for word from the guide at the fixed commit."""
    text = subprocess.run(["git", "show", f"{commit}:signals/gold_set/labeling-guide.md"], cwd=ROOT,
                          capture_output=True, text=True, check=True).stdout
    instructions = re.search(r"\*\*(How does this passage[^*]+)\*\*", text).group(1)
    levels = [re.search(r"\| \*\*" + w + r"\*\* \| ([^|]+) \|", text).group(1).strip() for w in LEVEL_WORDS]
    return instructions, levels


def start_checks():
    if settings()["model"] != PINNED:
        raise NotReady(f"config/jev.yaml must request {PINNED} (Clarification 27)")
    if not ai_lock_holds():
        raise NotReady("labels_AI.csv is not locked, has changed since its lock, or the release is not v0.1 (Amendment 7)")


def passages():
    """[(gold ID, round, text)] for the main and practice sets, in ID order."""
    with open(PRIVATE_PATH, newline="") as f:
        text = {r["id"]: r["passage"] for r in csv.DictReader(f)}
    with open(KEY_PATH, newline="") as f:
        return sorted((k["gold_id"], k["round"], text[k["corpus_id"]]) for k in csv.DictReader(f))


def to_row(gold_id, round_, result):
    """Most likely level and expected score from one Score answer (levels 0-3 from Jev -> 1-4)."""
    a = result["answers"]["level"]
    probs = [float(a["probabilities"][str(i)]) for i in range(4)]
    return {"ID": gold_id, "round": round_, "label": probs.index(max(probs)) + 1,
            **{f"p{i + 1}": round(p, 6) for i, p in enumerate(probs)},
            "expected_score": round(float(a["value"]) + 1, 6), "model_version": result["model"]}


def run():
    start_checks()
    instructions, levels = guide_question()
    question = {"level": score(instructions, levels)}
    done = set()
    if ANSWERS_PATH.exists():
        with open(ANSWERS_PATH, newline="") as f:
            done = {r["ID"] for r in csv.DictReader(f)}
    todo = [p for p in passages() if p[0] not in done]
    new_file = not ANSWERS_PATH.exists()
    with open(ANSWERS_PATH, "a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new_file:
            w.writeheader()
        for i, (gold_id, round_, text) in enumerate(todo, 1):
            w.writerow(to_row(gold_id, round_, ask(text, question, mock=False, tag="M2.4-v0.1")))
            f.flush()                       # each answer is kept as soon as it arrives
            if i % 25 == 0:
                print(f"  {i}/{len(todo)} passages answered", flush=True)
    print(f"done: {len(done) + len(todo)} passages answered in total ({len(todo)} this run)")


if __name__ == "__main__":
    try:
        run()
    except NotReady as err:
        raise SystemExit(f"Not started: {err}")
