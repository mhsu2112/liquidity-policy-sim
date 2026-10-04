"""Lock, compare and publish the labelers' answers (session M2.3; Clarification 19).

  lock FILE         check a returned CSV, record its SHA-256 in locks.md, commit and push locks.md only.
                    Refuses a wrong file name, wrong IDs, or any blank or invalid answer. Never prints
                    answers. A labeler's round can be locked only once (no re-labeling after a lock).
  compare-practice  show where the two practice sets differ, side by side. Refuses main-round files.
  publish           only after both main-round locks: check each file still matches its fingerprint,
                    then commit labels_L1.csv and labels_L2.csv (ID, Answer, Unsure, Note) and the key.

Labelers return one tab saved as CSV (labeling guide), named gold_set_<L1|L2>_<practice|main>.csv.
Locked files are kept in incoming/ (git-ignored) until publication.

Run: python -m signals.gold_set.labels lock FILE | compare-practice | publish
     (or: make lock-labels FILE=...; make compare-practice; make publish-labels)
"""

import csv
import datetime
import hashlib
import re
import shutil
import subprocess
import sys
from pathlib import Path

from signals.gold_set.draw import KEY_PATH, SUMMARY_PATH

HERE = Path(__file__).resolve().parent
INCOMING = HERE / "incoming"
LOCKS_PATH = HERE / "locks.md"
NAME = re.compile(r"^gold_set_(L1|L2)_(practice|main)\.csv$")
ANSWERS = {"1", "2", "3", "4", "N"}
LOCK_HEADER = ("# Gold-set label locks\n\nEach row fingerprints a labeler's returned file (SHA-256 of the file's bytes), "
               "recorded before either labeler's answers are seen (Clarification 19). Answers are published only after "
               "both main-round locks, and each published file must match its fingerprint.\n\n"
               "| Date | Labeler | Round | File | Rows | SHA-256 |\n| --- | --- | --- | --- | --- | --- |\n")


class Refused(Exception):
    """The file cannot be accepted; the message says why, without showing any answer."""


def git(*args):
    """Run git in the project folder (replaced in tests)."""
    subprocess.run(["git", *args], cwd=HERE.parents[1], check=True)


def expected_ids(round_):
    """The IDs a round must contain exactly, from the public draw summary."""
    with open(SUMMARY_PATH, newline="") as f:
        n = sum(int(r["count"]) for r in csv.DictReader(f) if r["round"] == round_)
    return {f"G{i:03d}" for i in range(1, n + 1)} if round_ == "main" else {f"PR{i:02d}" for i in range(1, n + 1)}


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def read_labels(path):
    """Rows of (ID, Answer, Unsure, Note) from a returned CSV; Excel may add a byte-order mark."""
    with open(path, newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))
    if not rows or not {"ID", "Answer", "Unsure", "Note"} <= set(rows[0]):
        raise Refused("the file needs the columns ID, Answer, Unsure and Note")
    return [{k: (r.get(k) or "").strip() for k in ("ID", "Answer", "Unsure", "Note")} for r in rows]


def check(path):
    """(labeler, round, rows) if the file is acceptable; otherwise Refused, naming problem rows by ID only."""
    m = NAME.match(Path(path).name)
    if not m:
        raise Refused("file name must be gold_set_L1_main.csv, gold_set_L2_main.csv, or the _practice equivalents")
    labeler, round_ = m.groups()
    rows = read_labels(path)
    ids = [r["ID"] for r in rows]
    want = expected_ids(round_)
    if len(ids) != len(set(ids)) or set(ids) != want:
        raise Refused(f"the IDs do not match the {round_} round exactly ({len(set(ids) & want)} of {len(want)} "
                      f"present, {len(set(ids) - want)} unexpected, {len(ids) - len(set(ids))} repeated)")
    blank = [r["ID"] for r in rows if not r["Answer"]]
    invalid = [r["ID"] for r in rows if r["Answer"] and r["Answer"].upper() not in ANSWERS]
    unsure = [r["ID"] for r in rows if r["Unsure"].upper() not in ("", "Y")]
    problems = [f"{len(blank)} blank answer(s): {', '.join(sorted(blank)[:10])}" if blank else "",
                f"{len(invalid)} answer(s) not 1, 2, 3, 4 or N: {', '.join(sorted(invalid)[:10])}" if invalid else "",
                f"{len(unsure)} Unsure value(s) not Y or blank: {', '.join(sorted(unsure)[:10])}" if unsure else ""]
    if any(problems):
        raise Refused("; ".join(p for p in problems if p))
    return labeler, round_, rows


