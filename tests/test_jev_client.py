"""Checks on the Jev client (session M2.1).

Mechanics only, with no live network call: the HTTP layer is replaced by a stand-in. Checks the
request shape, that the model version and tokens are recorded, retries, the audit line (no key, no
text), mock labelling, the missing-key error, the gold-set guard, and that the key appears in no
tracked file. Nothing here judges any answer Jev gives.
"""

import csv
import json
import subprocess

import pytest

import signals.jev_client as jc
from signals.corpus.fetch import env

FAKE_KEY = "ts-test-not-a-real-key-123"
REPLY = {"model": "jev-1.13.0", "answers": {"q": {"type": "noul", "noul": 0.93}},
         "usage": {"input_tokens": 41, "output_tokens": 1}}


@pytest.fixture
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(jc, "AUDIT_LOG", tmp_path / "audit.jsonl")
    monkeypatch.setattr(jc, "env", lambda name: FAKE_KEY if name == "TYPESAFE_API_KEY" else "")
    monkeypatch.setattr(jc, "gold_guard", lambda state: None)
    monkeypatch.setattr(jc.time, "sleep", lambda s: None)
    sent = []

    def fake_post(url, body, key, timeout, replies=[]):
        sent.append({"url": url, "body": body, "key": key})
        return replies.pop(0) if replies else (200, REPLY)
    monkeypatch.setattr(jc, "_post", fake_post)
    return tmp_path, sent, fake_post


def test_request_follows_the_api_contract_and_hints_are_not_sent(isolated):
    _, sent, _ = isolated
    jc.ask("A bank borrowed.", {"q": jc.noul("Did a bank borrow?", mock_hint="borrowed")}, mock=False)
    body = sent[0]["body"]
    assert sent[0]["url"] == "https://api.typesafe.ai/v1/systemone" and sent[0]["key"] == FAKE_KEY
    assert body["model"] == "jev-1.13.0" and body["state"] == "A bank borrowed."     # Clarification 27: pinned
    assert body["questions"]["q"] == {"type": "noul", "instructions": "Did a bank borrow?",
                                      "criteria": {"true": "yes", "false": "no"}}


def test_model_version_and_tokens_are_recorded(isolated):
    tmp, _, _ = isolated
    out = jc.ask("A bank borrowed.", {"q": jc.noul("Did a bank borrow?")}, mock=False, tag="t")
    assert out["model"] == "jev-1.13.0" and out["usage"] == {"input_tokens": 41, "output_tokens": 1}
    assert out["answers"]["q"] == {"type": "noul", "value": 0.93}
    rec = json.loads((tmp / "audit.jsonl").read_text().splitlines()[-1])
    assert rec["model_version"] == "jev-1.13.0" and rec["input_tokens"] == 41 and rec["output_tokens"] == 1
    for field in ("timestamp", "state_sha256", "questions", "answers", "mode"):
        assert field in rec


def test_audit_line_holds_neither_the_key_nor_the_text(isolated):
    tmp, _, _ = isolated
    text = "A distinctive sentence about the Bank borrowing overnight."
    jc.ask(text, {"q": jc.noul("Did a bank borrow?")}, mock=False)
    line = (tmp / "audit.jsonl").read_text()
    assert FAKE_KEY not in line and text not in line


def test_retries_on_429_and_529_but_not_on_401(isolated, monkeypatch):
    _, sent, fake_post = isolated
    replies = [(429, "slow down"), (529, "busy"), (200, REPLY)]
    monkeypatch.setattr(jc, "_post", lambda *a: (sent.append(1), replies.pop(0))[1])
    assert jc.ask("x y", {"q": jc.noul("?")}, mock=False)["model"] == "jev-1.13.0" and len(sent) == 3
    monkeypatch.setattr(jc, "_post", lambda *a: (401, "bad key"))
    with pytest.raises(jc.JevError, match="401") as err:
        jc.ask("x y", {"q": jc.noul("?")}, mock=False)
    assert FAKE_KEY not in str(err.value)


def test_missing_key_is_an_error_not_a_silent_mock(isolated, monkeypatch):
    monkeypatch.setattr(jc, "env", lambda name: "")
    with pytest.raises(jc.JevError, match="TYPESAFE_API_KEY is not set"):
        jc.ask("x y", {"q": jc.noul("?")}, mock=False)


def test_mock_answers_are_labelled_and_make_no_call(isolated):
    tmp, sent, _ = isolated
    out = jc.ask("A bank borrowed.", {"q": jc.noul("Did a bank borrow?", mock_hint="borrowed"),
                                      "s": jc.score("How severe?", ["low", "mid", "high"])}, mock=True)
    assert out["mode"] == "mock" and out["model"] == jc.MOCK_LABEL and not sent
    assert json.loads((tmp / "audit.jsonl").read_text().splitlines()[-1])["model_version"] == jc.MOCK_LABEL


def test_gold_guard_refuses_a_gold_passage_before_both_locks(monkeypatch):
    import signals.gold_set.labels as labels
    monkeypatch.setattr(labels, "locks", lambda: [])
    key = jc.ROOT / "signals" / "gold_set" / "key.csv"
    private = jc.ROOT / "signals" / "corpus" / "excerpts_private.csv"
    if not (key.exists() and private.exists()):
        pytest.skip("gold-set key and excerpts are not on this computer")
    with open(key, newline="") as f:
        first = next(csv.DictReader(f))["corpus_id"]
    with open(private, newline="") as f:
        passage = next(r["passage"] for r in csv.DictReader(f) if r["id"] == first)
    with pytest.raises(jc.JevError, match="gold-set passage") as err:
        jc.gold_guard({"text": "Context. " + passage})
    assert passage not in str(err.value)
    jc.gold_guard("A made-up sentence that is in no gold-set passage.")      # passes


def test_the_key_appears_in_no_tracked_file():
    key = env("TYPESAFE_API_KEY")
    if not key:
        pytest.skip("no TYPESAFE_API_KEY on this computer")
    files = subprocess.run(["git", "ls-files", "-z"], cwd=jc.ROOT, capture_output=True, check=True).stdout.split(b"\0")
    leaks = [f.decode() for f in files if f and (jc.ROOT / f.decode()).is_file()
             and key.encode() in (jc.ROOT / f.decode()).read_bytes()]
    assert not leaks, f"the TypeSafe key appears in tracked file(s): {leaks}"     # names files only, never the key


def test_a_different_model_version_stops_the_run_and_is_recorded(isolated, monkeypatch):
    tmp, _, _ = isolated
    monkeypatch.setattr(jc, "_post", lambda *a: (200, {**REPLY, "model": "jev-1.14.0"}))
    with pytest.raises(jc.JevError, match="model version changed: requested jev-1.13.0, TypeSafe answered with jev-1.14.0"):
        jc.ask("A bank borrowed.", {"q": jc.noul("Did a bank borrow?")}, mock=False)
    assert json.loads((tmp / "audit.jsonl").read_text().splitlines()[-1])["model_version"] == "jev-1.14.0"
