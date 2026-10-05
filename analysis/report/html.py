"""The page shell every report page shares (session M3.0).

Each page carries: the mock banner and watermark (when the results are mock), the README disclosure
(CLAUDE.md rule 7: it stays in every published output), links to every page, and the stamp.
"""

import html
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent

CSS = """
:root { --ink:#1a1a1a; --muted:#555; --rule:#ccc; --bg:#fff; --panel:#f6f6f4; --mock:#C00000; }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.5 Georgia, 'Times New Roman', serif; }
main { max-width:1180px; margin:0 auto; padding:16px 16px 48px; position:relative; z-index:1; }
h1 { font-size:1.7em; margin:.6em 0 .2em; } h2 { font-size:1.25em; margin-top:1.6em; } h3 { font-size:1.05em; }
a { color:#0b4f8a; }
nav { font:13px/1.8 Helvetica, Arial, sans-serif; border-bottom:1px solid var(--rule); padding:6px 0; }
nav a { margin-right:12px; white-space:nowrap; } nav a.here { font-weight:bold; color:var(--ink); text-decoration:none; }
.banner { position:sticky; top:0; z-index:10; background:var(--mock); color:#fff; text-align:center;
  font:bold 16px/1.2 Helvetica, Arial, sans-serif; letter-spacing:.05em; padding:9px 8px; }
.watermark { position:fixed; inset:0; z-index:0; pointer-events:none; display:flex; align-items:center;
  justify-content:center; overflow:hidden; }
.watermark span { transform:rotate(-28deg); font:bold 64px/1.1 Helvetica, Arial, sans-serif; color:var(--mock);
  opacity:.09; white-space:nowrap; }
.disclosure { background:var(--panel); border-left:4px solid #666; padding:10px 14px; margin:14px 0; font-size:.92em; }
.stamp { font:12px/1.6 Menlo, Consolas, monospace; color:var(--muted); border-top:1px solid var(--rule);
  margin-top:36px; padding-top:8px; overflow-wrap:anywhere; }
.scroll { overflow-x:auto; margin:8px 0 18px; }
table { border-collapse:collapse; font:13px/1.35 Helvetica, Arial, sans-serif; background:rgba(255,255,255,.85); }
th, td { border:1px solid var(--rule); padding:4px 7px; vertical-align:top; text-align:right; }
th { background:var(--panel); text-align:center; } td.l, th.l { text-align:left; }
td .ci { display:block; color:var(--muted); font-size:11px; white-space:nowrap; }
td.na { color:#999; text-align:center; } th.grace, td.grace { background:#fafafa; font-style:italic; }
.slot { display:inline-block; border:1px dashed #888; padding:1px 8px; font:12px Helvetica, Arial, sans-serif; color:var(--muted); }
.note { color:var(--muted); font-size:.92em; }
img.chart { max-width:100%; height:auto; border:1px solid var(--rule); }
.toc { columns:2; font:13px/1.7 Helvetica, Arial, sans-serif; } .toc a { display:block; }
@media (max-width:700px) { .toc { columns:1; } .watermark span { font-size:32px; } }
"""


def e(text):
    return html.escape(str(text))


def md_inline(text):
    """Escape text, then turn **bold**, *italic* and `code` from the Markdown sources into HTML."""
    out = e(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<![\w*])\*(?!\s)(.+?)\*(?![\w*])", r"<em>\1</em>", out)
    return re.sub(r"`(.+?)`", r"<code>\1</code>", out)


def disclosure():
    """The README's disclosure paragraph, read fresh each build so the two can never drift apart."""
    text = (ROOT / "README.md").read_text()
    m = re.search(r"\*\*Disclosure\.\*\*.*?(?=\n\s*\n)", text, re.S)
    if not m:
        raise ValueError("README.md has no **Disclosure.** paragraph; the report will not build without it (rule 7)")
    return md_inline(" ".join(m.group(0).split()))


def page(layout, meta, page_id, title, body, prefix=""):
    """A complete HTML page. prefix points links back to the report root from a sub-folder."""
    banner = layout["mock_banner"] if meta["mock"] else ""
    nav = "".join(f'<a href="{prefix}{p["file"]}"{" class=here" if p["id"] == page_id else ""}>{e(p["title"])}</a>'
                  for p in layout["pages"])
    s = meta["stamp"]
    stamp = (f"git commit {e(s['git_commit'])} · config hash {e(s['config_hash'])} · params fingerprint "
             f"{e(s['params_fingerprint'])} · Jev estimate {e(s['jev_estimate_version'])} · Jev model {e(s['jev_model'])}"
             f" · results written {e(meta['generated_at'])} · schema {e(meta['schema_version'])}")
    mock_bits = (f'<div class="banner">{e(banner)}</div><div class="watermark" aria-hidden="true"><span>{e(banner)}</span></div>'
                 if banner else "")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(title)}{" (MOCK)" if banner else ""} · Liquidity Policy Simulator</title><style>{CSS}</style></head>
<body>{mock_bits}<main>
<nav>{nav}</nav>
<h1>{e(title)}</h1>
<div class="disclosure">{disclosure()}</div>
{body}
<p class="stamp">{stamp}</p>
{f'<div class="banner" style="position:static">{e(banner)}</div>' if banner else ""}
</main></body></html>"""
