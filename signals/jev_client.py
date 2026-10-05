"""The one door to Jev, TypeSafe's text-judgment model (session M2.1).

Rules (CLAUDE.md, "Rules for Jev"):
- Calls go straight to the TypeSafe API (config/jev.yaml), with the key from TYPESAFE_API_KEY in .env.
  The key goes only into the request's Authorization header: it is never printed, logged or saved.
- Every call is written to signals/audit_log.jsonl (git-ignored): a fingerprint of the text (not the
  text), the questions, the answers, the exact model version TypeSafe returns, tokens used, and time.
- Mock mode tests the plumbing without a key. It runs only when asked for (mock=True or JEV_MOCK=1),
  never as a silent fallback, and every mock answer is labelled as not Jev. Mock answers are never results.
- One question = one judgment; answers are combined in code, never in a prompt.
- Every M2 call uses the pinned model version in config/jev.yaml (Clarification 27). If TypeSafe ever
  answers with a different version, ask() records the call and then stops with a clear message.
- No gold-set passage goes to Jev before both main-round label sets are locked (Clarification 19):
  ask() refuses such text.

Adapted from ~/Work/03-builders-lab/jev-supervision-lab/jevlab/client.py, using plain HTTP instead of
the SDK, and without the OpenRouter route.
"""

import csv
import hashlib
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path

import yaml

from signals.corpus.fetch import env

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "config" / "jev.yaml"
AUDIT_LOG = ROOT / "signals" / "audit_log.jsonl"
MOCK_LABEL = "MOCK - not Jev"


class JevError(Exception):
    """A call could not be made or was refused; the message never contains the key or the text."""


def settings():
    with open(CONFIG_PATH) as f:
        return yaml.safe_load(f)


# ---------- question builders (the API's documented shapes) ----------

def noul(instructions, true="yes", false="no", mock_hint=None):
    return {"type": "noul", "instructions": instructions, "criteria": {"true": true, "false": false},
            "_mock_hint": mock_hint}


def choice(instructions, criteria, mock_hint=None):
    return {"type": "choice", "instructions": instructions, "criteria": criteria, "_mock_hint": mock_hint}


def score(instructions, levels, mock_hint=None):
    return {"type": "score", "instructions": instructions, "criteria": list(levels), "_mock_hint": mock_hint}


def _wire(questions):
    """What is sent: the questions without our mock-only hints."""
    return {k: {kk: vv for kk, vv in q.items() if not kk.startswith("_")} for k, q in questions.items()}


# ---------- gold-set guard (Clarification 19) ----------

def _state_text(state):
    return state if isinstance(state, str) else json.dumps(state, sort_keys=True)


def gold_guard(state):
    """Refuse text containing a gold-set or practice passage until both main-round sets are locked."""
    from signals.gold_set.labels import locks
    held = {(l[0], l[1]) for l in locks()}
    if {("L1", "main"), ("L2", "main")} <= held:
        return
    text = _state_text(state)
    key_path = ROOT / "signals" / "gold_set" / "key.csv"
    private = ROOT / "signals" / "corpus" / "excerpts_private.csv"
    if key_path.exists() and private.exists():          # this computer has the texts: check containment
        with open(key_path, newline="") as f:
            gold_ids = {k["corpus_id"] for k in csv.DictReader(f)}
        with open(private, newline="") as f:
            gold_texts = [r["passage"] for r in csv.DictReader(f) if r["id"] in gold_ids]
        hit = any(t and t in text for t in gold_texts)
    else:                                                # otherwise: any draw-eligible excerpt, by fingerprint
        with open(ROOT / "signals" / "corpus" / "corpus.csv", newline="") as f:
            hashes = {r["excerpt_sha256"] for r in csv.DictReader(f) if r["gold_set_eligible"] == "Y"}
        hit = hashlib.sha256(text.encode("utf-8")).hexdigest() in hashes
    if hit:
        raise JevError("refused: the text contains a gold-set passage, and both main-round labels are not yet "
                       "locked (Clarification 19)")


# ---------- the call ----------

