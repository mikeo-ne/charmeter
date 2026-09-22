#!/usr/bin/env python3
"""Build the static Chartmeter site into site/.

Dependency-free: renders the Markdown subset used across this repo (headings,
tables, lists, task lists, fenced code, blockquotes, rules, inline emphasis,
links) so the build needs no pip install anywhere, including CI.

Usage:
    python3 scripts/build_site.py [--out site]
"""

from __future__ import annotations

import argparse
import datetime as _dt
import html
import io
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

PAGES = [
    ("index.html", "README.md", "Overview"),
    ("arena-architecture.html", "docs/01-arena-architecture.md", "1 · Are.na Architecture"),
    ("tiered-filtering.html", "docs/02-tiered-filtering.md", "2 · Tiered Filtering"),
    ("regional-playbook.html", "docs/03-regional-playbook.md", "3 · Regional Playbook"),
    ("execution-workflow.html", "docs/04-execution-workflow.md", "Execution Workflow"),
    ("data-schemas.html", "docs/05-data-schemas.md", "Data Schemas"),
    ("data-sources.html", "docs/06-data-sources.md", "Automated Data Sources"),
    ("demo-guide.html", "docs/07-demo-guide.md", "Client Demo Guide"),
    ("report.html", None, "Live Report"),
    ("templates.html", None, "Templates"),
]

TEMPLATES = [
    ("templates/artist-baseline.md", "Artist Baseline & Identity"),
    ("templates/competitor-swot.md", "Competitor SWOT"),
    ("templates/dj-seeding-tracker.md", "DJ Seeding Tracker"),
    ("templates/swipe-file-entry.md", "Swipe File Entry"),
    ("templates/campaign-brief.md", "Campaign Brief"),
]

# --------------------------------------------------------------------------- inline

_INLINE_CODE = re.compile(r"`([^`]+)`")
_LINK = re.compile(r"\[([^\]]+)\]\(([^)]+)\)")
_BOLD = re.compile(r"\*\*([^*]+)\*\*")
_ITALIC = re.compile(r"(?<![*\w])\*([^*\n]+)\*(?!\*)")


def _rewrite_href(href: str) -> str:
    """Point repo-relative Markdown links at their built HTML pages."""
    if href.startswith(("http://", "https://", "#", "mailto:")):
        return href
    clean = href.split("#", 1)[0].lstrip("./")
    while clean.startswith("../"):
        clean = clean[3:]
    for out, src, _ in PAGES:
        if src and clean == src:
            return out
    if clean.startswith("templates"):
        return "templates.html"
    if clean.startswith("data/"):
        return "https://github.com/mikeo-ne/charmeter/blob/main/" + clean
    return href


def inline(text: str) -> str:
    slots: list[str] = []

    def stash(markup: str) -> str:
        slots.append(markup)
        return "\x00%d\x00" % (len(slots) - 1)

    text = _INLINE_CODE.sub(lambda m: stash("<code>%s</code>" % html.escape(m.group(1))), text)
    text = html.escape(text)
    text = _LINK.sub(
        lambda m: stash('<a href="%s">%s</a>' % (html.escape(_rewrite_href(m.group(2))), m.group(1))),
        text,
    )
    text = _BOLD.sub(r"<strong>\1</strong>", text)
    text = _ITALIC.sub(r"<em>\1</em>", text)
    text = text.replace("·", "&middot;").replace("→", "&rarr;").replace("—", "&mdash;")
    # Slots may nest (e.g. a link whose label contains inline code), so keep
    # expanding until no placeholders remain rather than a single pass.
    for _ in range(10):
        if "\x00" not in text:
            break
        text = re.sub(r"\x00(\d+)\x00", lambda m: slots[int(m.group(1))], text)
    return text.replace("\x00", "")


def slugify(text: str) -> str:
    s = re.sub(r"<[^>]+>", "", text)
    s = re.sub(r"[^a-zA-Z0-9\s-]", "", s).strip().lower()
    return re.sub(r"[\s-]+", "-", s) or "section"


# --------------------------------------------------------------------------- block

