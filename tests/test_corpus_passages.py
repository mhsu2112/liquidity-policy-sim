"""Checks on how passages are cut from a page (session M2.2).

Mechanics only: passages are verbatim runs of the page's own sentences, within the
word limits; the scope rule follows config/corpus.yaml; dates fall in the right
Clarification 19 period; page furniture is left out. Nothing here judges whether a
passage reads as reassuring or distressed. No network: every page is made up here.
"""

import copy

import pytest

from signals.corpus.extract import page_date
from signals.corpus.passages import (Scope, cut_passages, html_to_text, load_settings, reads_cleanly,
                                     split_sentences, stratum_of, word_count)

SETTINGS = load_settings()
FILLER = "The committee also discussed regional economic conditions and the outlook for employment in detail. "


def test_passages_are_verbatim_whole_sentences_within_the_word_limit():
    text = (FILLER * 5 + "The bank borrowed $2 billion from the Federal Reserve's discount window on Tuesday, "
            "according to people familiar with the matter. " + FILLER * 5)
    passages = cut_passages(text, SETTINGS)
    assert len(passages) == 1
    p = passages[0]
    assert word_count(p) <= SETTINGS["passage"]["max_words"]
    assert p in text.replace("\n", " ")                       # verbatim, nothing reworded
    assert all(s in split_sentences(text) for s in split_sentences(p))   # made of whole sentences
    assert "discount window" in p


def test_sentence_splitter_keeps_abbreviations_together():
    sentences = split_sentences("The U.S. bank borrowed from the Fed. Mr. Smith declined to comment. It repaid.")
    assert sentences == ["The U.S. bank borrowed from the Fed.", "Mr. Smith declined to comment.", "It repaid."]


@pytest.mark.parametrize("passage, expected", [
    # a bank facility plus borrowing: in scope
    ("Banks borrowed a record amount through the discount window last week as deposits fled regional lenders "
     "and funding markets tightened across the country.", True),
    # a rate change with no facility named: out of scope (plan: discount-rate-only announcements are out)
    ("The Federal Reserve lowered the discount rate by half a percentage point on Friday, citing tighter "
     "credit conditions and growing downside risks to growth.", False),
    # a non-bank program only: out of scope
    ("Companies sold a record volume of paper to the Commercial Paper Funding Facility, which the Fed "
     "set up to lend to issuers when the market seized up.", False),
    # ECB stimulus program only: out of scope
    ("The targeted longer-term refinancing operations will allow banks to borrow at attractive rates "
     "provided they increase lending to firms and households.", False),
    # a broad term with only general talk: out of scope
    ("The crisis showed the importance of the central bank acting as lender of last resort in a modern "
     "financial system with large and complex institutions.", False),
    # the same broad term with actual borrowing: in scope
    ("Several lenders turned to the central bank as lender of last resort and borrowed heavily once "
     "interbank markets closed to them in the autumn.", True),
])
def test_scope_rule(passage, expected):
    assert Scope(SETTINGS).passage_in_scope(passage) is expected


@pytest.mark.parametrize("date, stratum", [
    ("2007-01-01", "S-A"), ("2009-12-31", "S-A"), ("2010-01-01", "S-B"), ("2019-12-31", "S-B"),
    ("2020-01-01", "S-C"), ("2021-12-31", "S-C"), ("2022-01-01", "S-D"), ("2024-12-31", "S-D"),
    ("2006-12-31", None), ("2025-01-01", None), ("", None),
])
def test_stratum_boundaries_match_clarification_19(date, stratum):
    assert stratum_of(date, SETTINGS) == stratum


@pytest.mark.parametrize("passage", [
    "if used for less than thirty consecutive days the bank may also borrow at the discount window from the "
    "Federal Reserve Bank of St. Louis.",                                   # starts mid-sentence
    "Cash 96,873 Securities 72,354 FHLB 897,776 Lines 55,000 Discount window 500 Total 1,231,882 as of June 30, "
    "2023 and 2022 respectively.",                                         # a table row
    "This article is for subscribers only. Banks tapped the discount window on Monday in large numbers, "
    "according to data released by the Fed.",                              # paywall teaser
    "Mar 31, 2023 Why banks are reluctant to borrow at the discount window There is a stigma attached to the "
    "emergency lending program.",                                          # headline/date banner
])
def test_quality_rules_reject_fragments_tables_and_furniture(passage):
    assert not reads_cleanly(passage, SETTINGS["passage"])


def test_page_text_prefers_the_article_body_and_drops_scripts():
    body = "<p>" + "Banks borrowed from the discount window. " * 30 + "</p>"
    page = f"<html><nav>Home Menu Login</nav><script>var x=1;</script><div id='article'>{body}</div>" \
           f"<footer>Contact us</footer></html>"
    text = html_to_text(page)
    assert "Menu" not in text and "var x" not in text and "Contact us" not in text
    assert text.startswith("Banks borrowed")


