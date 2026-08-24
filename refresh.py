"""
Génère docs/news.json — exécuté par GitHub Actions (voir .github/workflows/refresh.yml)
pour que le site statique (GitHub Pages) se mette à jour tout seul, sans serveur ni Mac.
"""
import json
import os

import core

OUTPUT_FILE = os.path.join(os.path.dirname(__file__), "docs", "news.json")

if __name__ == "__main__":
    core.load_translation_cache()
    snapshot = core.build_snapshot()
    os.makedirs(os.path.dirname(OUTPUT_FILE), exist_ok=True)
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(snapshot, f, ensure_ascii=False)
    print(f"Écrit {OUTPUT_FILE}")
