# /// script
# requires-python = ">=3.11"
# dependencies = ["markdown>=3.6", "pygments>=2.17"]
# ///
"""Static site generator for the cookbook.

Scans top-level category folders for markdown articles, renders them to HTML
with a heading-based table of contents (left), a site-wide index (right),
and generates an interactive mind-map SVG used as the landing page plus a
compact locator map at the top of every article.

Run: uv run build.py
"""

import html
import re
import shutil
import datetime
from pathlib import Path

import markdown
from pygments.formatters import HtmlFormatter

# ---------------------------------------------------------------- config

ROOT = Path(__file__).parent
OUT = ROOT / "_site"

SITE_TITLE = "Cookbook"
TAGLINE = "A living cookbook of software development practices, architecture patterns, and data engineering solutions."
AUTHOR = "Ahmad Hatahet"
GITHUB_OWNER = "ahmadhatahet"
GITHUB_REPO = "cookbook"
GITHUB_BRANCH = "main"
BASE_URL = f"https://{GITHUB_OWNER}.github.io/{GITHUB_REPO}"
RAW_BASE = f"https://raw.githubusercontent.com/{GITHUB_OWNER}/{GITHUB_REPO}/{GITHUB_BRANCH}"

# Folder name -> display name. Folders not listed here still work:
# they get a title-cased display name automatically.
CATEGORY_NAMES = {
    "automation": "Daily Automation",
    "architecture": "Architecture & Paradigms",
}

# Gentle palette, one color per category (cycled if more categories exist).
PALETTE = ["#4a7c74", "#5b7fa6", "#b3703f", "#7d6b94", "#75823f", "#a5636f"]

SKIP_DIRS = {"_site", "_book", "templates", "assets", ".github", ".claude"}

# Citation text lives in citation.txt so it can be edited without touching
# this script. Available placeholders: {author} {year} {title} {site_title}
# {url} {category}
CITATION_FILE = ROOT / "citation.txt"
CITATION_FALLBACK = '{author}. ({year}). "{title}." {site_title}. {url}'


def citation_template() -> str:
    if CITATION_FILE.exists():
        return CITATION_FILE.read_text(encoding="utf-8").strip()
    return CITATION_FALLBACK

# ---------------------------------------------------------------- content model


class Article:
    def __init__(self, path: Path, category: str):
        self.src = path
        self.category = category
        text = path.read_text(encoding="utf-8")
        self.meta, self.body = parse_frontmatter(text)
        self.title = self.meta.get("title") or first_h1(self.body) or path.stem.replace("-", " ").title()
        self.slug = path.stem
        self.out_rel = f"{category}/{self.slug}.html" if category else f"{self.slug}.html"
        self.md_rel = str(path.relative_to(ROOT))


def parse_frontmatter(text: str) -> tuple[dict, str]:
    meta = {}
    m = re.match(r"\A---\s*\n(.*?)\n---\s*\n", text, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip()] = v.strip().strip('"').strip("'")
        text = text[m.end():]
    return meta, text


def first_h1(body: str) -> str | None:
    m = re.search(r"^#\s+(.+)$", body, re.MULTILINE)
    return m.group(1).strip() if m else None


def discover() -> dict[str, list[Article]]:
    """Every top-level folder containing .md files is a category."""
    categories: dict[str, list[Article]] = {}
    for d in sorted(p for p in ROOT.iterdir() if p.is_dir()):
        if d.name.startswith(".") or d.name in SKIP_DIRS:
            continue
        articles = [Article(f, d.name) for f in sorted(d.glob("*.md"))]
        if articles:
            articles.sort(key=lambda a: a.title.lower())
            categories[d.name] = articles
    return categories


def display_name(folder: str) -> str:
    return CATEGORY_NAMES.get(folder, folder.replace("-", " ").replace("_", " ").title())


def cat_color(folder: str, categories: dict) -> str:
    return PALETTE[list(categories).index(folder) % len(PALETTE)]


# ---------------------------------------------------------------- markdown rendering


