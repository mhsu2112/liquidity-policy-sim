"""The fingerprint of the frozen behavioral settings (session M1.10; Rule 3).

The fingerprint is a SHA-256 hash of the values in config/params_frozen.yaml (comments
ignored), cut to 16 characters. docs/amendments.md records it: Clarification 15 at
params-frozen, and any later amendment that changes a value records the new one.
tests/test_frozen.py fails if the file and the latest recorded fingerprint disagree.
"""

import hashlib
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
FROZEN_PATH = ROOT / "config" / "params_frozen.yaml"
AMENDMENTS_PATH = ROOT / "docs" / "amendments.md"
RECORD = re.compile(r"params_frozen fingerprint: `?([0-9a-f]{16})`?")


def frozen_fingerprint(path=FROZEN_PATH):
    with open(path) as f:
        values = yaml.safe_load(f)
    return hashlib.sha256(json.dumps(values, sort_keys=True).encode()).hexdigest()[:16]


def recorded_fingerprints(path=AMENDMENTS_PATH):
    """Every fingerprint recorded in docs/amendments.md, in the order written."""
    return RECORD.findall(Path(path).read_text())
