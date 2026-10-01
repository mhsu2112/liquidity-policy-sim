"""The frozen behavioral settings may change only with an amendment (session M1.10; Rule 3).

Fails if config/params_frozen.yaml holds any value other than those whose fingerprint
was last recorded in docs/amendments.md ("params_frozen fingerprint: ..."). To change a
frozen value legitimately, add a dated amendment that records the new fingerprint.
"""

import yaml

from engine.frozen import FROZEN_PATH, frozen_fingerprint, recorded_fingerprints


def test_frozen_values_match_the_latest_amendment():
    recorded = recorded_fingerprints()
    assert recorded, "No params_frozen fingerprint recorded in docs/amendments.md"
    assert frozen_fingerprint() == recorded[-1], (
        "config/params_frozen.yaml changed without a matching entry in docs/amendments.md")


def test_every_value_is_labelled_frozen():
    text = FROZEN_PATH.read_text()
    assert "PLACEHOLDER" not in text
    values = [line for line in text.splitlines() if line.strip().startswith("value:")]
    assert len(values) == 7 and all("FROZEN at params-frozen" in v for v in values)


def test_the_engine_reads_the_frozen_file():
    from engine.episode import load_yaml
    from engine.funding import BEHAVIOR_SETTINGS_PATH
    assert BEHAVIOR_SETTINGS_PATH == FROZEN_PATH
    with open(FROZEN_PATH) as f:
        assert load_yaml("params_frozen.yaml") == yaml.safe_load(f)