def render_markdown(body: str) -> tuple[str, list]:
    md = markdown.Markdown(
        extensions=["extra", "codehilite", "toc", "sane_lists"],
        extension_configs={
            "codehilite": {"guess_lang": False, "noclasses": False},
            "toc": {"toc_depth": "2-4", "permalink": "#", "permalink_title": "Link to this section"},
        },
    )
    html_body = md.convert(body)
    return html_body, md.toc_tokens


def toc_html(tokens: list) -> str:
    if not tokens:
        return ""

    def items(toks):
        out = []
        for t in toks:
            sub = f"<ul>{items(t['children'])}</ul>" if t["children"] else ""
            # token names arrive already HTML-escaped from the toc extension
            out.append(f'<li><a href="#{t["id"]}">{t["name"]}</a>{sub}</li>')
        return "".join(out)

    return f"<nav class='page-toc' aria-label='On this page'><h2>On this page</h2><ul>{items(tokens)}</ul></nav>"


# ---------------------------------------------------------------- svg helpers

def esc(s: str) -> str:
    return html.escape(s, quote=True)


def tw(text: str, size: float) -> float:
    """Rough text width estimate for the system sans stack."""
    return len(text) * size * 0.58


def pill(x, y, text, size, color, href=None, anchor="middle", bold=False, cls=""):
    w = tw(text, size) + size * 1.6
    h = size * 2.1
    if anchor == "start":
        rx = x
        tx = x + w / 2
    elif anchor == "end":
        rx = x - w
        tx = x - w / 2
    else:
        rx = x - w / 2
        tx = x
    weight = "600" if bold else "500"
    node = (
        f'<g class="node {cls}">'
        f'<rect x="{rx:.1f}" y="{y - h / 2:.1f}" width="{w:.1f}" height="{h:.1f}" rx="{h / 2:.1f}" '
        f'fill="{color}" fill-opacity="0.1" stroke="{color}" stroke-opacity="0.45" stroke-width="1.2"/>'
        f'<text x="{tx:.1f}" y="{y:.1f}" text-anchor="middle" dominant-baseline="central" '
        f'font-size="{size}" font-weight="{weight}" fill="{color}">{esc(text)}</text></g>'
    )
    if href:
        node = f'<a href="{esc(href)}">{node}</a>'
    return node, w, h


def curve(x1, y1, x2, y2, color, opacity=0.5):
    mx = (x1 + x2) / 2
    return (
        f'<path d="M {x1:.1f} {y1:.1f} C {mx:.1f} {y1:.1f}, {mx:.1f} {y2:.1f}, {x2:.1f} {y2:.1f}" '
        f'fill="none" stroke="{color}" stroke-opacity="{opacity}" stroke-width="1.6"/>'
    )


# ---------------------------------------------------------------- mind map (landing page)


def wrap_label(text: str, max_chars: int = 24) -> list[str]:
    lines, line = [], ""
    for word in text.split():
        if line and len(line) + 1 + len(word) > max_chars:
            lines.append(line)
            line = word
        else:
            line = f"{line} {word}".strip()
    if line:
        lines.append(line)
    return lines


