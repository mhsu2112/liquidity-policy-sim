"""One live call to Jev on a made-up sentence, to check the connection (session M2.1).

The sentence is invented for this check: it is not from the corpus or the gold set. Prints the
answer, the exact model version TypeSafe returned, the tokens used, and the audit line written.
The key is never printed.

Run: make jev-hello
"""

import json

from signals.jev_client import AUDIT_LOG, JevError, ask, noul

SENTENCE = ("The regional bank said it took a small overnight loan from the central bank last week "
            "to test its systems, and repaid it the next morning.")


def main():
    try:
        result = ask(SENTENCE, {"repaid": noul("Does the text say the loan was repaid?")}, mock=False, tag="jev-hello")
    except JevError as err:
        raise SystemExit(f"Jev hello failed: {err}")
    p = result["answers"]["repaid"]["value"]
    usage = result["usage"]
    print(f"Sentence (made up): {SENTENCE}")
    print("Question: Does the text say the loan was repaid?")
    print(f"Answer: P(yes) = {p:.3f}")
    print(f"Model version: {result['model']}")
    print(f"Tokens: {usage.get('input_tokens')} in, {usage.get('output_tokens')} out")
    last = AUDIT_LOG.read_text().strip().splitlines()[-1]
    print(f"Audit line ({AUDIT_LOG.name}):\n{json.dumps(json.loads(last), indent=1)}")


if __name__ == "__main__":
    main()
