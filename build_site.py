#!/usr/bin/env python3
"""Assemble tous les gadgets en un seul site statique (gadgets.raphaelsimon.fr).

Chaque sous-dossier contenant un fichier `gadget.json` est un gadget :
  - clé "build" : la commande est exécutée DANS le dossier du gadget, puis le
    dossier "output" (défaut "dist") est copié vers dist/<slug>/
  - sinon (gadget statique) : le dossier est copié tel quel vers dist/<slug>/

Le HTML partagé vit dans core/ (facile à éditer, séparé du code) :
  - core/index.html : la page d'accueil (placeholders __CARDS__ / __GENERATED__)
  - core/nav.html   : la mini-navbar injectée automatiquement en haut de
    chaque page de chaque gadget (placeholder __ROOT__ = chemin vers la racine).
    Un gadget peut s'en passer avec "nav": false dans son gadget.json.

Aucune dépendance externe : stdlib uniquement.
Ajouter un gadget = déposer un dossier + un gadget.json + push.
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

BODY_RE = re.compile(r"(<body[^>]*>)", re.IGNORECASE)


def discover():
    gadgets = []
    for manifest in sorted(ROOT.glob("*/gadget.json")):
        meta = json.loads(manifest.read_text(encoding="utf-8"))
        meta["slug"] = manifest.parent.name
        meta["dir"] = manifest.parent
        gadgets.append(meta)
    return gadgets


def build_gadget(g):
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
    if g.get("nav", True):
        inject_nav(out)


def inject_nav(gadget_dist):
    """Insère la navbar partagée juste après <body> dans chaque .html du gadget."""
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


def build_index(gadgets):
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
    page = tmpl.replace("__CARDS__", "\n".join(cards)).replace("__GENERATED__", generated)
    (DIST / "index.html").write_text(page, encoding="utf-8")


def main():
    if DIST.exists():
        shutil.rmtree(DIST)
    DIST.mkdir(parents=True)
    gadgets = discover()
    if not gadgets:
        print("⚠️  aucun gadget trouvé (cherche */gadget.json).")
    for g in gadgets:
        build_gadget(g)
    build_index(gadgets)
    # Domaine custom : le CNAME doit être présent dans l'artefact déployé.
    cname = ROOT / "CNAME"
    if cname.exists():
        shutil.copy(cname, DIST / "CNAME")
    print(f"✅ {len(gadgets)} gadget(s) assemblé(s) -> {DIST}")


if __name__ == "__main__":
    main()