def ask(state, questions, *, mock=None, tag=""):
    """Ask every question about one state in a single call. Returns {"model", "answers", "usage", "mode"}.

    Normalised answers: noul -> value = P(yes); choice -> value = chosen option; score -> value =
    probability-weighted level. Confidence and probabilities are kept as returned.
    """
    mock = (os.environ.get("JEV_MOCK") == "1") if mock is None else mock
    gold_guard(state)
    wire = _wire(questions)
    t0 = time.time()
    if mock:
        result = {"model": MOCK_LABEL, "answers": _mock(state, questions), "usage": {"input_tokens": 0, "output_tokens": 0}}
    else:
        result = _live(state, wire)
    answers = {k: _normalise(v) for k, v in result["answers"].items()}
    out = {"model": result["model"], "answers": answers, "usage": result.get("usage", {}),
           "mode": "mock" if mock else "live"}
    _audit(state, wire, answers, result, out["mode"], tag, time.time() - t0)
    pinned = settings()["model"]
    if not mock and result["model"] != pinned:     # Clarification 27: no M2 result may mix model versions
        raise JevError(f"model version changed: requested {pinned}, TypeSafe answered with {result['model']}. "
                       "Stop and report the change (Clarification 27); the call is in the audit log.")
    return out


def _post(url, body, key, timeout):
    """One HTTP request (replaced in tests). Returns (status, parsed JSON or text)."""
    req = urllib.request.Request(url, data=json.dumps(body).encode("utf-8"), method="POST",
                                 headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as err:
        return err.code, err.read().decode("utf-8", errors="replace")[:500]


def _live(state, wire):
    key = env("TYPESAFE_API_KEY")
    if not key:
        raise JevError("TYPESAFE_API_KEY is not set in .env. Live calls need it; use mock=True only to test plumbing.")
    s = settings()
    body = {"state": state, "model": s["model"], "questions": wire}
    for attempt in range(s["retries"] + 1):
        status, data = _post(s["endpoint"], body, key, s["timeout_seconds"])
        if status == 200:
            return data
        if status in (429, 529) and attempt < s["retries"]:      # rate limit / overloaded: back off and retry
            time.sleep(s["backoff_seconds"] * 2 ** attempt)
            continue
        detail = data if isinstance(data, str) else json.dumps(data)[:500]
        raise JevError(f"TypeSafe API returned {status}: {detail}")
    raise JevError("TypeSafe API: retries exhausted")


def _normalise(a):
    t = a.get("type")
    if t == "noul":
        return {"type": "noul", "value": float(a["noul"])}
    if t == "choice":
        return {"type": "choice", "value": a["choice"], "confidence": a.get("confidence"),
                "probabilities": a.get("probabilities")}
    if t == "score":
        return {"type": "score", "value": a["score"], "confidence": a.get("confidence"),
                "probabilities": a.get("probabilities"), "legend": a.get("legend")}
    return a


def _audit(state, wire, answers, result, mode, tag, seconds):
    """One line per call. The text is stored only as a fingerprint; the key never appears."""
    text = _state_text(state)
    usage = result.get("usage", {})
    rec = {"timestamp": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "tag": tag, "mode": mode,
           "model_version": result.get("model"), "state_sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
           "state_chars": len(text), "questions": wire, "answers": answers,
           "input_tokens": usage.get("input_tokens"), "output_tokens": usage.get("output_tokens"),
           "seconds": round(seconds, 3)}
    AUDIT_LOG.parent.mkdir(exist_ok=True)
    with open(AUDIT_LOG, "a") as f:
        f.write(json.dumps(rec) + "\n")
    return rec


# ---------- mock (plumbing only; never a result) ----------

def _mock(state, questions):
    """Deterministic fake answers from a hash of the text and question (or a keyword hint). Not Jev."""
    text = _state_text(state).lower()
    out = {}
    for name, q in questions.items():
        u = int(hashlib.sha256(f"{text}|{name}".encode()).hexdigest()[:8], 16) / 0xFFFFFFFF
        hint = q.get("_mock_hint")
        if q["type"] == "noul":
            p = 0.9 if hint and hint.lower() in text else 0.1 + 0.3 * u
            out[name] = {"type": "noul", "noul": round(p, 3)}
        elif q["type"] == "choice":
            opts = list(q["criteria"])
            pick = hint if hint in opts else opts[int(u * len(opts)) % len(opts)]
            out[name] = {"type": "choice", "choice": pick, "confidence": 0.5,
                         "probabilities": {o: (0.6 if o == pick else 0.4 / max(1, len(opts) - 1)) for o in opts}}
        else:
            n = len(q["criteria"])
            level = int(u * n) % n
            out[name] = {"type": "score", "score": float(level), "confidence": 0.5,
                         "probabilities": {str(i): (1.0 if i == level else 0.0) for i in range(n)},
                         "legend": {str(i): l for i, l in enumerate(q["criteria"])}}
    return out