def mindmap_svg(categories: dict[str, list[Article]], prefix: str = "") -> str:
    """Horizontal mind map: center node, categories fan out left/right,
    each category's articles stacked as clickable leaves."""
    LINE = 20     # px per wrapped label line
    PAD = 18      # vertical padding per article leaf
    CAT_GAP = 36
    FONT = 15
    BRANCH = 70   # curve length center -> category and category -> leaves
    center_w = tw(SITE_TITLE, 21) + 21 * 1.6

    labels = {a.slug: wrap_label(a.title) for arts in categories.values() for a in arts}

    def cat_w(folder: str) -> float:
        return tw(display_name(folder), 17) + 17 * 1.6

    def block_height(folder: str) -> float:
        return sum(len(labels[a.slug]) * LINE + PAD for a in categories[folder])

    # Balance categories between right and left side by rendered height.
    sides = {"R": [], "L": []}
    heights = {"R": 0.0, "L": 0.0}
    for folder in categories:
        side = "R" if heights["R"] <= heights["L"] else "L"
        sides[side].append(folder)
        heights[side] += block_height(folder) + CAT_GAP

    H = max(heights["R"], heights["L"], 220) + 60
    cy = H / 2

    # Everything is positioned edge-to-edge so labels can never overlap,
    # whatever their length: center pill -> curve -> category pill -> curve
    # -> article leaves.
    cat_inner = center_w / 2 + BRANCH                     # inner edge of category pills
    art_x, max_label = {}, {"R": 0.0, "L": 0.0}
    for s in ("R", "L"):
        widest_cat = max((cat_w(f) for f in sides[s]), default=0.0)
        art_x[s] = cat_inner + widest_cat + BRANCH        # leaf dot distance from center
        for folder in sides[s]:
            for a in categories[folder]:
                w = max(tw(line, FONT) for line in labels[a.slug])
                max_label[s] = max(max_label[s], w + 40)
    half = {
        s: max(art_x[s] + max_label[s], center_w / 2) + 30 if sides[s] else center_w / 2 + 30
        for s in ("R", "L")
    }
    W = half["L"] + half["R"]
    cx = half["L"]

    parts = []
    for s, sign in (("R", 1), ("L", -1)):
        y = cy - heights[s] / 2 + CAT_GAP / 2
        for folder in sides[s]:
            arts = categories[folder]
            color = cat_color(folder, categories)
            block = block_height(folder)
            cat_y = y + block / 2
            w = cat_w(folder)
            cat_x = cx + sign * (cat_inner + w / 2)
            cat_url = f"{prefix}{folder}/index.html"

            parts.append(curve(cx + sign * (center_w / 2 + 4), cy, cx + sign * (cat_inner - 6), cat_y, color))
            node, _, _ = pill(cat_x, cat_y, display_name(folder), 17, color, href=cat_url, bold=True, cls="cat")
            parts.append(node)

            ay = y
            for a in arts:
                lines = labels[a.slug]
                leaf_h = len(lines) * LINE + PAD
                ly = ay + leaf_h / 2
                ax = cx + sign * art_x[s]
                anchor = "start" if sign > 0 else "end"
                ty0 = ly - (len(lines) - 1) * LINE / 2
                tspans = "".join(
                    f'<text x="{ax + sign * 12:.1f}" y="{ty0 + i * LINE:.1f}" text-anchor="{anchor}" '
                    f'dominant-baseline="central" font-size="{FONT}" fill="#3d4144">{esc(line)}</text>'
                    for i, line in enumerate(lines)
                )
                parts.append(curve(cx + sign * (cat_inner + w + 6), cat_y, ax - sign * 6, ly, color, 0.35))
                parts.append(
                    f'<a href="{prefix}{a.out_rel}"><g class="node leaf">'
                    f'<circle cx="{ax:.1f}" cy="{ly:.1f}" r="4.5" fill="{color}"/>{tspans}</g></a>'
                )
                ay += leaf_h
            y += block + CAT_GAP

    center, _, _ = pill(cx, cy, SITE_TITLE, 21, "#2f3437", bold=True, cls="root")
    parts.append(center)

    return (
        f'<svg class="mindmap" viewBox="0 0 {W:.0f} {H:.0f}" width="{W:.0f}" height="{H:.0f}" role="img" '
        f'aria-label="Mind map of cookbook categories and articles" '
        f'font-family="ui-sans-serif, system-ui, sans-serif">{"".join(parts)}</svg>'
    )


