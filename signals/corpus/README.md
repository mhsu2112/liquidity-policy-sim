# Calibration corpus (session M2.2)

> **Disclosure.** The project owner has disclosed prior support for Option B. See the
> [project README](../../README.md).

The corpus holds short public passages, 2007–2024, about banks borrowing from a central bank: the Fed's
discount window, its emergency programs, and comparable lending by other central banks. It is the
sampling frame for the gold set (Clarification 19). M2.6 later scores it to show how such borrowing has
historically been described. Rules: `docs/amendments.md` Clarifications 19 and 20, with every setting
and its reason in `config/corpus.yaml`. **No passage has been sent to Jev.**

## Files

| File | Public? | Holds |
| --- | --- | --- |
| `corpus.csv` | yes | `id`, `document_id`, `url`, `pub_date`, `source_name`, `source_type`, `stratum` (period), `found_via`, `excerpt_sha256`, and `passage`. The passage is filled for official (Fed, ECB, BoE) and SEC text only; for news and analyst notes it is blank and only the fingerprint is published. |
| `excerpts_private.csv` | **no** (git-ignored) | `id` and `passage` for every row, including news and analyst excerpts |
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
   - SEC filings via EDGAR full-text search: 60 companies a year, chosen at random (seeded).
   - The Guardian and New York Times search services (free keys). Only what those services return is used:
     Guardian article text and NYT summaries and first paragraphs. The newspapers' own pages are never read.
   - Web searches for other news and analysis (`candidates/web_found.csv`, each with its query). Pages on
     paywalled sites are never read, and there is no fallback to archived copies.
2. **Cutting** (`extract.py`, `passages.py`). The program reads the article body only. It finds a sentence
   naming a bank lending facility and adds whole neighbouring sentences up to 80 words. Headlines, bylines,
   tables, fragments, paywall teasers and photo credits are dropped.
3. **Scope** (owner's decision). Bank borrowing only. Rate-only announcements, non-bank programs and ECB
   stimulus (TLTROs) are out.
4. **Eligibility** (Clarification 20; `eligibility.py`). Mechanical, never judging tone. A passage is kept
   only if it refers to borrowing from a central bank by a bank or banks (actual, planned, expected or
   avoided) or to how such borrowing is seen. Passages that only announce or describe a facility, list
   funding sources, or discuss policy design are dropped. The written rules are tried in a fixed order, and
   every drop is logged with its reason. A hand audit of kept and dropped passages reports the rules' error
   rates.
5. **Personal data.** Quoted words of private individuals (callers, commenters, readers) are excluded, by
   rule and by reading every passage. Hand exclusions go in `exclusions.csv`.
6. **Build** (`build_corpus.py`), in order:
   - re-check against the current rules;
   - hand exclusions;
   - near-duplicates removed (sharing 60% or more of their 5-word runs; the earliest is kept);
   - at most 2 passages per document;
   - filings: one per company per year;
   - **no source type above 25% of any period**.

   Choices among equals use a seeded random order, never the wording. All eligible passages that survive
   are kept, with at least 150 per period. A period that falls short is reported before any gold-set draw
   and is never padded.

## Rebuild

```
make corpus          # collect from the web (hours; resumable; needs the keys in .env)
make corpus-build    # rebuild the corpus files from the collected passages (no internet)
make corpus-sample   # eligible share, drop reasons, counts by period and type, 20 random rows
```

Web pages change and disappear, so a fresh collection will not match row for row. The committed
`corpus.csv` is the record.

## Counts and known gaps

(Filled in after the full collection.)
