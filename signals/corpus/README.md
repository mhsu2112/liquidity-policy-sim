# Calibration corpus (session M2.2)

> **Disclosure.** The project owner has disclosed prior support for Option B. See the
> [project README](../../README.md).

The corpus holds short public passages, 2007–2024, about banks borrowing from a central bank: the Fed's
discount window, its emergency programs, and comparable lending by other central banks. It is the
sampling frame for the gold set (Clarification 19). M2.6 later scores it to show how such borrowing has
historically been described. Rules: `docs/amendments.md` Clarifications 19 to 22, with every
setting and its reason in `config/corpus.yaml`. **No passage has been sent to Jev.**

## Files

| File | Public? | Holds |
| --- | --- | --- |
| `corpus.csv` | yes | `id`, `document_id`, `url`, `pub_date`, `source_name`, `source_type`, `stratum` (period), `found_via`, `excerpt_sha256`, `eligibility` (the review's reason code), `decided_by` (reviewer model and instruction version, or "owner check"), `gold_set_eligible` and `gold_set_exclusion` (Clarification 22), and `passage`. The passage is filled for official (Fed, ECB, BoE) and SEC text only; for news and analyst notes it is blank and only the fingerprint is published. |
| `excerpts_private.csv` | **no** (git-ignored) | `id` and `passage` for every row, including news and analyst excerpts |
| `eligibility_instruction.md` | yes | The instruction every passage is reviewed against (v2; v1 in `eligibility_instruction_v1.md`) |
| `eligibility_owner_check.csv` | yes | The owner's check of 50 decisions: his blind first answer, his final answer after seeing the recommendations (not blind), and the reviewer's v1 decision. By ID and hash, no text. His final answers override the reviewer for these 50. |
| `gold_set_exclusions.csv` | yes | Excerpt hashes the gold-set draw must skip because the owner has already seen them (check sheet, trial examples) |
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
   - US congressional hearing transcripts held 2020–2024 (govinfo, public domain; Clarification 22).
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
   judges tone. The rules' verdict is kept for comparison.

   **How the review was checked (Clarification 22).** The owner checked 50 random v1 decisions twice.
   - Blind, first answers: 16 of 50 agreed (32%). The owner attributes this to answering before studying
     the guidelines.
   - After seeing the recommendations, with confidence levels and reasons (not blind): 46 of 50 agreed (92%).

   Instruction v2 was written from his remaining disagreements, and every passage is reviewed under v2. No
   fresh blind check was run, by the owner's decision, so the published agreement figure is the non-blind
   92%.
5. **Personal data.** Quoted words of private individuals are excluded, by rule and in the review.
6. **Build** (`build_corpus.py`), in order:
   - re-check against the current rules;
   - keep reviewed-eligible passages only (unreviewed ones are never kept);
   - hand exclusions;
   - near-duplicates removed (sharing 60% or more of their 5-word runs; the earliest is kept);
   - at most 2 passages per document;
   - filings: one per company per year.

   There is **no source-type cap in the corpus**. For the gold-set draw (M2.3), Clarification 22 sets two
   limits: no source type above 25% of the 300, and none above 25% of a period's 75 where supply allows.
   Doubtful review calls and passages the owner has already seen are flagged and skipped by the draw. The
   readout reports whether the draw can be filled. The 25% cap applies when M2.3 draws the gold set, and
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

## Counts and known gaps (full collection, 2026-10-03)

**Collected.** About 21,700 pages read:
- Fed Board 5,501; Bank of England 2,685; ECB 2,241; NY Fed Liberty Street 1,595;
- SEC filings 9,439 (every filer found);
- Guardian about 480 articles; NYT about 350 summaries;
- congressional hearings 97 (2020–24);
- web search 236 pages.

**Reviewed.** 9,272 in-scope passages:
- Every non-filing passage and a company-year sample of filings, 6,101 in all, was reviewed under instruction
  v2 (Clarification 23).
- Filing sampling rates: 2007–09 100%, 2010–19 32.8%, 2020–21 100%, 2022–24 79.7%. M2.6 weights filing
  passages by the inverse of their period's rate.
- 21.3% were eligible. The written rules alone agree with the review on 82%.
- 599 reviews (about 10%) were marked doubtful.

**Corpus: 771 passages.**

| Source type | 2007–09 | 2010–19 | 2020–21 | 2022–24 | Total |
| --- | --- | --- | --- | --- | --- |
| News | 56 | 32 | 8 | 43 | 139 |
| Analyst notes | 0 | 36 | 33 | 34 | 103 |
| Official statements | 2 | 8 | 1 | 1 | 12 |
| Speeches and testimony | 39 | 66 | 8 | 41 | 154 |
| Filings | 13 | 34 | 164 | 152 | 363 |
| **Total** | **110** | **176** | **214** | **271** | **771** |

**Known gaps**
- **2007–09 is short: 110 passages, under the 150 minimum.** It is reported here and not padded. That period
  has few filings in the SEC's full-text search, little web-available news apart from the Guardian, and no
  analyst notes.
- **Gold-set draw under the Clarification 22 caps: at most 288 of 300.** 2007–09 can supply at most 63 of its 75.
  No period can meet the 25% per-period cap on its own: 2007–09 is mostly news and speeches, 2010–19 mostly
  speeches, and 2020–21 and 2022–24 mostly filings.
- **The gold-set draw skips 236 corpus passages:** 179 doubtful review calls, and 57 the owner has already
  seen (his check sheet and the trial examples). 535 are eligible for the draw.
- **The NYT contributes almost nothing.** Its search service returns only summaries, which rarely name the
  facility.
- **Paywalled outlets are not read** (Bloomberg, WSJ, FT, Reuters, AP and others).
- **The eligibility check is not blind.** The owner's check of the review was blind at first (32% agreement)
  and then not blind (92%). No fresh blind check was run (Clarification 22).
