# Gold-Set Labeling Guide

Liquidity Policy Simulator · Draft v0.9 · 2026-10-01 (becomes v1.0 after the practice round; rules in Clarification 19)

## What this is

You'll read 315 short public passages about banks borrowing from a central bank and answer one question about each. The passages come from 2007 to 2024: news, analyst notes, official statements and filings. Your answers test whether an AI text-reading model (Jev) reads these passages the way people do. You never see Jev's answers, and it never sees yours.

- **Practice round:** 15 passages, about 15 minutes. Not scored.
- **Main round:** 300 passages, about 4–5 hours. Do it in several sittings, ideally over 2–3 days.
- **Two labelers:** you and one other person, working alone.
- **No technical skills needed:** one spreadsheet, one column to fill in, one file to send back.

## The question

**How does this passage present a bank's borrowing from a central bank: as reassuring, as routine, or as a sign of trouble?**

Pick one answer per passage. A higher number means a stronger sign of trouble.

| Answer | Meaning | Example (made up, for illustration) |
| --- | --- | --- |
| **1 Reassuring** | The borrowing is presented as prudent, a sign of strength, or a responsible use of the facility. | "The bank said it borrowed briefly to test its access, as supervisors encourage." |
| **2 Routine** | The borrowing is reported as a fact or as ordinary business. There's no suggestion of strength or weakness. | "Discount window lending rose to $3.1 billion last week, Fed data showed." |
| **3 Some concern** | The passage suggests the borrowing may point to strain, or that others may read it that way. It stops short of saying the bank is in trouble. | "The draw raised questions among analysts about the bank's deposit base." |
| **4 Clear distress** | The borrowing is presented as evidence that the bank is in trouble: losing deposits, cut off from other funding, or close to failing. | "After depositors pulled $40 billion, the bank was forced to turn to the Fed." |
| **N Not applicable** | The passage isn't about borrowing from a central bank, or there's too little to judge. Use this sparingly. | "The Fed held rates steady on Wednesday." |

"Central bank borrowing" includes the Fed's discount window and its emergency programs (for example, the Term Auction Facility or the Bank Term Funding Program), and similar lending by other central banks.

## Rules

1. **Judge the passage, not the bank.** Label what the passage, as written, says or implies about the borrowing. Your own view of the bank, the policy or the facility doesn't count.
2. **Reported views count.** If the passage reports what others think the borrowing signals (analysts, depositors, "markets"), label that view, unless the passage clearly rejects it.
3. **Mixed passages.** Go with the overall impression a typical reader would take away. If you hesitate, still pick a level and put **Y** in the Unsure column.
4. **No hindsight.** Use only what's in the passage. If you know the bank later failed or recovered, set that aside.
5. **Don't look anything up.** Don't search for the article, the bank or the date.
6. **No AI help.** Don't use ChatGPT, Claude or any other AI tool while labeling. The whole point is to compare people with an AI.
7. **Work alone.** Don't discuss main-round passages with anyone, including the other labeler, until both sets have been returned.
8. **Go with your first considered reading.** About a minute per passage is right. Fix obvious slips, but don't go back and re-label earlier passages for consistency.
9. **Take breaks.** Long sittings blur judgment. Batches of about 50 work well.

## Step by step

You'll receive one Excel file with two tabs, **Practice** and **Main**. Each row is one passage. Fill in only the three shaded columns:

| Column | What to enter |
| --- | --- |
| Answer | 1, 2, 3, 4 or N |
| Unsure | Y if you hesitated; otherwise leave blank |
| Note | Optional. A few words if something was odd (for example, "cut off mid-sentence") |

The passages show no source or date, on purpose. Don't change any other column.

**Practice round**

1. Read this guide once. It takes about 10 minutes.
2. Open the file and click the **Practice** tab.
3. Answer all 15 passages.
4. Save and send it back (see "Saving and sending" below). Name it `gold_set_L2_practice.csv`.
5. Wait for the final guide. We'll compare the two practice sets and go through any passages where we differed, to find instructions that need clarifying. This is the only time labels are discussed. You'll then receive the final guide (v1.0). Only its wording can change. The practice passages are never scored.

**Main round**

6. Re-read the final guide, especially the table of answers.
7. Click the **Main** tab and answer all 300 passages, in batches of about 50.
8. Before saving, scroll down once to check that every row has an answer.
9. Save and send it back. Name it `gold_set_L2_main.csv`.

**Saving and sending**

Send the file back as CSV, not as an Excel file. An Excel file stores your name inside it. A CSV file holds only the cells.

- **Excel on a Mac:** File → Save As… → File Format: **CSV UTF-8 (Comma delimited) (.csv)** → Save. If Excel warns that only the current sheet will be saved, click **OK**. Make sure the tab you're returning is the one that's open.
- **Excel on Windows:** File → Save As → Browse → Save as type: **CSV UTF-8 (Comma delimited)** → Save → OK.
- **Then:** attach the .csv file to an email to Mike. Don't attach the Excel file.

If anything goes wrong, email Mike rather than starting over.

## What gets published

Only your answers are published, labeled "L2", and only after both labelers' sets are in. Nothing else about you is published.

- **Each labeler's answers** go into the project's public repository as "L1" and "L2".
- **Agreement figures:** how often the two labelers agree with each other, and how often Jev agrees with each of them.
- **One disclosure sentence,** which you'll see and approve first: "Labeler 1 is the project owner, who has disclosed prior support for Option B. Labeler 2 is the outside reviewer of Option C, who approaches it from an LCR-recognition perspective and asked to remain anonymous."

Before either labeler sees the other's answers, each finished set is "locked": a digital fingerprint of the file is recorded publicly. This shows that neither set was changed after the other was seen.

Mike is Labeler 1. He follows the same steps and rules, with file names ending in L1.
