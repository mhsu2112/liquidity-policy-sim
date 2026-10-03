"""Cut short verbatim passages about central-bank borrowing out of a page (session M2.2).

A page's text is split into sentences. A sentence that names a central-bank lending
facility for banks is an "anchor". Around each anchor we add whole neighbouring
sentences, one at a time, while the passage stays within the word limit. Nothing is
reworded: a passage is always a run of the page's own sentences.

Whether a passage is in scope is decided by the rules in config/corpus.yaml only.
Nothing here judges whether the passage sounds reassuring or distressed.
"""

import hashlib
import html
import re
from html.parser import HTMLParser
from pathlib import Path

import yaml

CONFIG_PATH = Path(__file__).resolve().parents[2] / "config" / "corpus.yaml"


def load_settings(path=CONFIG_PATH):
    with open(path) as f:
        return yaml.safe_load(f)


# ---------- page text ----------

# Where pages keep the article itself, most reliable first: the Fed's <div id="article">, then
# the standard <article> and <main> elements, then a generic <div id="content">. Reading only
# that part keeps site menus, cookie notices and "related stories" out of the passages.
_BODY_REGIONS = [("div", "article"), ("article", None), ("main", None), ("div", "content")]
_MIN_BODY_WORDS = 100   # a marked region shorter than this is probably not the article


