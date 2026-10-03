"""Candidate pages from other central banks and from Fed research blogs (session M2.2).

- Bank of England: news, speeches and statements, listed in its public site map. The
  map gives no day, so the date is read from the page's "Published on" line (extract.py).
- ECB: press releases and speeches, from its yearly listing pages. The date is in the
  page name (pr080327 = 27 March 2008).
- NY Fed Liberty Street Economics: research blog posts, tagged as analyst notes. The
  year and month are in the address; the day is read from the page.

Run: python -m signals.corpus.collect_other_cb
"""

import re

from signals.corpus.candidates import write_candidates
from signals.corpus.fetch import get
from signals.corpus.passages import load_settings

BOE_SITEMAP = "https://www.bankofengland.co.uk/_api/sitemap/getsitemap"
BOE_SECTIONS = {"news": "official_statement", "statement": "official_statement", "speech": "speech_testimony"}
ECB = "https://www.ecb.europa.eu"
ECB_SECTIONS = {"pr": "official_statement", "key": "speech_testimony"}
LSE_SITEMAP = "https://libertystreeteconomics.newyorkfed.org/post-sitemap.xml"


def _locs(xml):
    return re.findall(r"<loc>([^<]+)</loc>", xml)


def _years(settings):
    return range(int(settings["date_range"]["start"][:4]), int(settings["date_range"]["end"][:4]) + 1)


def boe(settings):
    rows, years = [], {str(y) for y in _years(settings)}
    for url in _locs(get(BOE_SITEMAP, settings)):
        m = re.match(r"https://www\.bankofengland\.co\.uk/(\w+)/(\d{4})/", url)
        if m and m.group(1) in BOE_SECTIONS and m.group(2) in years:
            rows.append({"url": url, "source_name": "Bank of England", "source_type": BOE_SECTIONS[m.group(1)],
                         "pub_date": "", "found_via": "Bank of England site map"})
    return rows


def ecb(settings):
    rows = []
    for year in _years(settings):
        for section, kind in ECB_SECTIONS.items():
            listing = f"{ECB}/press/{section}/date/{year}/html/index_include.en.html"
            for path in sorted(set(re.findall(r'href="(/press/[^"]+\.en\.html)"', get(listing, settings)))):
                m = re.search(r"/(?:pr|sp|is|ip)(\d{2})(\d{2})(\d{2})", path)
                if not m:
                    continue
                rows.append({"url": ECB + path, "source_name": "European Central Bank", "source_type": kind,
                             "pub_date": f"20{m.group(1)}-{m.group(2)}-{m.group(3)}",
                             "found_via": f"ECB {section} listing {year}"})
    return rows


def liberty_street(settings):
    rows, years = [], {str(y) for y in _years(settings)}
    for url in _locs(get(LSE_SITEMAP, settings)):
        m = re.search(r"newyorkfed\.org/(\d{4})/(\d{2})/", url)
        if m and m.group(1) in years:
            rows.append({"url": url, "source_name": "Federal Reserve Bank of New York, Liberty Street Economics",
                         "source_type": "analyst_note", "pub_date": "", "found_via": "Liberty Street Economics site map"})
    return rows


def collect(settings=None):
    settings = settings or load_settings()
    write_candidates("bank_of_england", boe(settings))
    write_candidates("ecb", ecb(settings))
    write_candidates("liberty_street", liberty_street(settings))


if __name__ == "__main__":
    collect()
