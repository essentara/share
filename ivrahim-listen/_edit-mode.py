#!/usr/bin/env python3
"""Turn inline copy-editing on or off for index.html.

    python3 _edit-mode.py on     # tag every copy block, inject the editor
    python3 _edit-mode.py off    # strip every trace of it

The storage key auto-versions on each `on`, because element ids get renumbered
whenever a block is added or deleted. A stale key silently restores old copy
into the wrong elements, which is the one failure mode worth engineering against.
"""
import re, sys, pathlib

HTML = pathlib.Path(__file__).with_name("index.html")

TARGETS = [r'<div class="tagline">', r'<div class="eyebrow">', r'<h2>', r'<p class="lede">',
           r'<p class="drawer-intro">', r'<summary>', r'<div class="pull">',
           r'<span class="t-name">', r'<span class="t-sub">', r'<span class="t-time">',
           r'<span class="n">', r'<span class="d">', r'<div class="a">', r'<div class="b">',
           r'<h3>', r'<a class="cta"[^>]*>', r'<a class="cta ghost"[^>]*>']

CSS = """
  /* ---- edit mode (?edit=1 only) ---- */
  body.editing [data-e]{outline:1px dashed rgba(140,98,57,.38);outline-offset:3px;border-radius:2px;}
  body.editing [data-e]:hover{outline-color:var(--bronze);background:rgba(140,98,57,.05);}
  body.editing [data-e]:focus{outline:2px solid var(--bronze);background:rgba(140,98,57,.08);}
  body.editing .tri-dot{position:static;width:auto;height:auto;border:0;background:none;display:block;margin:0 0 10px;pointer-events:auto;}
  body.editing .tri-dot::before{display:none;}
  body.editing .tri-tip{opacity:1 !important;position:static;transform:none;width:auto;pointer-events:auto;}
  #editbar{position:fixed;left:20px;bottom:20px;z-index:9999;background:var(--char);color:var(--bone);
    padding:14px 18px;border-radius:4px;font-family:var(--text);font-size:12.5px;letter-spacing:.06em;
    display:flex;align-items:center;gap:16px;box-shadow:0 6px 30px rgba(0,0,0,.3);}
  #editbar b{color:var(--peach);font-weight:400;letter-spacing:.16em;text-transform:uppercase;font-size:11px;}
  #editbar .count{color:rgba(244,239,230,.62);}
  #editbar button{font-family:var(--text);font-size:11px;letter-spacing:.14em;text-transform:uppercase;
    background:var(--peach);color:var(--char);border:0;padding:8px 14px;border-radius:3px;cursor:pointer;}
  #editbar button.ghost{background:none;color:rgba(244,239,230,.7);box-shadow:inset 0 0 0 1px rgba(232,192,164,.4);}
"""

JS = """
<script>
(function(){
  if (!/[?&]edit=1/.test(location.search)) return;
  var KEY = "__KEY__";
  var saved = {}; try { saved = JSON.parse(localStorage.getItem(KEY) || "{}"); } catch(e){}
  var els = [].slice.call(document.querySelectorAll("[data-e]"));
  els.forEach(function(el){
    var id = el.getAttribute("data-e");
    if (saved[id] != null) el.innerHTML = saved[id];
    el.setAttribute("contenteditable","true");
    el.setAttribute("spellcheck","true");
  });
  els.forEach(function(el){ el.dataset.orig = el.innerHTML; });
  document.body.classList.add("editing");
  document.addEventListener("click", function(e){
    var a = e.target.closest("a[data-e], .track, .tri-dot");
    if (a) { e.preventDefault(); e.stopPropagation(); }
  }, true);
  var bar = document.createElement("div");
  bar.id = "editbar";
  bar.innerHTML = '<b>Edit mode</b><span class="count">0 changed</span>' +
    '<button id="ed-done">Done</button><button class="ghost" id="ed-reset">Reset</button>';
  document.body.appendChild(bar);
  var countEl = bar.querySelector(".count");
  function changed(){ return els.filter(function(el){ return el.innerHTML !== el.dataset.orig; }); }
  function persist(){
    var out = {};
    els.forEach(function(el){ out[el.getAttribute("data-e")] = el.innerHTML; });
    localStorage.setItem(KEY, JSON.stringify(out));
    countEl.textContent = changed().length + " changed";
  }
  document.addEventListener("input", function(e){
    if (e.target.hasAttribute && e.target.hasAttribute("data-e")) persist();
  });
  document.addEventListener("paste", function(e){
    if (!e.target.hasAttribute || !e.target.hasAttribute("data-e")) return;
    e.preventDefault();
    document.execCommand("insertText", false, (e.clipboardData || window.clipboardData).getData("text"));
  });
  bar.querySelector("#ed-done").addEventListener("click", function(){
    persist();
    var b = bar.querySelector("#ed-done");
    b.textContent = "Saved locally";
    setTimeout(function(){ b.textContent = "Done"; }, 1600);
  });
  bar.querySelector("#ed-reset").addEventListener("click", function(){
    localStorage.removeItem(KEY); location.reload();
  });
  countEl.textContent = "0 changed";
})();
</script>
"""


def off(t):
    t = re.sub(r'\s*data-e="\d+"', '', t)
    t = re.sub(r'\n\s*/\* ---- edit mode.*?#editbar button\.ghost\{[^}]*\}\n', '\n', t, flags=re.S)
    t = re.sub(r'\n<script>\n\(function\(\)\{\n  if \(!/\[\?&\]edit=1/.*?\n</script>\n', '\n', t, flags=re.S)
    return t


def on(t):
    t = off(t)                      # always start clean
    # the version must survive `off`, which deletes the key from the HTML,
    # so it lives in a sidecar rather than being derived from the file
    stamp = HTML.with_name(".edit-version")
    version = (int(stamp.read_text().strip()) if stamp.exists() else 1) + 1
    stamp.write_text(str(version))
    n = [0]

    def tag(m):
        n[0] += 1
        return m.group(0)[:-1] + ' data-e="%d">' % n[0]

    for pat in TARGETS:
        t = re.sub(pat, tag, t)

    def tagp(m):
        n[0] += 1
        return '<p data-e="%d">' % n[0]

    t = re.sub(r'<p>', tagp, t)
    t = t.replace("</style>", CSS + "</style>")
    t = t.replace("</body>", JS.replace("__KEY__", "ivrahim-edits-v%d" % version) + "</body>")
    return t, n[0], version


if __name__ == "__main__":
    mode = sys.argv[1] if len(sys.argv) > 1 else "on"
    src = HTML.read_text()
    if mode == "off":
        HTML.write_text(off(src))
        print("edit mode OFF")
    else:
        out, count, ver = on(src)
        HTML.write_text(out)
        print("edit mode ON — %d blocks, storage key ivrahim-edits-v%d" % (count, ver))
