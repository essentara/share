# share

The public site behind **share.axelmansoor.com** — a small directory of pages Axel makes and shares.

- `index.html` — auto-generated directory (the "database"), built from `manifest.json`.
- `<slug>/index.html` — each published page.
- `_tools/publish.py` — the publisher: copies a page in, updates the manifest, rebuilds the index, pushes.
- `robots.txt` + per-page `noindex` — pages are shareable by link but not search-indexed.

This repo is **public** and intentionally separate from the private Secondbrain. Nothing private goes here.

## Publish a page

```sh
python3 _tools/publish.py add --src /path/to/page.html --slug my-page \
  --title "Title" --desc "One line." --push
```

Omit `--title` / `--desc` to auto-extract from the page's `<title>` and `<meta name="description">`.

- Rebuild just the index: `python3 _tools/publish.py rebuild`
- Remove a page: `python3 _tools/publish.py remove --slug my-page --push`
