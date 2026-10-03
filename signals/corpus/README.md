# Calibration corpus (session M2.2)

> **Disclosure.** The project owner has disclosed prior support for Option B. See the
> [project README](../../README.md).

The corpus holds short public passages, 2007–2024, about banks borrowing from a central bank: the Fed's
discount window, its emergency programs, and comparable lending by other central banks. It is the
sampling frame for the gold set (Clarification 19). M2.6 later scores it to show how such borrowing has
historically been described. Rules: `docs/amendments.md` Clarifications 19, 20 and 21, with every
setting and its reason in `config/corpus.yaml`. **No passage has been sent to Jev.**

## Files

| File | Public? | Holds |
| --- | --- | --- |
| `corpus.csv` | yes | `id`, `document_id`, `url`, `pub_date`, `source_name`, `source_type`, `stratum` (period), `found_via`, `excerpt_sha256`, `eligibility` (the review's reason code), and `passage`. The passage is filled for official (Fed, ECB, BoE) and SEC text only; for news and analyst notes it is blank and only the fingerprint is published. |
| `excerpts_private.csv` | **no** (git-ignored) | `id` and `passage` for every row, including news and analyst excerpts |
| `eligibility_instruction.md` | yes | The fixed instruction every passage is reviewed against (v1) |
| `eligibility_reviews.csv` | yes | Every review decision: id, excerpt hash, keep/drop, reason code, reviewer model, instruction version, date (no text) |
| `exclusions.csv` | yes | Passages excluded by hand (e.g. a private individual's words), by id and reason only |
| `candidates/` | yes | The page lists each collector produced: links and metadata only |
| `work/` | no (git-ignored) | Raw passages, every drop with its reason, page-reading logs |

Passages are verbatim, whole sentences, at most 80 words. Full pages are read into memory, cut, and
discarded. The `excerpt_sha256` lets anyone holding the text confirm it is the same excerpt.

## How it was collected

1. **Finding pages** (`collect_*.py`):
   - Federal Reserve Board press releases, speeches and testimony, from its public listing files.
   - Bank of England news, speeches and statements (site map); ECB press releases and speeches (yearly
     listings); NY Fed Liberty Street Economics (site map).
   - SEC filings via EDGAR full-text search: every company found each year, up to two filings each, 8-Ks first
     (Clarification 21).
   - The Guardian and New York Times search services (free keys). Only what those services return is used:
     Guardian article text and NYT summaries and first paragraphs. The newspapers' own pages are never read.
   - Web searches for other news and analysis (`candidates/web_found.csv`, each with its query). Pages on
     paywalled sites are never read, and there is no fallback to archived copies.
2. **Cutting** (`extract.py`, `passages.py`). The program reads the article body only. It finds sentences
   naming a bank lending facility and adds whole neighbouring sentences up to 80 words. Each page gives up
   to 6 non-overlapping in-scope passages. Headlines, bylines, tables, fragments, paywall teasers and photo
   credits are dropped.
3. **Scope** (owner's decision). Bank borrowing only. Rate-only announcements, non-bank programs and ECB
   stimulus (TLTROs) are out.
4. **Eligibility** (Clarifications 20 and 21). A passage is kept only if it refers to borrowing from a
   central bank by a bank or banks (actual, planned, expected or avoided) or to how such borrowing is seen.
   Written rules (`eligibility.py`) proved too inaccurate on their own: wrong on 46% of kept and 11% of
   dropped passages in a fresh trial. So every in-scope passage is read against the fixed instruction
   `eligibility_instruction.md`, by Claude (model ID recorded). The reader sees the text only and never
   judges tone. The rules' verdict is kept for comparison. The owner hand-checks a random 50 decisions, and
   the agreement is published.
5. **Personal data.** Quoted words of private individuals are excluded, by rule and in the review.
6. **Build** (`build_corpus.py`), in order:
   - re-check against the current rules;
   - keep reviewed-eligible passages only (unreviewed ones are never kept);
   - hand exclusions;
   - near-duplicates removed (sharing 60% or more of their 5-word runs; the earliest is kept);
   - at most 2 passages per document;
   - filings: one per company per year.

   There is **no source-type cap in the corpus**. The 25% cap applies when M2.3 draws the gold set, and
   type shares by period are reported. Choices among equals use a seeded random order, never the wording.
   All eligible passages are kept, with at least 150 per period. A shortfall is reported before any
   gold-set draw and is never padded.

## Rebuild

```
make corpus          # collect from the web and write review batches (hours; resumable; needs the keys in .env)
                     # then review every batch against eligibility_instruction.md and import the decisions:
                     #   python -m signals.corpus.review --import <decisions.csv>
make corpus-build    # rebuild the corpus files from the reviewed passages (no internet)
make corpus-check-sheet  # the owner's random 50 decisions to hand-check
make corpus-sample   # eligible share, drop reasons, counts by period and type, 20 random rows
```

Web pages change and disappear, so a fresh collection will not match row for row. The committed
`corpus.csv` is the record.

## Counts and known gaps

(Filled in after the full collection.)
