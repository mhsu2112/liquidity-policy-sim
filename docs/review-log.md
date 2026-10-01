# Review log

Every outside review of the comparison rules or results is recorded here, with the changes it led to.
Reviewers choose whether to be named. Anonymous reviewers are identified only by number and perspective.

---

## Review 1 — Option C specification (M0.5)

- **Reviewer:** Reviewer 1, anonymous at their request. Perspective: supportive of LCR recognition of discount window capacity.
- **Received:** 2026-09-26
- **Sign-off option chosen:** Sign off with changes. Changes are to be made and sent back to the reviewer for a final check before the rules are frozen.

### Changes requested to the Option C specification

| # | Element | Draft specification | Reviewer 1's change |
| --- | --- | --- | --- |
| R1-1 | Ceiling | 15% of net cash outflows; swept 10%, 15%, 25% | 20% in the ordinary course, rising automatically to 30% when market indicators show funding stress (for example, SOFR above the top of the federal funds target range). Sweep 15%, 25%, 30% |
| R1-2 | Stress-adjustable cap | Deferred to v2 | Include in v1: "banks will be incentivized to preposition more as stress builds to ensure full 30% credit once triggered" |
| R1-3 | Usage multiple | k × average discount window borrowing over the prior four quarters; default 20; swept no limit, 20, 10 | k × average of the 1st, 3rd and 5th largest overnight discount window borrowings over the prior two quarters; default 75; swept no limit, 75, 100, 125 (the package's two tables listed 100/125 and 75/100) |
| R1-4 | Implication noted by reviewer | — | A bank must make at least five discount window draws every six months to receive full credit |
| R1-5 | Released HQLA | A bank may cut HQLA by up to its credit; default 50%; swept 0%, 50%, 100% | Row deleted, without comment. **Clarification requested** |
| R1-6 | Voluntary uptake | Default 50%; swept 0%, 50%, 100% | Default 75%; swept 50%, 75%, 100% |
| R1-7 | Bank population / LCR scope | Large bank (I–II, full); SVB-like (IV, 70%); diversified regional (IV, none) | Large bank relabeled GSIBs and extended to Category III with $75bn or more wSTWF (full LCR); add Category III regional banks (85% LCR) |
| R1-8 | Outcomes reported | Survival, shortfall, official support, annual cost | Add "reduced stigma for discount window borrowing" |

### Answers to the review questions

1. **Design fidelity:** revisions suggested (R1-1 to R1-7).
2. **Eligibility (non-HQLA collateral only):** "That seems right."
3. **Ceiling and multiple:** see R1-1, R1-3 and R1-4.
4. **Bank behavior:** see R1-5 and R1-6.
5. **Scope:** "No changes to current LCR rules, other than as expressly contemplated above."
6. **Metrics (false comfort paired with buffer gap and cost):** "I don't understand this but am not sure this is an important design feature."
7. **Flagged templates (AN6, L2, W2, L3, P5):** no changes; not an important design feature.
8. **Anything else:** "some question as to whether the modeling could take full account of the incentivizes [sic] established by C for sizeable discount window draws each quarter, and the associated implications for reducing discount window stigma. That reduced discount window stigma will significantly mitigate risks of disruption in the short-term funding markets."

### Sponsor's responses

Recorded 2026-09-28. Contract updated to v0.4.

| # | Response |
| --- | --- |
| R1-1, R1-2 | **Accepted.** Ordinary ceiling 20% (swept 15/20/25%); automatic rise to 30% on a funding-stress trigger, in v1. Because v1's scenarios are bank-specific and the SOFR trigger would rarely fire, the trigger is run as a switch in S1 (off / fires on day 1), and banks that opt in preposition ahead of time for the 30% ceiling. |
| R1-3, R1-4 | **Accepted.** Usage formula as specified; default k = 75; swept over no limit, 75, 100, 125 (combining the two lists in the marked-up package). Banks that opt in make at least five overnight draws per six months, and their cost is counted. |
| R1-5 | **Clarification requested.** Default set to 0% released in the meantime; 50% and 100% kept as sensitivities. |
| R1-6 | **Accepted.** Default uptake 75%; swept 50/75/100%. |
| R1-7 | **Accepted.** Category III regional banks (85% LCR) added as a fourth bank type; 40 banks in total. |
| R1-8 and answer 8 | **Accepted in part.** A routine-borrowing effect is added for every policy: the more often banks borrow routinely, the less a single draw signals distress. Effective stigma and borrowing frequency are reported outcomes. Market-wide effects on short-term funding markets need a multi-bank funding scenario and are deferred to v2. |
| Answers 2, 6, 7 | No change needed. The five flagged templates are kept. |

### Reviewer 1's final check (received 2026-09-29)

- **Stress trigger switch:** "That sounds right." The off / fires-on-day-1 approach is accepted.
- **Released HQLA (R1-5):** the deleted row was a misunderstanding. Banks should be assumed to release HQLA after
  prepositioning, shifting their balance sheets to non-HQLA; this is part of the rationale for C. **Resolved:** default
  release set to 100% of credit received; 0% and 50% kept as sensitivities.
- **Stigma:** the reviewer notes that effective stigma will necessarily rest on an assumption. The purpose of regular draws
  is to normalize discussion of discount window use with senior management and examiners, so borrowing is less fraught in
  stress; stronger banks borrowing more ahead of a stress, to take advantage of funding-market dislocations, could add to
  the benefit. **Response:** the routine-borrowing effect now also lowers supervisory and internal reluctance, by the same
  rule for every policy. Pre-stress borrowing by stronger banks needs a multi-bank scenario and is deferred to v2.
- **Suggested variant C′:** C with the 20% and 30% ceilings but no usage cap and no draw requirement. **Response:** added
  as a named variant (the "no limit" point of the usage-multiple sweep). Reviewer 1's stated expectation, recorded before
  any results: C′ will not have the same benefits as C.
- **Sign-off:** complete, with the changes above. Contract updated to v0.5.

