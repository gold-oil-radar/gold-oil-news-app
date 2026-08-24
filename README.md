# Gold & Oil News Radar

Agrège des flux RSS **gratuits** de journaux et sites financiers mondiaux, filtre
automatiquement les articles liés à **l'or**, au **pétrole** et aux **matières premières**,
les traduit en français, et affiche en plus un graphique temps réel du Dollar Index (DXY)
face à l'or (XAU/USD).

Deux façons de l'utiliser :

## 1. Version autonome (recommandée) — hébergée sur GitHub Pages

Le site dans `docs/` est 100% statique et se met à jour tout seul toutes les 15 minutes
via GitHub Actions (`refresh.py` régénère `docs/news.json`), **sans avoir besoin du Mac
allumé ni connecté**. Accessible à l'URL GitHub Pages du dépôt, sur n'importe quel appareil.

## 2. Version locale — serveur sur le Mac

```bash
./run.sh
```

Puis ouvre http://127.0.0.1:5055. Utile pour développer/tester en local (accès Wi-Fi ou
tunnel Cloudflare vers d'autres appareils, bouton de rafraîchissement manuel immédiat).

## Fonctionnement

- `core.py` contient toute la logique partagée : ~14 flux RSS (OilPrice.com, FXStreet,
  Investing.com Commodities, Mining.com, Nasdaq Commodities, MarketWatch, CNBC,
  Yahoo Finance, Seeking Alpha, Business Insider, BBC Business, Al Jazeera, BFM Bourse),
  classification par mots-clés (or/pétrole/matières premières), traduction français
  (MyMemory Translator, avec Google Translate en secours), déduplication.
- `refresh.py` : génère `docs/news.json` (utilisé par GitHub Actions pour la version statique).
- `app.py` : serveur Flask local avec rafraîchissement automatique en tâche de fond.
- Le dashboard (`docs/` ou `templates/`+`static/`) interroge les données toutes les
  5 minutes (statique) ou 60 secondes (local), permet de filtrer par catégorie ou de
  rechercher un mot-clé, et affiche deux widgets TradingView temps réel (DXY et XAU/USD).

## Ajouter une source RSS

Ajoute une entrée dans la liste `FEEDS` de `core.py` avec son URL RSS, un nom, et
`always_relevant=True` si le flux est déjà 100% dédié aux matières premières (sinon
`False` pour qu'il passe par le filtre de mots-clés).

## Mise à jour du cache de traduction

`translations_cache.json` est committé dans le dépôt pour éviter de retraduire les mêmes
articles à chaque exécution — c'est ce qui permet à GitHub Actions de rester rapide.