def minimap_svg(categories: dict, article: Article, prefix: str) -> str:
    """Compact locator shown on article pages: Cookbook -> category -> current
    article, with sibling articles as small linked dots."""
    color = cat_color(article.category, categories)
    cat = display_name(article.category)
    siblings = categories[article.category]

    size = 14
    x = 14
    y = 34
    parts = []

    node, w, _ = pill(x, y, SITE_TITLE, size, "#2f3437", href=f"{prefix}index.html", anchor="start", bold=True)
    parts.append(node)
    x += w
    parts.append(curve(x, y, x + 34, y, color))
    x += 34
    node, w, _ = pill(x, y, cat, size, color, href=f"{prefix}{article.category}/index.html", anchor="start", bold=True)
    cat_cx = x + w / 2
    parts.append(node)
    x += w
    parts.append(curve(x, y, x + 34, y, color))
    x += 34
    node, w, _ = pill(x, y, article.title, size, color, anchor="start", bold=True, cls="current")
    parts.append(node)
    x += w

    # sibling dots under the category pill
    dot_y = y + 30
    dot_x = cat_cx - (len(siblings) - 1) * 9
    for s in siblings:
        if s.slug == article.slug:
            parts.append(f'<circle cx="{dot_x:.1f}" cy="{dot_y}" r="5" fill="{color}"/>')
        else:
            parts.append(
                f'<a href="{prefix}{s.out_rel}"><circle cx="{dot_x:.1f}" cy="{dot_y}" r="4" '
                f'fill="{color}" fill-opacity="0.3" stroke="{color}" stroke-width="1">'
                f'<title>{esc(s.title)}</title></circle></a>'
            )
        dot_x += 18

    W = max(x + 14, dot_x + 14)
    return (
        f'<div class="minimap-wrap"><svg class="minimap" viewBox="0 0 {W:.0f} 80" width="{W:.0f}" height="80" '
        f'role="img" aria-label="You are here: {esc(cat)} / {esc(article.title)}" '
        f'font-family="ui-sans-serif, system-ui, sans-serif">{"".join(parts)}</svg></div>'
    )


# ---------------------------------------------------------------- page templates


def excerpt(body: str, max_len: int = 180) -> str:
    """First plain-text paragraph of a markdown body."""
    for block in re.split(r"\n\s*\n", body):
        block = block.strip()
        if not block or block.startswith(("#", "```", "|", ">", "-", "*", "!")):
            continue
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", block)      # links -> text
        text = re.sub(r"[`*_]", "", text)                          # inline markup
        text = re.sub(r"\s+", " ", text).strip()
        return text if len(text) <= max_len else text[: max_len].rsplit(" ", 1)[0] + "…"
    return ""


def site_index_html(categories: dict, prefix: str, current: Article | None) -> str:
    parts = ["<nav class='site-index' aria-label='All articles'><h2>All articles</h2>"]
    for folder, arts in categories.items():
        color = cat_color(folder, categories)
        parts.append(
            f"<h3><a href='{prefix}{folder}/index.html' style='color:{color}'>{esc(display_name(folder))}</a></h3><ul>"
        )
        for a in arts:
            cls = " class='current'" if current and a.out_rel == current.out_rel else ""
            parts.append(f"<li{cls}><a href='{prefix}{a.out_rel}'>{esc(a.title)}</a></li>")
        parts.append("</ul>")
    parts.append("</nav>")
    return "".join(parts)


def page(title: str, prefix: str, body: str, description: str = "") -> str:
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(title)} · {esc(SITE_TITLE)}</title>
<meta name="description" content="{esc(description or TAGLINE)}">
<link rel="stylesheet" href="{prefix}assets/style.css">
<link rel="stylesheet" href="{prefix}assets/pygments.css">
<link rel="icon" href="data:image/svg+xml,<svg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 100 100%22><text y=%22.9em%22 font-size=%2290%22>📖</text></svg>">
</head>
<body>
<header class="site-header">
  <a class="brand" href="{prefix}index.html">📖 {esc(SITE_TITLE)}</a>
  <nav><a href="{prefix}index.html">Home</a><a href="{prefix}about.html">About</a></nav>
</header>
{body}
<footer class="site-footer">© {datetime.date.today().year} {esc(AUTHOR)} · <a href="https://github.com/{GITHUB_OWNER}/{GITHUB_REPO}">Source on GitHub</a></footer>
<script src="{prefix}assets/main.js"></script>
</body>
</html>"""


def article_page(article: Article, categories: dict) -> str:
    prefix = "../" if article.category else ""
    content, toc_tokens = render_markdown(article.body)
    page_url = f"{BASE_URL}/{article.out_rel}"
    raw_url = f"{RAW_BASE}/{article.md_rel}"
    citation = citation_template().format(
        author=AUTHOR,
        year=datetime.date.today().year,
        title=article.title,
        site_title=SITE_TITLE,
        url=page_url,
        category=display_name(article.category),
    )

    agent_text = (
        f"# {article.title}\n"
        f"Source: {SITE_TITLE} — {page_url} (raw markdown: {raw_url})\n\n"
        f"{article.body.strip()}\n"
    )

    buttons = f"""