def render(md: str) -> tuple[str, list[tuple[int, str, str]]]:
    """Return (html, table-of-contents entries as (level, text, anchor))."""
    out = io.StringIO()
    toc: list[tuple[int, str, str]] = []
    lines = md.splitlines()
    i = 0
    list_stack: list[str] = []

    def close_lists(to_depth: int = 0) -> None:
        while len(list_stack) > to_depth:
            out.write("</%s>\n" % list_stack.pop())

    while i < len(lines):
        line = lines[i]
        stripped = line.strip()

        if stripped.startswith("```"):
            close_lists()
            i += 1
            buf = []
            while i < len(lines) and not lines[i].strip().startswith("```"):
                buf.append(lines[i])
                i += 1
            i += 1
            out.write("<pre><code>%s</code></pre>\n" % html.escape("\n".join(buf)))
            continue

        if not stripped:
            close_lists()
            i += 1
            continue

        if re.fullmatch(r"-{3,}|\*{3,}", stripped):
            close_lists()
            out.write("<hr>\n")
            i += 1
            continue

        m = re.match(r"(#{1,6})\s+(.*)", stripped)
        if m:
            close_lists()
            level = len(m.group(1))
            text = inline(m.group(2))
            anchor = slugify(m.group(2))
            if level <= 3:
                toc.append((level, re.sub(r"<[^>]+>", "", text), anchor))
            out.write('<h%d id="%s">%s</h%d>\n' % (level, anchor, text, level))
            i += 1
            continue

        # table
        if stripped.startswith("|") and i + 1 < len(lines) and re.fullmatch(
            r"\|[\s:|-]+\|", lines[i + 1].strip()
        ):
            close_lists()
            def cells(row: str) -> list[str]:
                return [c.strip() for c in row.strip().strip("|").split("|")]

            header = cells(stripped)
            i += 2
            out.write('<div class="table-wrap"><table>\n<thead><tr>')
            for c in header:
                out.write("<th>%s</th>" % inline(c))
            out.write("</tr></thead>\n<tbody>\n")
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = cells(lines[i])
                row += [""] * (len(header) - len(row))
                out.write("<tr>")
                for c in row[: len(header)]:
                    out.write("<td>%s</td>" % inline(c))
                out.write("</tr>\n")
                i += 1
            out.write("</tbody></table></div>\n")
            continue

        if stripped.startswith("> "):
            close_lists()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(lines[i].strip().lstrip(">").strip())
                i += 1
            out.write("<blockquote>%s</blockquote>\n" % inline(" ".join(buf)))
            continue

        m = re.match(r"([-*])\s+(.*)", stripped)
        if m:
            indent = len(line) - len(line.lstrip(" "))
            depth = indent // 2 + 1
            while len(list_stack) > depth:
                out.write("</%s>\n" % list_stack.pop())
            while len(list_stack) < depth:
                list_stack.append("ul")
                out.write("<ul>\n")
            item = m.group(2)
            task = re.match(r"\[([ xX])\]\s*(.*)", item)
            if task:
                checked = " checked" if task.group(1).lower() == "x" else ""
                out.write(
                    '<li class="task"><input type="checkbox" disabled%s> %s</li>\n'
                    % (checked, inline(task.group(2)))
                )
            else:
                out.write("<li>%s</li>\n" % inline(item))
            i += 1
            continue

        m = re.match(r"(\d+)\.\s+(.*)", stripped)
        if m:
            if list_stack[-1:] != ["ol"]:
                close_lists()
                list_stack.append("ol")
                out.write("<ol>\n")
            out.write("<li>%s</li>\n" % inline(m.group(2)))
            i += 1
            continue

        close_lists()
        buf = []
        while i < len(lines) and lines[i].strip() and not re.match(
            r"(#{1,6}\s|[-*]\s|\d+\.\s|\||>|```)", lines[i].strip()
        ):
            buf.append(lines[i].strip())
            i += 1
        if buf:
            out.write("<p>%s</p>\n" % inline(" ".join(buf)))
        else:
            i += 1

    close_lists()
    return out.getvalue(), toc


# --------------------------------------------------------------------------- shell

CSS = """
:root{--bg:#0d0f12;--panel:#14181d;--line:#242b33;--fg:#e6e9ee;--mut:#98a4b3;
--acc:#f2c14e;--acc2:#4ea3f2;--ok:#4fbf7b;--bad:#e2685f}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;background:var(--bg);color:var(--fg);
font:16px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI",Inter,Roboto,Helvetica,Arial,sans-serif}
a{color:var(--acc2);text-decoration:none}
a:hover{text-decoration:underline}
.layout{display:grid;grid-template-columns:270px minmax(0,1fr);min-height:100vh}
aside{background:var(--panel);border-right:1px solid var(--line);padding:26px 20px;
position:sticky;top:0;height:100vh;overflow-y:auto}
.brand{font-weight:700;font-size:15px;letter-spacing:.06em;text-transform:uppercase;color:var(--acc)}
.brand small{display:block;text-transform:none;letter-spacing:0;font-weight:400;
font-size:12px;color:var(--mut);margin-top:6px;line-height:1.45}
nav{margin-top:26px}
nav a{display:block;padding:7px 10px;border-radius:6px;color:var(--fg);font-size:14px}
nav a:hover{background:#1c222a;text-decoration:none}
nav a.active{background:#1c222a;color:var(--acc);font-weight:600}
.toc{margin-top:22px;border-top:1px solid var(--line);padding-top:16px}
.toc div{font-size:11px;text-transform:uppercase;letter-spacing:.08em;color:var(--mut);margin-bottom:8px}
.toc a{display:block;padding:3px 0;font-size:13px;color:var(--mut)}
.toc a:hover{color:var(--fg)}
.toc a.l3{padding-left:12px;font-size:12.5px}
main{padding:44px 52px 90px;max-width:960px}
h1{font-size:30px;margin:0 0 20px;line-height:1.25}
h2{font-size:21px;margin:38px 0 14px;padding-bottom:7px;border-bottom:1px solid var(--line)}
h3{font-size:17px;margin:26px 0 10px;color:var(--acc)}
h4{font-size:15px;margin:20px 0 8px;color:var(--mut)}
p{margin:12px 0}
ul,ol{margin:12px 0;padding-left:22px}
li{margin:5px 0}
li.task{list-style:none;margin-left:-18px}
code{background:#1b2027;border:1px solid var(--line);border-radius:4px;
padding:1px 5px;font-size:13px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}
pre{background:#11151a;border:1px solid var(--line);border-radius:8px;padding:14px 16px;overflow-x:auto}
pre code{background:none;border:0;padding:0;font-size:13px;line-height:1.55}
blockquote{margin:16px 0;padding:10px 16px;border-left:3px solid var(--acc);
background:#171b21;border-radius:0 6px 6px 0;color:#cfd6df}
hr{border:0;border-top:1px solid var(--line);margin:34px 0}
.table-wrap{overflow-x:auto;margin:16px 0}
table{border-collapse:collapse;width:100%;font-size:14px}
th,td{border:1px solid var(--line);padding:8px 11px;text-align:left;vertical-align:top}
th{background:#1a1f26;font-weight:600;white-space:nowrap}
tbody tr:nth-child(even){background:#12161b}
.meta{color:var(--mut);font-size:13px;margin:0 0 26px;padding-bottom:16px;border-bottom:1px solid var(--line)}
.banner{background:#1d1a12;border:1px solid #3d3421;color:#e8d9a8;
padding:12px 16px;border-radius:8px;font-size:14px;margin:0 0 26px}
@media(max-width:860px){.layout{grid-template-columns:1fr}
aside{position:static;height:auto}main{padding:28px 20px 60px}}
"""