def locks():
    """[(labeler, round, file, rows, sha)] already recorded."""
    if not LOCKS_PATH.exists():
        return []
    out = []
    for line in LOCKS_PATH.read_text().splitlines():
        cells = [c.strip() for c in line.strip("|").split("|")]
        if len(cells) == 6 and re.fullmatch(r"[0-9a-f]{64}", cells[5]):
            out.append((cells[1], cells[2], cells[3], cells[4], cells[5]))
    return out


def lock(path):
    labeler, round_, rows = check(path)
    if any(l[0] == labeler and l[1] == round_ for l in locks()):
        raise Refused(f"{labeler} {round_} is already locked; a locked set is never replaced")
    INCOMING.mkdir(exist_ok=True)
    kept = INCOMING / Path(path).name
    if Path(path).resolve() != kept.resolve():
        shutil.copyfile(path, kept)
    digest = sha256(kept)
    if not LOCKS_PATH.exists():
        LOCKS_PATH.write_text(LOCK_HEADER)
    with open(LOCKS_PATH, "a") as f:
        f.write(f"| {datetime.date.today().isoformat()} | {labeler} | {round_} | {kept.name} | {len(rows)} | {digest} |\n")
    git("add", str(LOCKS_PATH))
    git("commit", "-m", f"Lock {labeler} {round_} labels (fingerprint only)", "--", str(LOCKS_PATH))
    git("push")
    print(f"Locked {labeler} {round_}: {len(rows)} rows, SHA-256 {digest}. locks.md committed and pushed.")


def compare_practice():
    files = [INCOMING / f"gold_set_{l}_practice.csv" for l in ("L1", "L2")]
    for f in files:
        if not f.exists():
            raise Refused(f"missing {f.name} in incoming/")
    sets = []
    for f in files:
        labeler, round_, rows = check(f)
        if round_ != "practice" or any(not r["ID"].startswith("PR") for r in rows):
            raise Refused("compare-practice reads practice files only")
        sets.append({r["ID"]: r for r in rows})
    text = {}
    if KEY_PATH.exists():
        from signals.corpus.build_corpus import PRIVATE_PATH
        with open(PRIVATE_PATH, newline="") as f:
            passages = {r["id"]: r["passage"] for r in csv.DictReader(f)}
        with open(KEY_PATH, newline="") as f:
            text = {k["gold_id"]: passages.get(k["corpus_id"], "") for k in csv.DictReader(f) if k["round"] == "practice"}
    a, b = sets
    differ = [i for i in sorted(a) if a[i]["Answer"].upper() != b[i]["Answer"].upper()]
    print(f"Practice: the labelers agree on {len(a) - len(differ)} of {len(a)}.")
    for i in differ:
        print(f"\n{i}  L1: {a[i]['Answer']}{' (unsure)' if a[i]['Unsure'] else ''}  {a[i]['Note']}")
        print(f"     L2: {b[i]['Answer']}{' (unsure)' if b[i]['Unsure'] else ''}  {b[i]['Note']}")
        if text.get(i):
            print(f"     {text[i]}")


def publish():
    held = {(l[0], l[1]): l for l in locks()}
    for labeler in ("L1", "L2"):
        if (labeler, "main") not in held:
            raise Refused(f"{labeler} main round is not locked; publication waits for both main locks")
    files = {l: INCOMING / f"gold_set_{l}_main.csv" for l in ("L1", "L2")}
    for labeler, f in files.items():          # check both before writing anything
        if not f.exists() or sha256(f) != held[(labeler, "main")][4]:
            raise Refused(f"{f.name} is missing or no longer matches its locked fingerprint")
    written = []
    for labeler, f in files.items():
        out = HERE / f"labels_{labeler}.csv"
        with open(out, "w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=["ID", "Answer", "Unsure", "Note"])
            w.writeheader()
            w.writerows(sorted(read_labels(f), key=lambda r: r["ID"]))
        written.append(str(out))
    key = str(KEY_PATH)
    git("add", "-f", key, *written)          # -f: the key is git-ignored until now (Clarification 24)
    git("commit", "-m", "Publish gold-set labels L1 and L2 and the ID key (both main rounds locked)", "--", key, *written)
    print("Published labels_L1.csv, labels_L2.csv and key.csv (committed; push when ready).")


if __name__ == "__main__":
    try:
        cmd = sys.argv[1] if len(sys.argv) > 1 else ""
        if cmd == "lock" and len(sys.argv) == 3:
            lock(sys.argv[2])
        elif cmd == "compare-practice":
            compare_practice()
        elif cmd == "publish":
            publish()
        else:
            sys.exit("usage: python -m signals.gold_set.labels lock FILE | compare-practice | publish")
    except Refused as err:
        sys.exit(f"REFUSED: {err}")
