> **v0.1 proof of concept. Jev reference not validated against human readers. Not a v1 result.**

# How the v0.1 Jev signals were made (one page)

**What Jev is.** Jev (`jev-1.13.0`, pinned; Clarification 27) is TypeSafe's text-judgment model. It reads a passage and answers
narrow, typed questions. It reads language. It does not predict how depositors or markets behave. The simulation never calls
Jev: it reads only the files in this folder.

**1. Gold-set check: model-to-model agreement (M2.4; Clarification 30, Part A).**
- **What was compared.** Jev placed 278 public passages on the labeling guide's four-level scale (Reassuring, Routine, Some
  Concern, Clear Distress). Each passage was asked once. Jev's answers were compared with labels from another AI model,
  GPT-6.1 Sol (high), which the owner filled in and reviewed by eye (Amendment 7). No second human labeler was available.
- **Agreement.**
  - All passages: Krippendorff's ordinal alpha was 0.62 (90% interval 0.54 to 0.69).
  - The 148 passages the AI did not mark Unsure: 0.81.
  - Filings: 0.21. 2020–21: 0.35.
- **The main difference.** The AI called many passages Reassuring that Jev called Routine.
- **What this shows.** Two AI models broadly read the same passages alike. It says nothing about how people read them. There
  was no pass/fail gate.

**2. Market-stigma markers (M2.5; Clarification 30, Part B). Provisional.**
- **What was read.** Jev read each disclosure template in its original wording and in 3–4 paraphrases, which the owner
  checked: 99 texts in all. Placeholders were filled with fixed illustrative values.
- **The questions.** From three vantage points (an uninsured depositor, a wholesale lender, a bank equity analyst), Jev was
  asked both "read as a sign of distress?" and "read as a sign the bank is sound?".
- **A reading.** The average of P(distress) and 1 − P(sound).
- **A policy's marker.** The average over its 8–9 draw-revealing templates. The spread is the range of the readings behind
  it.
- **The markers.**

  | Policy | Marker | Spread |
  | --- | --- | --- |
  | A | 0.78 | 0.49–0.91 |
  | B, B′, E | 0.65 | 0.21–0.91 |
  | C | 0.77 | 0.49–0.91 |
  | C′ | 0.78 | 0.49–0.91 |

  B, B′ and E share the same templates, and so do A and C′, so their markers are equal by construction.
- **Flags.** In many readings Jev's two answers did not mirror each other (more than 0.25 apart): every W2 and P5 wording,
  and several AN1 and AN5 ones. Jev often found these texts neither distressed nor sound. Four wordings differed from their
  siblings by more than 0.15.
- **Where it appears.** The marker is a point on the stigma sweep (0 to 0.9), labelled "provisional". The sweep remains the
  primary result.

**3. Historical range (M2.6).**
- **What was scored.** Jev scored all 771 corpus passages with the gold-set question. Filings are weighted by 1 / their
  sampling rate (Clarification 23).
- **Expected score**, on a scale of 1 (Reassuring) to 4 (Clear Distress):

  | Group | Weighted mean | Share Some Concern or Clear Distress |
  | --- | --- | --- |
  | All passages | 2.25 | 31% |
  | 2007–09 | 2.66 | 58% |
  | 2010–19 | 2.38 | 40% |
  | 2020–21 | 1.95 | 10% |
  | 2022–24 | 2.20 | 29% |
  | News | 3.04 | 80% |
  | Filings | 1.88 | 5% |

- **Reading the range.** How borrowing is described depends heavily on who is writing and when. Crisis-era news reads as
  distress; filings and pandemic-era text read as routine.

**Limits.**
- The labels are an AI's, not people's.
- The AI marked 46% of its labels Unsure.
- Jev and the AI agree least on filings and on 2020–21.
- The 2007–09 corpus has 110 passages, below the 150 target (Clarification 24).
- The placeholder values and the template set shape the markers.
- v1 needs a fresh gold-set draw labelled by independent people (Amendment 7).

**Files.** All files here are fingerprinted in `MANIFEST.json`:
- `gold_check.json`, `gold_set_answers.csv`;
- `markers.csv`, `markers_readings.csv`;
- `corpus_scores.csv`, `historical_range.csv`.
