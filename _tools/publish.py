#!/usr/bin/env python3
"""Publish self-contained HTML pages to the public share site (share.axelmansoor.com).

  python3 publish.py add --src PATH --slug SLUG [--title T] [--desc D] [--date YYYY-MM-DD] [--push]
  python3 publish.py rebuild                 # regenerate index.html from manifest.json
  python3 publish.py remove --slug SLUG [--push]

The repo root is inferred from this script's location (_tools/.. == repo root).
"""
import argparse, json, os, re, shutil, subprocess, html
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_TITLE = "Axel Mansoor"
SITE_TAGLINE = "Things I've made and shared — guides, notes, and the occasional rabbit hole."
CUSTOM_URL = "https://share.axelmansoor.com"
PAGES_URL = "https://essentara.github.io/share"


def manifest_path():
    return os.path.join(REPO, "manifest.json")


def load_manifest():
    p = manifest_path()
    if not os.path.exists(p):
        return []
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def save_manifest(items):
    with open(manifest_path(), "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2)
        f.write("\n")


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def slugify(s):
    s = re.sub(r"[^\w\s-]", "", s.lower()).strip()
    return re.sub(r"[\s_]+", "-", s)


def extract_title(h):
    m = re.search(r"<title>(.*?)</title>", h, re.I | re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    m = re.search(r"<h1[^>]*>(.*?)</h1>", h, re.I | re.S)
    if m:
        return re.sub(r"<[^>]+>", "", m.group(1)).strip()
    return "Untitled"


def extract_desc(h):
    m = re.search(r'<meta[^>]+name=["\']description["\'][^>]*content=["\'](.*?)["\']', h, re.I | re.S)
    if m:
        return re.sub(r"\s+", " ", m.group(1)).strip()
    return ""


def inject_noindex(h):
    if re.search(r'name=["\']robots["\']', h, re.I):
        return h
    tag = '\n<meta name="robots" content="noindex, nofollow">'
    m = re.search(r"<head[^>]*>", h, re.I)
    if m:
        return h[:m.end()] + tag + h[m.end():]
    return tag + h


def fmt_date(iso):
    try:
        y, m, d = iso.split("-")
        months = ["", "Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
        return f"{months[int(m)]} {int(d)}, {y}"
    except Exception:
        return iso


def card(it):
    return (
        f'  <a class="card" href="./{html.escape(it["slug"])}/">\n'
        f'    <span class="date">{html.escape(fmt_date(it["date"]))}</span>\n'
        f'    <span class="title">{html.escape(it["title"])}</span>\n'
        f'    <span class="desc">{html.escape(it.get("desc", ""))}</span>\n'
        f'    <span class="go">Open &rarr;</span>\n'
        f'  </a>'
    )


def render_index(*_):
    items = load_manifest()
    cards = "\n".join(card(it) for it in items) or '<p class="empty">Nothing here yet.</p>'
    out = (INDEX_TMPL
           .replace("{{TITLE}}", html.escape(SITE_TITLE))
           .replace("{{TAGLINE}}", html.escape(SITE_TAGLINE))
           .replace("{{CARDS}}", cards)
           .replace("{{COUNT}}", str(len(items))))
    with open(os.path.join(REPO, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)
    print("Rebuilt index.html (%d page%s)" % (len(items), "" if len(items) == 1 else "s"))


def add(args):
    src = os.path.abspath(args.src)
    h = read(src)
    title = args.title or extract_title(h)
    desc = args.desc or extract_desc(h)
    slug = args.slug or slugify(title)
    items = load_manifest()
    existing = next((it for it in items if it["slug"] == slug), None)
    d = args.date or (existing["date"] if existing else date.today().isoformat())
    dest_dir = os.path.join(REPO, slug)
    os.makedirs(dest_dir, exist_ok=True)
    with open(os.path.join(dest_dir, "index.html"), "w", encoding="utf-8") as f:
        f.write(inject_noindex(h))
    items = [it for it in items if it["slug"] != slug]
    items.append({"slug": slug, "title": title, "desc": desc, "date": d})
    items.sort(key=lambda it: (it["date"], it["title"]), reverse=True)
    save_manifest(items)
    render_index()
    verb = "Updated" if existing else "Published"
    print(f"{verb}: {title}")
    print(f"  {CUSTOM_URL}/{slug}/")
    print(f"  {PAGES_URL}/{slug}/")
    if args.push:
        git_publish(f"{verb.lower()}: {slug}")


def remove(args):
    items = [it for it in load_manifest() if it["slug"] != args.slug]
    save_manifest(items)
    d = os.path.join(REPO, args.slug)
    if os.path.isdir(d):
        shutil.rmtree(d)
    render_index()
    print(f"Removed: {args.slug}")
    if args.push:
        git_publish(f"unpublish: {args.slug}")


def git_publish(msg):
    subprocess.run(["git", "-C", REPO, "add", "-A"], check=True)
    subprocess.run(["git", "-C", REPO, "commit", "-q", "-m", msg])
    subprocess.run(["git", "-C", REPO, "push", "origin", "main"], check=True)
    print("Pushed → live in ~60s")


INDEX_TMPL = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{TITLE}}</title>
<meta name="robots" content="noindex, nofollow">
<meta name="description" content="{{TAGLINE}}">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Young+Serif&family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root{--bg:#f8f2ea;--surface:#fff;--ink:#303636;--ink-soft:#6f6a63;--ink-faint:#9a948c;--clay:#d4967d;--clay-deep:#b06a4f;--line:rgba(48,54,54,.10);--shadow:0 14px 40px rgba(80,50,30,.07);--shadow-sm:0 6px 18px rgba(80,50,30,.06)}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:'Poppins',system-ui,-apple-system,sans-serif;font-size:17px;line-height:1.7;-webkit-font-smoothing:antialiased}
  h1{font-family:'Young Serif',Georgia,serif;font-weight:400;letter-spacing:-.01em;margin:0}
  a{color:inherit}
  .wrap{max-width:900px;margin:0 auto;padding:0 26px}
  header{padding:84px 0 26px;text-align:center;position:relative;overflow:hidden}
  header::before{content:"";position:absolute;top:-220px;left:50%;transform:translateX(-50%);width:760px;height:480px;border-radius:50%;background:radial-gradient(closest-side,rgba(212,150,125,.28),rgba(212,150,125,0));z-index:0}
  header .wrap{position:relative;z-index:1}
  .kicker{display:inline-block;font-size:12.5px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--clay-deep);margin-bottom:16px}
  header h1{font-size:clamp(40px,6vw,62px)}
  .tagline{color:var(--ink-soft);font-size:19px;max-width:560px;margin:14px auto 0}
  main{padding:26px 0 70px}
  .grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:18px}
  .card{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--line);border-radius:18px;padding:26px 24px;box-shadow:var(--shadow-sm);text-decoration:none;color:inherit;transition:.2s}
  .card:hover{transform:translateY(-3px);box-shadow:var(--shadow);border-color:rgba(212,150,125,.4)}
  .card .date{font-size:12.5px;font-weight:600;letter-spacing:.04em;text-transform:uppercase;color:var(--clay-deep);margin-bottom:10px}
  .card .title{font-family:'Young Serif',serif;font-size:21px;line-height:1.2;color:#2b2622;margin-bottom:8px}
  .card .desc{font-size:14.5px;color:var(--ink-soft);line-height:1.55;flex:1}
  .card .go{margin-top:16px;font-size:14px;font-weight:600;color:var(--clay-deep)}
  .empty{color:var(--ink-faint);text-align:center;padding:50px 0;grid-column:1/-1}
  footer{border-top:1px solid var(--line);padding:28px 0;text-align:center;color:var(--ink-faint);font-size:14px}
  @media(max-width:600px){header{padding:54px 0 18px}}
</style>
</head>
<body>
<header>
  <div class="wrap">
    <span class="kicker">&#10022; share.axelmansoor.com</span>
    <h1>{{TITLE}}</h1>
    <p class="tagline">{{TAGLINE}}</p>
  </div>
</header>
<main class="wrap">
  <div class="grid">
{{CARDS}}
  </div>
</main>
<footer><div class="wrap">{{COUNT}} pages &middot; made with love &#10084;&#65039;</div></footer>
</body>
</html>
'''


def main():
    p = argparse.ArgumentParser(description="Publish HTML to share.axelmansoor.com")
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("add", help="publish or update a page")
    pa.add_argument("--src", required=True)
    pa.add_argument("--slug")
    pa.add_argument("--title")
    pa.add_argument("--desc")
    pa.add_argument("--date")
    pa.add_argument("--push", action="store_true")
    pa.set_defaults(func=add)
    pr = sub.add_parser("rebuild", help="regenerate index.html from manifest.json")
    pr.set_defaults(func=render_index)
    prm = sub.add_parser("remove", help="unpublish a page")
    prm.add_argument("--slug", required=True)
    prm.add_argument("--push", action="store_true")
    prm.set_defaults(func=remove)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