def test_cutting_keeps_every_in_scope_passage_up_to_the_page_limit_without_overlaps():
    # Clarification 21: eligibility is decided by review, so cutting keeps all in-scope passages (up to a bound)
    s = copy.deepcopy(SETTINGS)
    limit = s["passage"]["max_candidates_per_page"]
    # each mention is numbered so that every passage can be found in the page exactly once
    text = "".join(FILLER * 6 + f"In quarter {i} smaller banks drew on the discount window as deposits ran off. "
                   for i in range(limit + 3))
    many = cut_passages(text, s)
    assert len(many) == limit
    starts = [text.find(p) for p in many]
    assert all(starts[i] + len(many[i]) <= starts[i + 1] for i in range(len(many) - 1))   # in order, no overlap
    anchor = "Smaller banks drew on the discount window heavily during the quarter as deposits ran off. "
    assert len(cut_passages(FILLER * 6 + anchor + FILLER * 6 + anchor, s)) == 2


def test_page_date_reads_the_page_own_date():
    assert page_date('<div class="published-date">Published on  \n 16 April 2008</div>') == "2008-04-16"
    assert page_date('<meta property="article:published_time" content="2023-03-31T10:00:00Z">') == "2023-03-31"
    assert page_date("<p>No date here</p>") == ""


def test_headlines_and_bylines_are_not_glued_onto_passages():
    text = ("Fed Lending Jumps As Banks Seek Cash\nBy A Reporter\n"
            "Banks borrowed $5 billion through the discount window this week, the most in a year, as funding "
            "markets tightened and lenders sought cash. Officials said the facility was working as intended.")
    [p] = cut_passages(text, SETTINGS)
    assert p.startswith("Banks borrowed") and "Reporter" not in p


def test_a_rate_decision_naming_a_lending_facility_is_out_of_scope():
    rate_only = ("At today's meeting the Governing Council decided that the interest rates on the main refinancing "
                 "operations, the marginal lending facility and the deposit facility will remain unchanged.")
    assert not Scope(SETTINGS).passage_in_scope(rate_only)
    used = ("Several banks borrowed overnight from the marginal lending facility after interbank markets froze, "
            "the central bank's weekly figures showed.")
    assert Scope(SETTINGS).passage_in_scope(used)


def test_slide_deck_debris_is_rejected():
    assert not reads_cleanly("Pledging of eligible assets to FHLB, Fed Discount window, and BTFP ▪ to enhance "
                             "operational liquidity and ease of access to reliable sources of funding . This "
                             "secured a total of $ 960 million.", SETTINGS["passage"])


# ---------- Clarification 20: eligibility and personal data ----------

from signals.corpus.eligibility import Eligibility   # noqa: E402

ELIG = Eligibility(SETTINGS)


@pytest.mark.parametrize("passage, keep, reason", [
    ("Banks borrowed $150 billion from the discount window in the week after the failure, Fed data showed.",
     True, "borrowing"),
    ("The Company obtained a $54.0 million advance from the Bank Term Funding Program on May 15, 2023.",
     True, "borrowing"),
    ("The company expects to utilize the Federal Reserve discount window for liquidity needs related to the program.",
     True, "planned"),
    ("Banks were reluctant to borrow from the discount window for fear that markets would learn of it.",
     True, "perception"),
    ("Bankers say they avoid the discount window except as a last resort, according to a survey of treasurers.",
     True, "avoided"),
    ("Other sources of liquidity include Federal Home Loan Bank advances and the Federal Reserve discount window.",
     False, "funding_source_list"),
    ("The Bank can also borrow from the discount window. As of December 31 no amounts were outstanding.",
     False, "funding_source_list"),
    ("The Federal Reserve announced the creation of a temporary term auction facility to provide term funding.",
     False, "facility_description"),
    ("Supervisors should consider whether discount window capacity ought to count toward liquidity requirements.",
     False, "policy_design"),
    # "avoid" alone, with no borrowing word near it, is not avoided borrowing
    ("Investors were inclined to avoid risky assets in early 2020 as the discount window rate was lowered.",
     False, "no_borrowing"),
    ("Total loans outstanding rose 4 percent, and the bank keeps collateral pledged at the discount window.",
     False, "no_borrowing"),
])
def test_eligibility_rules(passage, keep, reason):
    assert ELIG.judge(passage) == (keep, reason)


def test_personal_data_rule_flags_private_individuals_only():
    assert ELIG.personal_data("Scott here from Knoxville, Tennessee. Did SVB go to the discount window?")
    assert ELIG.personal_data("One listener called in to ask why the bank did not borrow from the Fed.")
    assert not ELIG.personal_data("Chair Powell said banks should not hesitate to use the discount window.")


def test_cutting_does_not_filter_by_eligibility():
    # Clarification 21: an ineligible mention (a funding-source list) still goes to review
    early = "Other sources of liquidity include the Federal Reserve discount window and brokered deposits. "
    later = "In March the bank borrowed $2 billion from the discount window as deposits ran off. "
    passages = cut_passages(early + FILLER * 8 + later, SETTINGS)
    assert len(passages) == 2 and passages[0].startswith("Other sources") and "borrowed $2 billion" in passages[1]
