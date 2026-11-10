#!/usr/bin/env python3
"""External links open in a new tab — shared rule for every Ullswater Investments site (Nov 2026).

Post-processes every .html file under a folder, after the site has been generated:
  * links to any host outside the Ullswater network get target="_blank" and rel="noopener noreferrer";
  * text links also get a small "↗" icon and a hidden "(opens in a new tab)" label for screen readers;
  * links inside the network (*.ullswaterinvestments.com, ullswaterinvestments.eu), relative links,
    #anchors, mailto: and tel: are left untouched, so moving between our own sites stays in the same tab.
Idempotent (safe to run twice). <script> and <style> blocks are never modified. No dependencies.

Usage:  python3 extlinks.py <site folder> [--check]
   --check only reports external links without target="_blank" and exits 1 if any are found.
Same file in ullswater-www, ullswater-calls, ullswater-news (main and events-site) and ullswater-landings.
"""
import re, sys, pathlib
from urllib.parse import urlparse

INTERNAL = ("ullswaterinvestments.com", "ullswaterinvestments.eu")
STYLE = ('<style id="uw-ext">.uw-ext{display:inline-block;margin-left:.25em;font-size:.85em;line-height:1;text-decoration:none;opacity:.75}'
         '.uw-sr{position:absolute!important;width:1px;height:1px;padding:0;margin:-1px;overflow:hidden;clip:rect(0,0,0,0);white-space:nowrap;border:0}</style>')
LABEL = {"en": " (opens in a new tab)", "es": " (se abre en una pestaña nueva)"}
LANG = re.compile(r'<html\b[^>]*\blang\s*=\s*["\']?([a-zA-Z]{2})', re.I)

A = re.compile(r'<a\b([^>]*)>(.*?)</a\s*>', re.I | re.S)
HREF = re.compile(r'''\bhref\s*=\s*(["'])(.*?)\1''', re.I | re.S)
SKIP = re.compile(r'(<script\b.*?</script\s*>|<style\b.*?</style\s*>|<!--.*?-->)', re.I | re.S)
BLOCKY = re.compile(r'<(img|svg|picture|div|section|article|figure|h[1-6]|p|ul|ol|table)\b', re.I)


def external(href):
    href = href.strip()
    if href.startswith("//"):
        href = "https:" + href
    if not re.match(r'https?://', href, re.I):
        return False
    host = (urlparse(href).hostname or "").lower().rstrip(".")
    return bool(host) and not any(host == d or host.endswith("." + d) for d in INTERNAL)


def _attr(attrs, name):
    m = re.search(r'''\b%s\s*=\s*(["'])(.*?)\1''' % name, attrs, re.I | re.S)
    return m


def fix_anchor(m, label=LABEL["en"]):
    attrs, inner = m.group(1), m.group(2)
    h = HREF.search(attrs)
    if not h or not external(h.group(2)):
        return m.group(0)
    t = _attr(attrs, "target")
    if t:
        attrs = attrs[:t.start()] + 'target="_blank"' + attrs[t.end():]
    else:
        attrs += ' target="_blank"'
    r = _attr(attrs, "rel")
    if r:
        vals = r.group(2).split()
        vals += [v for v in ("noopener", "noreferrer") if v not in vals]
        attrs = attrs[:r.start()] + 'rel="%s"' % " ".join(vals) + attrs[r.end():]
    else:
        attrs += ' rel="noopener noreferrer"'
    if 'class="uw-sr"' not in inner:
        # image/card links: no visible icon, only the screen-reader label
        sr = '<span class="uw-sr">%s</span>' % label
        inner += ('<span class="uw-ext" aria-hidden="true">↗</span>' + sr) if not (BLOCKY.search(inner) or "↗" in inner) else sr
    return "<a%s>%s</a>" % (attrs, inner)


def process(text):
    lm = LANG.search(text)
    label = LABEL.get(lm.group(1).lower() if lm else "en", LABEL["en"])
    if re.search(r'<html\b[^>]*\bdata-lang\s*=', text, re.I):  # bilingual landings: EN/ES shown by html[data-lang]
        label = '<span class="en">%s</span><span class="es">%s</span>' % (LABEL["en"], LABEL["es"])
    parts = SKIP.split(text)
    out = [p if i % 2 else A.sub(lambda m: fix_anchor(m, label), p) for i, p in enumerate(parts)]
    text = "".join(out)
    if 'class="uw-' in text and 'id="uw-ext"' not in text:
        text = re.sub(r'</head\s*>', STYLE + "</head>", text, count=1, flags=re.I) if re.search(r'</head\s*>', text, re.I) else STYLE + text
    return text


def missing(text):
    bad = []
    for i, p in enumerate(SKIP.split(text)):
        if i % 2:
            continue
        for m in A.finditer(p):
            h = HREF.search(m.group(1))
            t = _attr(m.group(1), "target")
            if h and external(h.group(2)) and not (t and t.group(2) == "_blank"):
                bad.append(h.group(2))
    return bad


def run(folder, check=False):
    root = pathlib.Path(folder)
    files = sorted(root.rglob("*.html")) if root.is_dir() else [root]
    changed, bad = 0, {}
    for f in files:
        text = f.read_text(encoding="utf-8", errors="surrogateescape")
        if check:
            b = missing(text)
            if b:
                bad[str(f)] = b
            continue
        new = process(text)
        if new != text:
            f.write_text(new, encoding="utf-8", errors="surrogateescape")
            changed += 1
    if check:
        for f, b in bad.items():
            print(f"{f}: {len(b)} external link(s) without target=_blank, e.g. {b[0]}")
        print(f"extlinks check: {len(files)} pages, {len(bad)} with problems")
        return 1 if bad else 0
    print(f"extlinks: {changed} of {len(files)} pages updated (external links open in a new tab)")
    return 0


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    sys.exit(run(args[0] if args else ".", check="--check" in sys.argv))
