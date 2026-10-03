"""Read public web pages politely (session M2.2).

Pages are read into memory only; full articles are never saved (M2.2 brief). We pause
between requests to the same site. A site that refuses automated reading is skipped and logged;
there is no fallback to archived copies (Clarification 20: paywalled pages are never read).
The SEC requires a contact email on automated requests; it is read from .env and sent to
sec.gov only.
"""

import gzip
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

from signals.corpus.passages import load_settings

ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
_last_call = {}


def env(name):
    """A value from .env (or the shell). Never printed or logged."""
    if name in os.environ:
        return os.environ[name]
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text().splitlines():
            if line.startswith(name + "="):
                return line.split("=", 1)[1].split("#")[0].strip()
    return ""


def _headers(url, settings):
    agent = settings["fetch"]["user_agent"]
    if urllib.parse.urlparse(url).hostname.endswith("sec.gov"):
        # SEC fair-access rule: "name contact-email". It refuses agents that carry a web link.
        agent = f"liquidity-policy-sim research {env('SEC_CONTACT_EMAIL')}"
    return {"User-Agent": agent, "Accept-Encoding": "gzip"}


def get(url, settings=None, retries=2):
    """The body of a URL as text. Raises urllib.error.HTTPError on refusal."""
    settings = settings or load_settings()
    host = urllib.parse.urlparse(url).hostname
    wait = settings["fetch"]["pause_seconds"] - (time.time() - _last_call.get(host, 0))
    if wait > 0:
        time.sleep(wait)
    for attempt in range(retries + 1):
        _last_call[host] = time.time()
        try:
            req = urllib.request.Request(url, headers=_headers(url, settings))
            with urllib.request.urlopen(req, timeout=settings["fetch"]["timeout_seconds"]) as r:
                body = r.read()
                if r.headers.get("Content-Encoding") == "gzip":
                    body = gzip.decompress(body)
                charset = r.headers.get_content_charset() or "utf-8"
                return body.decode(charset, errors="replace")
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504) and attempt < retries:
                time.sleep(5 * (attempt + 1))   # the site is busy: back off and try again
                continue
            raise
        except (urllib.error.URLError, TimeoutError):
            if attempt < retries:
                time.sleep(5 * (attempt + 1))
                continue
            raise


def get_json(url, settings=None):
    return json.loads(get(url, settings).lstrip("\ufeff"))
