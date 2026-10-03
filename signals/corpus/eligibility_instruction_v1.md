# Eligibility instruction (v1, 2026-10-03)

Fixed before any passage is reviewed (Clarification 21). Any change means a new version number and
an entry in `docs/amendments.md`. Passages already reviewed keep the version they were reviewed under.

## Your task

You will see short passages, one at a time, with an ID and the text only. You will not see the source,
date or link. For each passage, decide whether it is **eligible** and give **one reason code**.

**Eligible** (Clarification 20, item 1, verbatim): *keep a passage only if it refers to borrowing from a
central bank by a bank or banks — actual, planned, expected or avoided — or to how such borrowing is seen.
Drop passages that only announce or describe a facility, list available funding sources, or discuss policy
design.*

**Never judge tone.** You are not deciding whether the passage sounds reassuring, routine or alarming.
That is the gold-set labelers' job. A calm passage and an alarmed passage are equally eligible if they
refer to banks' borrowing.

## Reason codes

Keep (eligible):

| Code | Use when the passage refers to… | Examples |
| --- | --- | --- |
| `borrowing` | borrowing that happened or is happening, by a named bank, banks in general, or in aggregate | "banks borrowed $150 billion", "the Bank had $20 million of BTFP advances outstanding", "repaid its PPPLF advances", "discount window lending spiked", "500 banks took part in the operation" |
| `planned` | borrowing a bank plans, expects or intends | "the Company expects to use the PPPLF", "banks intend to draw £200bn" |
| `avoided` | borrowing a bank or banks avoided, resisted or chose against | "banks were reluctant to borrow", "the facility has been shunned", "we have not used the PPPLF because our liquidity is ample" |
| `perception` | how borrowing is or would be seen, by markets, depositors, supervisors, the public or banks | stigma, "seen as a sign of weakness", "kept secret", "regulatory disapproval", "if word leaks out" |

Drop (not eligible):

| Code | Use when the passage only… | Examples |
| --- | --- | --- |
| `facility_description` | announces, creates, extends, prices or describes a facility, its terms, collateral or operations | "the Fed announced the BTFP, which offers loans of up to one year", "lowered the rate on discount window loans" |
| `funding_source_list` | lists funding sources, or states borrowing capacity, eligibility or access, or that nothing was borrowed | "other sources include the discount window", "the Bank may borrow from the FRB", "capacity of $15 million, none outstanding", "the Bank did not borrow from the BTFP" |
| `policy_design` | discusses what policy should be, proposals, reforms, readiness exhortations, how the tool works in principle | "banks should be ready to use the window", "a prepositioning requirement could reduce stigma" *(but see the stigma rule below)* |
| `not_bank_borrower` | refers to borrowing by someone other than a bank: the FDIC, a government, GSEs, money funds, companies, households | "the FDIC borrowed from the Fed", "Fannie and Freddie can borrow at the discount window" |
| `no_borrowing` | mentions a facility in passing, or is about something else | footnotes, reference lists, rate decisions, monetary statistics |
| `personal_data` | quotes or identifies a private individual (a caller, reader or commenter) | "Scott here from Knoxville…" (drop whatever else the passage says) |

## Rules for edge cases (decided before reading)

1. **Capacity is not borrowing.** "Can borrow", "may borrow", "has access", "available", "capacity",
   "pledged collateral", "approved to participate", "had no borrowings": `funding_source_list`.
2. **Actual amounts are borrowing**, even in a dry filing: "outstanding advances of $280 million",
   "average outstanding balance at the discount window was $3.5 million", "paid off $85.9 million of the
   PPPLF": `borrowing`.
3. **Decided not to borrow, with a reason** ("because liquidity was ample", "to avoid…"): `avoided`.
   A bare statement that nothing was borrowed: `funding_source_list`.
4. **Perception beats policy.** A passage that discusses stigma or how borrowing is seen counts as
   `perception`, even if it also discusses policy design.
5. **Aggregate or system-wide borrowing counts**: weekly totals, take-up of LTROs or the SLS, "banks
   repaid €362 billion". So does borrowing by banks' dealer subsidiaries under the PDCF.
6. **Facility descriptions that include an amount offered** ("will offer $75 billion in 28-day credit")
   are `facility_description`. Amounts **taken** or **outstanding** are `borrowing`.
7. **Hypotheticals in principle** ("a bank which borrows from the ECB can use the funds to…"): `no_borrowing`.
   Hypotheticals about stigma ("if banks fear being seen…"): `perception`.
8. **Historical accounts** of borrowing ("lending soared after September 11") are `borrowing`.
9. **When two codes fit**, use the first applicable in this order: `personal_data`, `perception`,
   `avoided`, `borrowing`, `planned`, then the drop codes.
10. **If unsure**, choose the code that best fits and add `?` after it (for example `borrowing?`). Doubtful
    calls are counted in the readout.

## Output

One line per passage: `id,decision,reason`, where decision is `keep` or `drop`. For example:
`P1a2b3c4d5e,keep,borrowing`