class _TextGrabber(HTMLParser):
    """Keeps visible text, for the whole page and separately for each article-body region."""
    SKIP = {"script", "style", "noscript", "nav", "header", "footer", "aside", "form", "svg", "button"}
    BLOCK = {"p", "div", "br", "li", "h1", "h2", "h3", "h4", "h5", "h6", "tr", "td", "section", "article", "blockquote"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts, self.skip_depth = [], 0
        self.region_parts = {r: [] for r in _BODY_REGIONS}
        self.region_depth = {r: 0 for r in _BODY_REGIONS}   # 0 = not inside; else nesting of that tag
        self.region_done = set()                           # only the first region of each kind is read

    def _emit(self, text):
        self.parts.append(text)
        for r, depth in self.region_depth.items():
            if depth:
                self.region_parts[r].append(text)

    def handle_starttag(self, tag, attrs):
        for r in _BODY_REGIONS:
            if tag != r[0]:
                continue
            if self.region_depth[r]:
                self.region_depth[r] += 1
            elif r not in self.region_done and (r[1] is None or dict(attrs).get("id") == r[1]):
                self.region_depth[r] = 1
        if tag in self.SKIP:
            self.skip_depth += 1
        elif tag in self.BLOCK:
            self._emit("\n")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip_depth:
            self.skip_depth -= 1
        elif tag in self.BLOCK:
            self._emit("\n")
        for r in _BODY_REGIONS:
            if tag == r[0] and self.region_depth[r]:
                self.region_depth[r] -= 1
                if not self.region_depth[r]:
                    self.region_done.add(r)

    def handle_data(self, data):
        if not self.skip_depth:
            self._emit(data)


def html_to_text(raw_html):
    """Visible text of a web page's article body (or the whole page if no body is marked), one paragraph per line."""
    grabber = _TextGrabber()
    grabber.feed(raw_html)
    for r in _BODY_REGIONS:
        body = clean_text("".join(grabber.region_parts[r]))
        if word_count(body) >= _MIN_BODY_WORDS:
            return body
    return clean_text("".join(grabber.parts))


def clean_text(text):
    text = html.unescape(text).replace("\xa0", " ")
    lines = [re.sub(r"\s+", " ", line).strip() for line in text.split("\n")]
    return "\n".join(line for line in lines if line)


def page_fingerprint(text):
    """SHA-256 of the page text, so anyone can check a passage came from that page."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------- sentences ----------

# A sentence ends at . ! or ? (perhaps followed by a closing quote) then a space and a capital
# letter, digit or opening quote, but not after common abbreviations ("U.S.", "Mr.", "Inc.")
# that would split a sentence in the wrong place.
_SENTENCE_END = re.compile(r'[.!?]["”’)]?\s+(?=["“‘(]?[A-Z0-9$])')
_ABBREVIATIONS = {"u.s.", "u.k.", "mr.", "ms.", "mrs.", "dr.", "inc.", "corp.", "co.", "no.", "st.",
                  "jr.", "vs.", "e.g.", "i.e.", "jan.", "feb.", "aug.", "sept.", "oct.", "nov.", "dec."}


def _split_paragraph(para):
    sentences, start = [], 0
    for m in _SENTENCE_END.finditer(para):
        last_word = para[start:m.start() + 1].split()[-1].lower() if para[start:m.start() + 1].split() else ""
        if last_word in _ABBREVIATIONS or re.fullmatch(r"[a-z]\.", last_word):
            continue   # "U.S." or an initial like "J." is not the end of a sentence
        sentences.append(para[start:m.end()].strip())
        start = m.end()
    sentences.append(para[start:].strip())
    return [s for s in sentences if s]


def split_sentences(text):
    """Sentences in page order. Paragraph breaks always end a sentence."""
    out = []
    for para in text.split("\n"):
        out.extend(_split_paragraph(para))
    return out


def word_count(text):
    return len(text.split())


# ---------- scope ----------

def _compile(patterns):
    return [re.compile(p, re.IGNORECASE) for p in patterns]


class Scope:
    """The plan's scope rule: a bank lending facility is named, and borrowing, access or use is discussed.

    Broad terms ("lender of last resort", LTROs) count only when the passage also says borrowing
    happened or was weighed (the stricter "strong usage" test), because in the trial they mostly
    appeared in general policy talk.
    """

    def __init__(self, settings):
        s = settings["scope"]
        self.facility = _compile(s["facility_patterns"])
        self.weak = _compile(s["weak_facility_patterns"])
        self.usage = _compile(s["usage_patterns"])
        self.strong_usage = re.compile(s["strong_usage_pattern"], re.IGNORECASE)
        self.exclude = _compile(s["exclude_patterns"])

    def is_anchor(self, sentence):
        return any(p.search(sentence) for p in self.facility + self.weak)

    def passage_in_scope(self, passage):
        for p in self.exclude:                      # set aside non-bank and stimulus programs ...
            passage = p.sub(" ", passage)
        if any(p.search(passage) for p in self.facility):   # ... then a bank facility must remain
            # The borrowing word must sit outside the facility's own name: "marginal lending facility"
            # alone (an ECB rate decision) is not talk of borrowing (trial-round fix).
            rest = passage
            for p in self.facility:
                rest = p.sub(" ", rest)
            return any(p.search(rest) for p in self.usage)
        if any(p.search(passage) for p in self.weak):
            return bool(self.strong_usage.search(passage))
        return False


# ---------- cutting ----------

_ENDS_LIKE_SENTENCE = re.compile(r'[.!?]["”’)]?$')


def _grow(sentences, i, max_words):
    """Start from anchor sentence i; add the next sentence, then the previous, while within the limit.

    Lines with no closing punctuation (headlines, bylines, captions) are never added: they are
    page furniture rather than the article's sentences.
    """
    lo = hi = i
    words = word_count(sentences[i])
    if words > max_words or not _ENDS_LIKE_SENTENCE.search(sentences[i]):
        return None
    grew = True
    while grew:
        grew = False
        for side in ("next", "prev"):
            j = hi + 1 if side == "next" else lo - 1
            if (0 <= j < len(sentences) and words + word_count(sentences[j]) <= max_words
                    and _ENDS_LIKE_SENTENCE.search(sentences[j])):
                words += word_count(sentences[j])
                lo, hi = (lo, j) if side == "next" else (j, hi)
                grew = True
    return lo, hi


def cut_passages(text, settings, scope=None, eligibility=None, drops=None):
    """Verbatim passages from one page, in page order: within the word limits, in scope, and free of
    private individuals' words (by rule). Passages never overlap.

    Eligibility does not filter here (Clarification 21): every in-scope passage, up to
    `max_candidates_per_page`, goes on to be read and decided by the reviewer. If `drops` is a list,
    each rejected candidate is appended to it as (reason, passage) for the drop log.
    """
    from signals.corpus.eligibility import Eligibility   # here to avoid a circular import
    scope = scope or Scope(settings)
    eligibility = eligibility or Eligibility(settings)
    drops = drops if drops is not None else []
    p = settings["passage"]
    for pattern in p["strip_patterns"]:     # page furniture inside the article body
        text = re.sub(pattern, "", text, flags=re.MULTILINE)
    sentences = split_sentences(text)
    used, out = set(), []
    for i, sentence in enumerate(sentences):
        if len(out) >= p["max_candidates_per_page"]:
            break
        if i in used or not scope.is_anchor(sentence):
            continue
        span = _grow(sentences, i, p["max_words"])
        if span is None:
            drops.append(("sentence_too_long_or_heading", sentence))
            continue
        if used.intersection(range(span[0], span[1] + 1)):
            continue   # overlaps a passage already kept; the same words are not counted twice
        passage = " ".join(sentences[span[0]:span[1] + 1])
        if not reads_cleanly(passage, p):
            drops.append(("quality", passage))
            continue
        if not scope.passage_in_scope(passage):
            drops.append(("out_of_scope", passage))
            continue
        if eligibility.personal_data(passage):
            drops.append(("personal_data", passage))
            continue
        used.update(range(span[0], span[1] + 1))
        out.append(passage)
    return out


def reads_cleanly(passage, p):
    """Quality rules from config/corpus.yaml `passage`: long enough, whole sentences, not a table, no site furniture."""
    words = passage.split()
    if len(words) < p["min_words"]:
        return False
    if not re.search(p["start_pattern"], passage) or not re.search(p["end_pattern"], passage):
        return False
    if sum(any(ch.isdigit() for ch in w) for w in words) / len(words) > p["max_number_share"]:
        return False
    return not any(re.search(pattern, passage, re.IGNORECASE) for pattern in p["reject_patterns"])


def stratum_of(pub_date, settings):
    """Clarification 19 period for an ISO date (YYYY-MM-DD); None if outside 2007-2024."""
    for name, (start, end) in settings["strata"].items():
        if start <= pub_date <= end:
            return name
    return None
