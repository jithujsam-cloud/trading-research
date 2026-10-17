"""HTML for the web app. Every value from data is escaped before it reaches the page."""

import html

import markdown as md

CSS = """
:root{--bg:#f6f7f5;--panel:#fff;--fg:#1d2320;--muted:#5d6762;--line:#dfe3df;--accent:#1f5f4a;--bad:#b3261e;--ok:#1e6b3a;--warn:#8a5a00;
--sans:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--mono:ui-monospace,SFMono-Regular,Menlo,monospace}
@media (prefers-color-scheme:dark){:root{--bg:#141816;--panel:#1c211f;--fg:#e7ece9;--muted:#9aa49f;--line:#2e3532;--accent:#7cc4a4;--bad:#f2867c;--ok:#7fd29a;--warn:#e8b75a;color-scheme:dark}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 var(--sans)}
header{border-bottom:1px solid var(--line);background:var(--panel)}
.wrap{max-width:62rem;margin:0 auto;padding-inline:max(16px,env(safe-area-inset-left))}
header .wrap{display:flex;flex-wrap:wrap;gap:.25rem 1.25rem;align-items:center;padding-block:.75rem}
header b{font-weight:650;margin-right:auto}nav{display:flex;flex-wrap:wrap;gap:.25rem 1rem}
nav a{color:var(--muted);text-decoration:none}nav a:hover,nav a[aria-current]{color:var(--fg)}
main.wrap{padding-block:1.5rem 3rem;display:grid;gap:1.25rem}
h1{font-size:1.5rem;margin:0;text-wrap:balance}h2{font-size:1.15rem;margin:1.5rem 0 .5rem}
.card{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:1.1rem 1.25rem;min-width:0}
.grid{display:grid;gap:1rem;grid-template-columns:repeat(auto-fit,minmax(min(100%,14rem),1fr))}
.k{font-size:.8rem;color:var(--muted);letter-spacing:.02em}.v{font-size:1.6rem;font-variant-numeric:tabular-nums}
.bad{color:var(--bad)}.ok{color:var(--ok)}.warn{color:var(--warn)}.muted{color:var(--muted)}
.pill{display:inline-block;border:1px solid currentColor;border-radius:999px;padding:0 .6rem;font-size:.8rem}
table{border-collapse:collapse;width:100%;font-variant-numeric:tabular-nums}
.t{overflow-x:auto}th,td{text-align:left;padding:.35rem .6rem;border-bottom:1px solid var(--line);white-space:nowrap}
th{color:var(--muted);font-weight:600;font-size:.85rem}
form{display:grid;gap:.75rem;max-width:28rem}label{display:grid;gap:.25rem;font-size:.9rem}
input{font:inherit;padding:.5rem .6rem;border:1px solid var(--line);border-radius:8px;background:var(--bg);color:var(--fg)}
button{font:inherit;padding:.55rem 1rem;border-radius:8px;border:1px solid var(--accent);background:var(--accent);color:var(--bg);cursor:pointer;justify-self:start}
button.link{background:none;color:var(--muted);border:none;padding:0}
:focus-visible{outline:2px solid var(--accent);outline-offset:2px}
.report p,.report li{max-width:70ch}code{font-family:var(--mono)}
"""

NAV = [("/", "Overview"), ("/report", "History report"), ("/upload", "Upload statements"),
       ("/viability", "Option viability"), ("/snapshots", "Daily snapshots")]


def esc(v) -> str:
    return html.escape("" if v is None else str(v))


def page(title: str, body: str, current: str = "", logged_in: bool = True) -> str:
    nav = ""
    if logged_in:
        links = "".join(f'<a href="{h}"{" aria-current=page" if h == current else ""}>{esc(t)}</a>' for h, t in NAV)
        nav = (f'<nav aria-label="Main">{links}</nav>'
               '<form method="post" action="/logout" style="display:inline"><button class="link" type="submit">Log out</button></form>')
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8">'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><title>{esc(title)} · tradelab</title>'
            f'<style>{CSS}</style></head><body><header><div class="wrap"><b>tradelab</b>{nav}</div></header>'
            f'<main class="wrap">{body}</main></body></html>')


def markdown_html(text: str) -> str:
    """Render report Markdown. The source is HTML-escaped first, so data cannot inject markup."""
    rendered = md.markdown(html.escape(text, quote=False), extensions=["tables"])
    return rendered.replace("<table>", '<div class="t"><table>').replace("</table>", "</table></div>")


def rupees(v) -> str:
    if v is None:
        return "n/a"
    return f"{'−' if v < 0 else ''}₹{abs(v):,.0f}"


def signed_class(v) -> str:
    return "" if v is None else ("bad" if v < 0 else "ok" if v > 0 else "")
