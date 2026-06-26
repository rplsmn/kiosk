#!/usr/bin/env python3
"""Assemble toutes les pièces en un seul site statique (kiosk.raphaelsimon.fr).

Chaque sous-dossier contenant un fichier `gadget.json` est une pièce :
  - clé "build" : la commande est exécutée DANS le dossier de la pièce, puis le
    dossier "output" (défaut "dist") est copié vers dist/<slug>/
  - sinon (pièce statique) : le dossier est copié tel quel vers dist/<slug>/

Le HTML partagé vit dans core/ (facile à éditer, séparé du code) :
  - core/index.html : la page d'accueil (placeholders __CARDS__ / __GENERATED__
    / __BASEURL__ pour les balises Open Graph)
  - core/nav.html   : la mini-navbar injectée automatiquement en haut de
    chaque page de chaque pièce (placeholder __ROOT__ = chemin vers la racine).
    Une pièce peut s'en passer avec "nav": false dans son gadget.json.

Par pièce, le moteur injecte aussi dans le <head> de la page d'entrée :
  <title>, meta description et balises Open Graph / Twitter, depuis gadget.json.
  Champ optionnel "image" (relatif à la pièce, ou URL) pour la vignette de
  partage ; sinon repli sur og-default.png à la racine si présent. L'og:url
  absolue est dérivée du fichier CNAME.

Aucune dépendance externe : stdlib uniquement.
Ajouter une pièce = déposer un dossier + un gadget.json + push.
"""
import html
import json
import re
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CORE = ROOT / "core"
DIST = ROOT / "dist"
SITE_NAME = "Kiosk"

BODY_RE = re.compile(r"(<body[^>]*>)", re.IGNORECASE)
HEAD_CLOSE_RE = re.compile(r"</head>", re.IGNORECASE)
TITLE_RE = re.compile(r"<title>.*?</title>", re.IGNORECASE | re.DOTALL)


def site_base_url():
    """https://<domaine> dérivé du fichier CNAME (sinon "" -> URLs relatives)."""
    cname = ROOT / "CNAME"
    if cname.exists():
        host = cname.read_text(encoding="utf-8").strip()
        if host:
            return f"https://{host}"
    return ""


def discover():
    gadgets = []
    for manifest in sorted(ROOT.glob("*/gadget.json")):
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        meta["slug"] = manifest.parent.name
        meta["dir"] = manifest.parent
        gadgets.append(meta)
    return gadgets


def build_gadget(g, base_url, default_image):
    out = DIST / g["slug"]
    if g.get("build"):
        print(f"  build  {g['slug']}: {g['build']}")
        subprocess.run(g["build"], cwd=g["dir"], shell=True, check=True)
        src = g["dir"] / g.get("output", "dist")
        if not src.is_dir():
            raise SystemExit(f"{g['slug']} : sortie '{src}' introuvable après le build")
        shutil.copytree(src, out, dirs_exist_ok=True)
    else:
        print(f"  static {g['slug']}")
        shutil.copytree(
            g["dir"],
            out,
            dirs_exist_ok=True,
            ignore=shutil.ignore_patterns("gadget.json", "__pycache__", ".git", "dist"),
        )
    inject_meta(out, g, base_url, default_image)
    if g.get("nav", True):
        inject_nav(out)


def inject_nav(gadget_dist):
    """Insère la navbar partagée juste après <body> dans chaque .html de la pièce."""
    nav_tmpl = (CORE / "nav.html").read_text(encoding="utf-8")
    for htmlfile in gadget_dist.rglob("*.html"):
        text = htmlfile.read_text(encoding="utf-8")
        if "g-nav" in text:  # déjà injectée
            continue
        depth = len(htmlfile.relative_to(DIST).parts) - 1  # /<slug>/index.html -> 1
        root = "../" * depth or "./"
        nav = nav_tmpl.replace("__ROOT__", root)
        new_text, n = BODY_RE.subn(lambda m: m.group(1) + "\n" + nav, text, count=1)
        if n:
            htmlfile.write_text(new_text, encoding="utf-8")


