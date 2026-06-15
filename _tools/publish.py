#!/usr/bin/env python3
"""Publish documents to the public share site (share.axelmansoor.com).

  python3 publish.py add --src PATH [--slug S] [--title T] [--desc D] \
      [--listed] [--unlisted] [--date YYYY-MM-DD] [--dry-run] [--push]
  python3 publish.py rebuild                 # regenerate index.html + control panel
  python3 publish.py panel                   # regenerate just the local control panel
  python3 publish.py remove --slug SLUG [--push]

HTML files become a styled page at /<slug>/. Any other file (PDF, image, etc.)
is hosted at /<slug>/<filename> and linked. Pages/files are "unlisted" by
default (work by link, but don't appear on the directory index) unless --listed.

The repo root is inferred from this script's location (_tools/.. == repo root).
"""
import argparse, json, os, re, shutil, subprocess, html
from datetime import date

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE_TITLE = "Axel Mansoor"
SITE_TAGLINE = "Things I've made and shared — guides, notes, and the occasional rabbit hole."
CUSTOM_URL = "https://share.axelmansoor.com"
CONTROL_PANEL_PATH = os.path.expanduser("~/Secondbrain/share-control-panel.html")


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


def is_html(path):
    return os.path.splitext(path)[1].lower() in (".html", ".htm")


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


def entry_url(it):
    if it.get("type") == "file" and it.get("file"):
        return f"{CUSTOM_URL}/{it['slug']}/{it['file']}"
    return f"{CUSTOM_URL}/{it['slug']}/"


def entry_href(it):
    if it.get("type") == "file" and it.get("file"):
        return f"./{it['slug']}/{it['file']}"
    return f"./{it['slug']}/"


def card(it):
    go = "Download &rarr;" if it.get("type") == "file" else "Open &rarr;"
    return (
        f'  <a class="card" href="{html.escape(entry_href(it))}">\n'
        f'    <span class="date">{html.escape(fmt_date(it["date"]))}</span>\n'
        f'    <span class="title">{html.escape(it["title"])}</span>\n'
        f'    <span class="desc">{html.escape(it.get("desc", ""))}</span>\n'
        f'    <span class="go">{go}</span>\n'
        f'  </a>'
    )


def render_index(*_):
    listed = [it for it in load_manifest() if it.get("listed")]
    cards = "\n".join(card(it) for it in listed) or '<p class="empty">Nothing here yet.</p>'
    out = (INDEX_TMPL
           .replace("{{TITLE}}", html.escape(SITE_TITLE))
           .replace("{{TAGLINE}}", html.escape(SITE_TAGLINE))
           .replace("{{CARDS}}", cards)
           .replace("{{COUNT}}", str(len(listed))))
    with open(os.path.join(REPO, "index.html"), "w", encoding="utf-8") as f:
        f.write(out)
    print("Rebuilt index.html (%d listed)" % len(listed))
    render_control_panel()


def panel_row(it):
    url = entry_url(it)
    badge = '<span class="badge yes">listed</span>' if it.get("listed") else '<span class="badge no">unlisted</span>'
    kind = "file" if it.get("type") == "file" else "page"
    return (
        f'    <tr>\n'
        f'      <td class="t"><span class="ti">{html.escape(it["title"])}</span>'
        f'<span class="meta">{html.escape(fmt_date(it["date"]))} &middot; {kind}</span></td>\n'
        f'      <td>{badge}</td>\n'
        f'      <td class="u"><a href="{html.escape(url)}" target="_blank" rel="noopener">{html.escape(url)}</a></td>\n'
        f'      <td><button class="copy" data-url="{html.escape(url)}">Copy</button></td>\n'
        f'    </tr>'
    )


def render_control_panel(*_):
    try:
        items = load_manifest()
        rows = "\n".join(panel_row(it) for it in items) or '    <tr><td colspan="4" class="empty">Nothing shared yet.</td></tr>'
        listed_n = sum(1 for it in items if it.get("listed"))
        out = (CONTROL_PANEL_TMPL
               .replace("{{ROWS}}", rows)
               .replace("{{TOTAL}}", str(len(items)))
               .replace("{{LISTED}}", str(listed_n))
               .replace("{{UNLISTED}}", str(len(items) - listed_n))
               .replace("{{GENERATED}}", date.today().isoformat()))
        d = os.path.dirname(CONTROL_PANEL_PATH)
        if os.path.isdir(d):
            with open(CONTROL_PANEL_PATH, "w", encoding="utf-8") as f:
                f.write(out)
            print(f"Updated control panel → {CONTROL_PANEL_PATH}")
        else:
            print("(control panel skipped — Secondbrain dir not found)")
    except Exception as e:
        print(f"(control panel skipped: {e})")