def shell(title: str, body: str, toc, active: str, built: str) -> str:
    nav = "\n".join(
        '<a href="%s"%s>%s</a>' % (out, ' class="active"' if out == active else "", html.escape(label))
        for out, _, label in PAGES
    )
    toc_html = ""
    if toc:
        items = "\n".join(
            '<a href="#%s" class="l%d">%s</a>' % (anchor, lvl, text)
            for lvl, text, anchor in toc
            if lvl in (2, 3)
        )
        if items:
            toc_html = '<div class="toc"><div>On this page</div>%s</div>' % items
    return """<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>%s &middot; Chartmeter</title>
<meta name="description" content="Chartmeter // East Africa Intelligence Hub \u2014 visual qualitative research and market mapping for East African independent music careers.">
<style>%s</style></head>
<body><div class="layout">
<aside>
<div class="brand">Chartmeter<small>East Africa Intelligence Hub</small></div>
<nav>%s</nav>%s
</aside>
<main>%s
<hr><p class="meta">Built %s &middot; <a href="https://github.com/mikeo-ne/charmeter">mikeo-ne/charmeter</a></p>
</main></div></body></html>
""" % (html.escape(title), CSS, nav, toc_html, body, built)


# --------------------------------------------------------------------------- pages

def report_markdown() -> str:
    try:
        res = subprocess.run(
            [sys.executable, os.path.join(ROOT, "scripts", "chartmeter.py"), "report"],
            capture_output=True, text=True, timeout=60, cwd=ROOT,
        )
        if res.returncode == 0 and res.stdout.strip():
            return res.stdout
        return "# Live Report\n\nReport generation failed.\n\n```\n%s\n```\n" % (
            (res.stderr or "no output").strip()
        )
    except Exception as exc:  # pragma: no cover
        return "# Live Report\n\nReport generation failed: `%s`\n" % exc


def templates_markdown() -> str:
    parts = [
        "# Templates",
        "",
        "Copy-paste scaffolds for Are.na text blocks. Source files live in "
        "[`templates/`](https://github.com/mikeo-ne/charmeter/tree/main/templates).",
        "",
    ]
    for path, title in TEMPLATES:
        full = os.path.join(ROOT, path)
        if not os.path.exists(full):
            continue
        with open(full, encoding="utf-8") as fh:
            content = fh.read()
        parts += ["---", "", "## %s" % title, "", "```", content.rstrip(), "```", ""]
    return "\n".join(parts)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="site")
    args = ap.parse_args()

    outdir = args.out if os.path.isabs(args.out) else os.path.join(ROOT, args.out)
    os.makedirs(outdir, exist_ok=True)
    built = _dt.datetime.now().strftime("%Y-%m-%d %H:%M")

    for name, src, label in PAGES:
        if src:
            with open(os.path.join(ROOT, src), encoding="utf-8") as fh:
                md = fh.read()
        elif name == "report.html":
            md = report_markdown()
        else:
            md = templates_markdown()

        body, toc = render(md)
        if name == "report.html":
            body = (
                '<p class="banner">Generated from the committed sample data in '
                "<code>data/</code>. The artist and competitors are illustrative "
                "placeholders &mdash; replace them before drawing conclusions.</p>" + body
            )
        title = label.split("\u00b7")[-1].strip()
        with open(os.path.join(outdir, name), "w", encoding="utf-8") as fh:
            fh.write(shell(title, body, toc, name, built))
        print("wrote %s" % os.path.join(args.out, name))

    open(os.path.join(outdir, ".nojekyll"), "w").close()
    print("\nBuilt %d pages into %s/" % (len(PAGES), args.out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