def meta_tags(title, desc, url, image):
    """Bloc <meta> Open Graph / Twitter (valeurs échappées)."""
    t = html.escape(title)
    d = html.escape(desc)
    tags = [
        f'<meta name="description" content="{d}">',
        '<meta property="og:type" content="article">',
        f'<meta property="og:site_name" content="{html.escape(SITE_NAME)}">',
        f'<meta property="og:title" content="{t}">',
        f'<meta property="og:description" content="{d}">',
    ]
    if url:
        tags.append(f'<meta property="og:url" content="{html.escape(url)}">')
    tags.append(
        '<meta name="twitter:card" content="%s">'
        % ("summary_large_image" if image else "summary")
    )
    tags.append(f'<meta name="twitter:title" content="{t}">')
    tags.append(f'<meta name="twitter:description" content="{d}">')
    if image:
        i = html.escape(image)
        tags.append(f'<meta property="og:image" content="{i}">')
        tags.append(f'<meta name="twitter:image" content="{i}">')
    return "".join("  " + tag + "\n" for tag in tags)


def inject_meta(gadget_dist, g, base_url, default_image):
    """Injecte <title> + meta description + Open Graph dans la page d'entrée.

    Cible index.html (sinon le premier .html à la racine de la pièce). N'agit que
    sur le PREMIER <title>/</head> (une page reveal.js en embarque un second dans
    le markup de la « Speaker View »). Respecte une pièce qui apporte ses balises.
    """
    target = gadget_dist / "index.html"
    if not target.is_file():
        htmls = sorted(gadget_dist.glob("*.html"))
        if not htmls:
            return
        target = htmls[0]
    text = target.read_text(encoding="utf-8")
    if "og:title" in text:
        return
    title = g.get("title", g["slug"])
    desc = g.get("description", "")
    url = f"{base_url}/{g['slug']}/" if base_url else f"{g['slug']}/"
    image = g.get("image")
    if image and "://" not in image:
        rel = image.lstrip("/")
        image = f"{base_url}/{g['slug']}/{rel}" if base_url else f"{g['slug']}/{rel}"
    if not image:
        image = default_image
    block = meta_tags(title, desc, url, image)
    if TITLE_RE.search(text):
        text = TITLE_RE.sub(lambda m: f"<title>{html.escape(title)}</title>", text, count=1)
    else:
        block = f"  <title>{html.escape(title)}</title>\n" + block
    text, n = HEAD_CLOSE_RE.subn(lambda m: block + m.group(0), text, count=1)
    if n:
        target.write_text(text, encoding="utf-8")


def build_index(gadgets, base_url):
    cards = []
    for g in sorted(gadgets, key=lambda x: x.get("title", x["slug"]).lower()):
        title = html.escape(g.get("title", g["slug"]))
        desc = html.escape(g.get("description", ""))
        cards.append(
            f'      <li><a class="card" href="{g["slug"]}/">\n'
            f"        <h2>{title}</h2>\n"
            f"        <p>{desc}</p>\n"
            f'        <span class="arrow">Ouvrir &rarr;</span>\n'
            f"      </a></li>"
        )
    generated = datetime.now(timezone.utc).strftime("%d/%m/%Y à %H:%M UTC")
    tmpl = (CORE / "index.html").read_text(encoding="utf-8")
    page = (
        tmpl.replace("__CARDS__", "\n".join(cards))
        .replace("__GENERATED__", generated)
        .replace("__BASEURL__", base_url)
    )
    (DIST / "index.html").write_text(page, encoding="utf-8")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    base_url = site_base_url()
    default_image = ""
    if base_url and (ROOT / "og-default.png").is_file():
        default_image = f"{base_url}/og-default.png"
    gadgets = discover()
    if not gadgets:
        print("⚠️  aucune pièce trouvée (cherche */gadget.json).")
    for g in gadgets:
        build_gadget(g, base_url, default_image)
    build_index(gadgets, base_url)
    # Assets racine déployés tels quels (domaine custom + vignette sociale).
    for asset in ("CNAME", "og-default.png"):
        src = ROOT / asset
        if src.exists():
            shutil.copy(src, DIST / asset)
    print(f"✅ {len(gadgets)} pièce(s) assemblée(s) -> {DIST}")


if __name__ == "__main__":
    main()