def resolve_listed(args, existing):
    if args.unlisted:
        return False
    if args.listed:
        return True
    if existing is not None:
        return bool(existing.get("listed", False))
    return False


def add(args):
    src = os.path.abspath(args.src)
    if not os.path.exists(src):
        raise SystemExit(f"ERROR: file not found: {src}")
    items = load_manifest()
    page = is_html(src)
    if page:
        h = read(src)
        title = args.title or extract_title(h)
        desc = args.desc or extract_desc(h)
        slug = args.slug or slugify(title)
        fname = None
    else:
        fname = os.path.basename(src)
        stem = os.path.splitext(fname)[0]
        title = args.title or stem.replace("-", " ").replace("_", " ").strip().title()
        desc = args.desc or ""
        slug = args.slug or slugify(stem)
    existing = next((it for it in items if it["slug"] == slug), None)
    d = args.date or (existing["date"] if existing else date.today().isoformat())
    listed = resolve_listed(args, existing)
    if page:
        entry = {"slug": slug, "title": title, "desc": desc, "date": d, "listed": listed, "type": "page"}
    else:
        entry = {"slug": slug, "title": title, "desc": desc, "date": d, "listed": listed, "type": "file", "file": fname}
    url = entry_url(entry)

    if args.dry_run:
        print("DRY RUN — nothing published.")
        print(f"  action : {'update existing' if existing else 'new'} ({'page' if page else 'file'})")
        print(f"  title  : {title}")
        print(f"  slug   : {slug}")
        print(f"  listed : {'yes — shows on the directory' if listed else 'no — link-only'}")
        print(f"  url    : {url}")
        return

    dest_dir = os.path.join(REPO, slug)
    os.makedirs(dest_dir, exist_ok=True)
    if page:
        with open(os.path.join(dest_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(inject_noindex(h))
    else:
        shutil.copyfile(src, os.path.join(dest_dir, fname))
    items = [it for it in items if it["slug"] != slug]
    items.append(entry)
    items.sort(key=lambda it: (it["date"], it["title"]), reverse=True)
    save_manifest(items)
    render_index()
    verb = "Updated" if existing else "Published"
    print(f"{verb}: {title}")
    print(f"  {url}")
    print(f"  listed: {'yes' if listed else 'no (link-only)'}")
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
<footer><div class="wrap">{{COUNT}} shared &middot; made with love &#10084;&#65039;</div></footer>
</body>
</html>
'''


CONTROL_PANEL_TMPL = r'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Share &middot; Control Panel</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Young+Serif&family=Poppins:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
  :root{--bg:#f8f2ea;--surface:#fff;--ink:#303636;--ink-soft:#6f6a63;--ink-faint:#9a948c;--clay:#d4967d;--clay-deep:#b06a4f;--line:rgba(48,54,54,.10);--shadow-sm:0 6px 18px rgba(80,50,30,.06)}
  *{box-sizing:border-box}
  body{margin:0;background:var(--bg);color:var(--ink);font-family:'Poppins',system-ui,-apple-system,sans-serif;font-size:16px;line-height:1.6;-webkit-font-smoothing:antialiased}
  h1{font-family:'Young Serif',Georgia,serif;font-weight:400;letter-spacing:-.01em;margin:0;font-size:clamp(30px,5vw,44px)}
  a{color:var(--clay-deep)}
  .wrap{max-width:1000px;margin:0 auto;padding:46px 26px 80px}
  .kicker{display:inline-block;font-size:12px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--clay-deep);margin-bottom:12px}
  .sub{color:var(--ink-soft);margin:10px 0 0}
  .stats{display:flex;gap:10px;margin:26px 0 18px;flex-wrap:wrap}
  .stat{background:var(--surface);border:1px solid var(--line);border-radius:14px;padding:13px 20px;box-shadow:var(--shadow-sm)}
  .stat .n{font-family:'Young Serif',serif;font-size:26px;color:#2b2622}
  .stat .l{font-size:12px;color:var(--ink-faint);text-transform:uppercase;letter-spacing:.05em}
  table{width:100%;border-collapse:collapse;background:var(--surface);border:1px solid var(--line);border-radius:16px;overflow:hidden;box-shadow:var(--shadow-sm)}
  th{text-align:left;font-size:11.5px;text-transform:uppercase;letter-spacing:.06em;color:var(--ink-faint);padding:14px 16px;border-bottom:1px solid var(--line);font-weight:600}
  td{padding:14px 16px;border-bottom:1px solid var(--line);vertical-align:middle}
  tr:last-child td{border-bottom:none}
  td.t .ti{font-family:'Young Serif',serif;font-size:16.5px;color:#2b2622;display:block}
  td.t .meta{font-size:12.5px;color:var(--ink-faint)}
  td.u a{font-size:13.5px;word-break:break-all}
  .badge{display:inline-block;font-size:11px;font-weight:600;padding:4px 11px;border-radius:999px;text-transform:uppercase;letter-spacing:.04em;white-space:nowrap}
  .badge.yes{background:#e7ece4;color:#5b6b58}
  .badge.no{background:#efe9e2;color:#8a8175}
  .copy{cursor:pointer;border:1px solid var(--line);background:var(--bg);color:var(--ink);font-family:'Poppins',sans-serif;font-size:12.5px;font-weight:600;padding:7px 14px;border-radius:999px;transition:.15s}
  .copy:hover{border-color:var(--clay);color:var(--clay-deep)}
  .empty{text-align:center;color:var(--ink-faint);padding:36px 0}
  .note{margin-top:22px;background:var(--surface);border:1px dashed var(--line);border-radius:14px;padding:18px 20px;color:var(--ink-soft);font-size:14px}
  .note b{color:#2b2622}
  .foot{margin-top:24px;color:var(--ink-faint);font-size:12.5px}
  .toast{position:fixed;bottom:26px;left:50%;transform:translateX(-50%) translateY(20px);background:#221d1a;color:#fff;padding:11px 20px;border-radius:999px;font-size:14px;opacity:0;pointer-events:none;transition:.25s;box-shadow:0 10px 30px rgba(0,0,0,.25)}
  .toast.show{opacity:1;transform:translateX(-50%) translateY(0)}
</style>
</head>
<body>
<div class="wrap">
  <span class="kicker">&#10022; private &middot; your eyes only</span>
  <h1>Share &middot; Control Panel</h1>
  <p class="sub">Every link you've published to <a href="https://share.axelmansoor.com" target="_blank" rel="noopener">share.axelmansoor.com</a> — listed and unlisted. Regenerates each time you /share.</p>
  <div class="stats">
    <div class="stat"><div class="n">{{TOTAL}}</div><div class="l">total</div></div>
    <div class="stat"><div class="n">{{LISTED}}</div><div class="l">listed</div></div>
    <div class="stat"><div class="n">{{UNLISTED}}</div><div class="l">unlisted</div></div>
  </div>
  <table>
    <thead><tr><th>Title</th><th>Status</th><th>Link</th><th></th></tr></thead>
    <tbody>
{{ROWS}}
    </tbody>
  </table>
  <div class="note"><b>Private client files</b> will get their own section here once truly-private hosting is set up (separate from this public site).</div>
  <p class="foot">Generated {{GENERATED}} &middot; lives in your Secondbrain (local only) &middot; double-click this file to open it anytime.</p>
</div>
<div class="toast" id="toast">Copied &#10003;</div>
<script>
  var toast=document.getElementById('toast'),tt;
  function showToast(m){toast.textContent=m;toast.classList.add('show');clearTimeout(tt);tt=setTimeout(function(){toast.classList.remove('show');},1500);}
  document.querySelectorAll('.copy').forEach(function(b){
    b.addEventListener('click',function(){
      var u=b.getAttribute('data-url');
      navigator.clipboard.writeText(u).then(function(){showToast('Copied ✓');},function(){
        var ta=document.createElement('textarea');ta.value=u;document.body.appendChild(ta);ta.select();
        try{document.execCommand('copy');showToast('Copied ✓');}catch(e){showToast('Copy failed');}
        document.body.removeChild(ta);
      });
    });
  });
</script>
</body>
</html>
'''


def main():
    p = argparse.ArgumentParser(description="Publish documents to share.axelmansoor.com")
    sub = p.add_subparsers(dest="cmd", required=True)
    pa = sub.add_parser("add", help="publish or update a document")
    pa.add_argument("--src", required=True)
    pa.add_argument("--slug")
    pa.add_argument("--title")
    pa.add_argument("--desc")
    pa.add_argument("--date")
    pa.add_argument("--listed", action="store_true", help="show on the public directory index")
    pa.add_argument("--unlisted", action="store_true", help="link-only, hide from the index (default)")
    pa.add_argument("--dry-run", action="store_true", help="print what would happen without publishing")
    pa.add_argument("--push", action="store_true")
    pa.set_defaults(func=add)
    pr = sub.add_parser("rebuild", help="regenerate index.html + control panel")
    pr.set_defaults(func=render_index)
    pp = sub.add_parser("panel", help="regenerate the local control panel")
    pp.set_defaults(func=render_control_panel)
    prm = sub.add_parser("remove", help="unpublish a document")
    prm.add_argument("--slug", required=True)
    prm.add_argument("--push", action="store_true")
    prm.set_defaults(func=remove)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
