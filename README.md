# kiosk

Talks, decks, reports and other published pieces, assembled into one static site:
**[kiosk.raphaelsimon.fr](https://kiosk.raphaelsimon.fr/)**.

Same engine as [`gadgets`](https://github.com/rplsmn/gadgets): each subfolder that
contains a `gadget.json` becomes one card on the landing page.

## Add a piece

Drop a folder + a `gadget.json` + push to `main`. That's it.

```
mon-talk/
  gadget.json      # { "title": "...", "description": "...", "static": true }
  index.html       # the deck / report / poster / embed
```

- **`static: true`** (default use): the folder is copied as-is to `dist/<slug>/`.
- **Build step**: add `"build": "<cmd>"` and the engine runs it in the folder, then
  copies the `output` dir (default `dist`).
- A shared navbar (back to Kiosk + raphaelsimon.fr) is injected at the top of every
  `.html`. Opt out per piece with `"nav": false` (useful for full-screen reveal.js
  decks where the bar would overlap content).

Mixed media works for free: a "recorded talk" or "podcast" piece is just an
`index.html` with an `<iframe>` / `<audio>` inside.

## Build locally

```sh
python3 build_site.py      # stdlib only, no deps -> ./dist/
```

Deploy is automatic: pushing to `main` runs `.github/workflows/deploy.yml`
(GitHub Pages).