<div class="toolbar">
  <button class="btn" data-action="copy" data-copy="{esc(agent_text)}" title="Copy the full article as markdown, ready to paste into an AI agent">🤖 Copy for your Agent</button>
  <button class="btn" data-action="copy" data-copy="{esc(raw_url)}" title="Copy the raw GitHub markdown URL">📄 Copy raw link</button>
  <button class="btn" data-action="copy" data-copy="{esc(page_url + chr(10) + chr(10) + citation)}" title="Copy the page link with a citation">🔗 Share &amp; cite</button>
  <button class="btn" data-action="print" title="Open the print dialog to save this page as PDF">⬇ Download PDF</button>
</div>"""

    body = f"""
<div class="layout">
  <aside class="left">{toc_html(toc_tokens)}</aside>
  <main>
    {minimap_svg(categories, article, prefix)}
    {buttons}
    <article class="content">
      <p class="kicker"><a style="color:{cat_color(article.category, categories)}" href="index.html">{esc(display_name(article.category))}</a></p>
      <h1>{esc(article.title)}</h1>
      {content}
    </article>
  </main>
  <aside class="right">{site_index_html(categories, prefix, article)}</aside>
</div>"""
    return page(article.title, prefix, body, description=f"{article.title} — {display_name(article.category)}")


def category_page(folder: str, categories: dict) -> str:
    arts = categories[folder]
    color = cat_color(folder, categories)
    name = display_name(folder)
    cards = "".join(
        f"""<a class="card" href="{a.slug}.html">
  <h2>{esc(a.title)}</h2>
  <p>{esc(excerpt(a.body))}</p>
</a>"""
        for a in arts
    )
    body = f"""
<div class="layout">
  <aside class="left"></aside>
  <main>
    <article class="content category">
      <p class="kicker" style="color:{color}"><a href="../index.html">{esc(SITE_TITLE)}</a></p>
      <h1 style="color:{color}">{esc(name)}</h1>
      <p class="muted">{len(arts)} article{"s" if len(arts) != 1 else ""} in this category.</p>
      <div class="cards">{cards}</div>
    </article>
  </main>
  <aside class="right">{site_index_html(categories, "../", None)}</aside>
</div>"""
    return page(name, "../", body, description=f"{name} — all articles")


def home_page(categories: dict) -> str:
    n = sum(len(a) for a in categories.values())
    body = f"""
<main class="home">
  <p class="tagline">{esc(TAGLINE)}</p>
  <p class="hint">{n} articles across {len(categories)} categories — click any title to open it.</p>
  <div class="map-wrap">{mindmap_svg(categories)}</div>
</main>"""
    return page("Home", "", body)


def about_page(categories: dict) -> str:
    art = Article(ROOT / "about.md", "")
    content, toc_tokens = render_markdown(art.body)
    body = f"""
<div class="layout">
  <aside class="left">{toc_html(toc_tokens)}</aside>
  <main>
    <article class="content">
      <h1>{esc(art.title)}</h1>
      {content}
    </article>
  </main>
  <aside class="right">{site_index_html(categories, "", None)}</aside>
</div>"""
    return page(art.title, "", body)


# ---------------------------------------------------------------- build


def main():
    categories = discover()
    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "assets").mkdir(parents=True)

    for f in (ROOT / "templates").iterdir():
        shutil.copy(f, OUT / "assets" / f.name)
    (OUT / "assets" / "pygments.css").write_text(
        HtmlFormatter(style="friendly").get_style_defs(".codehilite"), encoding="utf-8"
    )
    (OUT / ".nojekyll").write_text("", encoding="utf-8")

    (OUT / "index.html").write_text(home_page(categories), encoding="utf-8")
    (OUT / "about.html").write_text(about_page(categories), encoding="utf-8")

    count = 0
    for folder, arts in categories.items():
        (OUT / folder).mkdir(exist_ok=True)
        (OUT / folder / "index.html").write_text(category_page(folder, categories), encoding="utf-8")
        for a in arts:
            (OUT / a.out_rel).write_text(article_page(a, categories), encoding="utf-8")
            count += 1

    print(f"Built {count} articles in {len(categories)} categories -> {OUT}")


if __name__ == "__main__":
    main()
