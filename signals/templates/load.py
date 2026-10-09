"""Read the disclosure templates (signals/templates/disclosure_templates.yaml), frozen at pre-registration-v1.

The frozen file has one YAML defect: P2's `realism` note contains a second colon ("Decision 3-1: B's
ratio ..."), which a strict YAML reader rejects. The file must not change without an amendment, so
this loader quotes each `realism` note in memory before parsing. No template text is touched: the
`text` fields are read exactly as written.
"""

import re
from pathlib import Path

import yaml

TEMPLATES_PATH = Path(__file__).resolve().parent / "disclosure_templates.yaml"


def load_templates(path=TEMPLATES_PATH):
    raw = Path(path).read_text()
    quoted = re.sub(r"^(\s+realism: )(.*)$", lambda m: m.group(1) + '"' + m.group(2).replace('"', '\\"') + '"',
                    raw, flags=re.MULTILINE)
    return yaml.safe_load(quoted)["templates"]
