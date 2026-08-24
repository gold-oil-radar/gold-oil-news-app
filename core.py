"""
Gold & Oil News Radar — logique partagée
Agrège des flux RSS gratuits, filtre les articles liés à l'or, au pétrole
et aux matières premières, et les traduit en français.
"""
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone

import feedparser
import requests
from deep_translator import GoogleTranslator, MyMemoryTranslator

BASE_DIR = os.path.dirname(__file__)
TRANSLATION_CACHE_FILE = os.path.join(BASE_DIR, "translations_cache.json")
TRANSLATION_CACHE_MAX_ENTRIES = 3000
TRANSLATION_WORKERS = 4
TRANSLATION_BAD_MARKERS = ("Error 500", "That’s an error", "That's an error", "<html", "<!DOCTYPE")
# Identifie les requêtes auprès de MyMemory pour bénéficier du quota gratuit étendu (50 000 car./jour au lieu de 5 000)
TRANSLATION_CONTACT_EMAIL = "gaelbrs@gmail.com"

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

MAX_ARTICLES = 200
FETCH_TIMEOUT = 10

# always_relevant=True  -> flux dédiés matières premières/or/pétrole, on garde tout
# always_relevant=False -> flux économiques généralistes, on filtre par mots-clés
# default_tag           -> tag appliqué quand always_relevant=True et qu'aucun mot-clé ne matche (def: matieres-premieres)
FEEDS = [
    # --- Sources dédiées matières premières / commodities ---
    {"name": "OilPrice.com", "url": "https://oilprice.com/rss/main", "always_relevant": True, "lang": "en"},
    {"name": "FXStreet (Forex & Commodities)", "url": "https://www.fxstreet.com/rss/news", "always_relevant": True, "lang": "en"},
    {"name": "Investing.com Commodities", "url": "https://www.investing.com/rss/news_11.rss", "always_relevant": True, "lang": "en"},
    {"name": "Mining.com", "url": "https://www.mining.com/feed/", "always_relevant": True, "lang": "en"},
    {"name": "Nasdaq Commodities", "url": "https://www.nasdaq.com/feed/rssoutbound?category=Commodities", "always_relevant": True, "lang": "en"},
    {"name": "EIA - Today in Energy", "url": "https://www.eia.gov/rss/todayinenergy.xml", "always_relevant": True, "lang": "en", "default_tag": "petrole"},

    # --- Sources officielles (banques centrales) : le driver n°1 du prix de l'or ---
    # always_relevant=False ici : ces flux mêlent décisions de taux (très pertinent) et
    # communiqués administratifs (agréments bancaires, enquêtes FX...) qu'on ne veut pas voir.
    # Seuls les communiqués qui matchent MACRO_RE (taux, inflation, FOMC...) sont gardés.
    {"name": "Federal Reserve - Communiqués", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "always_relevant": False, "lang": "en"},
    {"name": "BCE - Communiqués", "url": "https://www.ecb.europa.eu/rss/press.xml", "always_relevant": False, "lang": "en"},
    {"name": "Bank of England - News", "url": "https://www.bankofengland.co.uk/rss/news", "always_relevant": False, "lang": "en"},

    # --- Journaux économiques généralistes (filtrés par mots-clés) ---
    {"name": "MarketWatch - Top Stories", "url": "http://feeds.marketwatch.com/marketwatch/topstories/", "always_relevant": False, "lang": "en"},
    {"name": "MarketWatch - MarketPulse", "url": "http://feeds.marketwatch.com/marketwatch/marketpulse/", "always_relevant": False, "lang": "en"},
    {"name": "CNBC Markets", "url": "https://www.cnbc.com/id/20910258/device/rss/rss.html", "always_relevant": False, "lang": "en"},
    {"name": "Yahoo Finance", "url": "https://finance.yahoo.com/news/rssindex", "always_relevant": False, "lang": "en"},
    {"name": "Seeking Alpha", "url": "https://seekingalpha.com/market_currents.xml", "always_relevant": False, "lang": "en"},
    {"name": "Business Insider Markets", "url": "https://markets.businessinsider.com/rss/news", "always_relevant": False, "lang": "en"},
    {"name": "BBC Business", "url": "http://feeds.bbci.co.uk/news/business/rss.xml", "always_relevant": False, "lang": "en"},
    {"name": "The Guardian - Business", "url": "https://www.theguardian.com/uk/business/rss", "always_relevant": False, "lang": "en"},
    {"name": "Sky News - Business", "url": "https://feeds.skynews.com/feeds/rss/business.xml", "always_relevant": False, "lang": "en"},
    {"name": "Financial Times", "url": "https://www.ft.com/rss/home", "always_relevant": False, "lang": "en"},
    {"name": "South China Morning Post - Business", "url": "https://www.scmp.com/rss/92/feed", "always_relevant": False, "lang": "en"},
    {"name": "Times of India - Business", "url": "https://timesofindia.indiatimes.com/rssfeeds/1898055.cms", "always_relevant": False, "lang": "en"},
    {"name": "Deutsche Welle - Business", "url": "https://rss.dw.com/rdf/rss-en-bus", "always_relevant": False, "lang": "en"},
    {"name": "ABC News Australia - Business", "url": "https://www.abc.net.au/news/feed/51892/rss.xml", "always_relevant": False, "lang": "en"},
    {"name": "Straits Times - World", "url": "https://www.straitstimes.com/news/business/rss.xml", "always_relevant": False, "lang": "en"},
    {"name": "Al Jazeera (Monde)", "url": "https://www.aljazeera.com/xml/rss/all.xml", "always_relevant": False, "lang": "en"},

    # --- Journaux francophones ---
    {"name": "BFM Bourse", "url": "https://www.bfmtv.com/rss/economie/", "always_relevant": False, "lang": "fr"},
    {"name": "Le Figaro - Economie", "url": "https://www.lefigaro.fr/rss/figaro_economie.xml", "always_relevant": False, "lang": "fr"},
    {"name": "Le Monde - Economie", "url": "https://www.lemonde.fr/economie/rss_full.xml", "always_relevant": False, "lang": "fr"},
]

GOLD_PATTERNS = [
    r"\bgold\b", r"\bxau\b", r"\bbullion\b", r"gold price", r"gold miner",
    r"l'or\b", r"d'or\b", r"cours de l'or", r"prix de l'or", r"once d'or",
    r"m[ée]tal jaune", r"\blingots?\b", r"march[ée] de l'or",
]
OIL_PATTERNS = [
    r"\boil\b", r"\bcrude\b", r"\bbrent\b", r"\bwti\b", r"\bopec\+?\b",
    r"\bbarrel\b", r"\bshale\b", r"\brefiner", r"\bpetroleum\b",
    r"p[ée]trole", r"\bop[ée]p\b", r"\bbaril\b", r"raffinerie", r"essence\b",
    r"gasoil", r"brut\b",
]
COMMODITY_PATTERNS = [
    r"\bcommodit(y|ies)\b", r"\bsilver\b", r"\bcopper\b", r"\bmining\b",
    r"mati[èe]res? premi[èe]res?", r"\bargent m[ée]tal\b", r"\bcuivre\b",
    r"\bminerai\b", r"\bnickel\b", r"\blithium\b",
]
MACRO_PATTERNS = [
    r"\bfed\b", r"\bfomc\b", r"federal reserve", r"\brate cut", r"\brate hike",
    r"interest rate", r"taux d.int[ée]r[êe]t", r"taux directeur", r"banque centrale",
    r"\becb\b", r"european central bank", r"quantitative easing",
    r"\binflation\b", r"\bcpi\b", r"\bpce\b", r"bank of england",
    r"politique mon[ée]taire", r"\bpowell\b", r"\blagarde\b",
]
# Signaux à fort impact immédiat -> déclenchent une notification/pop-up côté client
IMPORTANT_PATTERNS = [
    # décisions de taux actées (pas juste des anticipations)
    r"\braises? (its |interest )?rates?\b", r"\bcuts? (its |interest )?rates?\b",
    r"\bhikes? rates?\b", r"\brate decision\b", r"hausse des taux", r"baisse des taux",
    r"\bfomc statement\b", r"\bemergency meeting\b", r"r[ée]union d.urgence",
    # OPEP / offre pétrolière
    r"\bopec\+? (agrees?|announces?|cuts?|raises?)\b", r"production cut", r"production increase",
    r"l.op[ée]p (annonce|d[ée]cide)",
    # mouvements de prix extrêmes
    r"\bsurges?\b", r"\bplunges?\b", r"\bcrashes?\b", r"\bsoars?\b",
    r"record high", r"record low", r"all-time high", r"record historique",
    r"s.effondre", r"bondit", r"flambe", r"chute libre",
    # géopolitique à impact direct sur l'offre
    r"\battack(s|ed)? on\b", r"\bstrikes? on\b", r"\bexplosion at\b", r"\binvasion\b",
    r"\bceasefire\b", r"sanctions on\b", r"\bblockade\b",
    r"attaque contre", r"cessez-le-feu", r"sanctions contre",
]

GOLD_RE = re.compile("|".join(GOLD_PATTERNS), re.IGNORECASE)
OIL_RE = re.compile("|".join(OIL_PATTERNS), re.IGNORECASE)
COMMODITY_RE = re.compile("|".join(COMMODITY_PATTERNS), re.IGNORECASE)
MACRO_RE = re.compile("|".join(MACRO_PATTERNS), re.IGNORECASE)
IMPORTANT_RE = re.compile("|".join(IMPORTANT_PATTERNS), re.IGNORECASE)

_translation_cache_lock = threading.Lock()
_translation_cache = {}


def load_translation_cache():
    global _translation_cache
    try:
        with open(TRANSLATION_CACHE_FILE, "r", encoding="utf-8") as f:
            _translation_cache = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        _translation_cache = {}


def save_translation_cache():
    with _translation_cache_lock:
        # borne la taille du cache pour qu'il ne grossisse pas indéfiniment
        if len(_translation_cache) > TRANSLATION_CACHE_MAX_ENTRIES:
            excess = len(_translation_cache) - TRANSLATION_CACHE_MAX_ENTRIES
            for key in list(_translation_cache.keys())[:excess]:
                del _translation_cache[key]
        try:
            with open(TRANSLATION_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(_translation_cache, f, ensure_ascii=False)
        except OSError:
            pass


def is_bad_translation(text):
    return bool(text) and any(marker in text for marker in TRANSLATION_BAD_MARKERS)


def make_translator():
    return MyMemoryTranslator(source="en-GB", target="fr-FR", email=TRANSLATION_CONTACT_EMAIL)


def make_fallback_translator():
    return GoogleTranslator(source="auto", target="fr")


def translate_text(text):
    if not text:
        return text, True
    # MyMemory limite chaque appel à 500 caractères
    chunk = text[:490]
    for translator_factory in (make_translator, make_fallback_translator):
        try:
            result = translator_factory().translate(chunk)
            if result and not is_bad_translation(result):
                return result, True
        except Exception:
            pass
        time.sleep(0.5)
    return text, False


def translate_pair(title, summary):
    t_title, ok1 = translate_text(title)
    t_summary, ok2 = translate_text(summary)
    return t_title, t_summary, (ok1 and ok2)


def translate_articles(articles):
    """Traduit en français (en place) les articles dont la langue source n'est pas déjà fr."""
    to_translate = []
    with _translation_cache_lock:
        for art in articles:
            if art["lang"] == "fr":
                continue
            cached = _translation_cache.get(art["link"])
            if cached:
                art["title"] = cached["title"]
                art["summary"] = cached["summary"]
            else:
                to_translate.append(art)

    if not to_translate:
        return

    with ThreadPoolExecutor(max_workers=TRANSLATION_WORKERS) as executor:
        results = list(executor.map(lambda a: translate_pair(a["title"], a["summary"]), to_translate))

    with _translation_cache_lock:
        for art, (t_title, t_summary, ok) in zip(to_translate, results):
            art["title"] = t_title
            art["summary"] = t_summary
            if ok:
                _translation_cache[art["link"]] = {"title": t_title, "summary": t_summary}

    save_translation_cache()


def classify(text):
    tags = []
    if GOLD_RE.search(text):
        tags.append("or")
    if OIL_RE.search(text):
        tags.append("petrole")
    if COMMODITY_RE.search(text):
        tags.append("matieres-premieres")
    if MACRO_RE.search(text):
        tags.append("macro")
    return tags


def parse_published(entry):
    for key in ("published_parsed", "updated_parsed"):
        val = entry.get(key)
        if val:
            try:
                return datetime(*val[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_feed(feed):
    articles = []
    error = None
    try:
        resp = requests.get(feed["url"], headers={"User-Agent": USER_AGENT}, timeout=FETCH_TIMEOUT)
        parsed = feedparser.parse(resp.content)
        for entry in parsed.entries:
            title = entry.get("title", "").strip()
            summary = re.sub("<[^<]+?>", "", entry.get("summary", entry.get("description", ""))).strip()
            link = entry.get("link", "")
            if not title or not link:
                continue

            haystack = f"{title} {summary}"
            tags = classify(haystack)

            if not feed["always_relevant"] and not tags:
                continue

            published = parse_published(entry)
            articles.append({
                "title": title,
                "summary": (summary[:280] + "…") if len(summary) > 280 else summary,
                "link": link,
                "source": feed["name"],
                "lang": feed["lang"],
                "tags": tags or ([feed.get("default_tag", "matieres-premieres")] if feed["always_relevant"] else []),
                "important": bool(IMPORTANT_RE.search(haystack)),
                "published_iso": published.isoformat() if published else None,
                "published_ts": published.timestamp() if published else 0,
            })
    except Exception as exc:
        error = str(exc)
    return articles, error


def build_snapshot():
    """Récupère tous les flux, filtre, déduplique et traduit. Retourne le dict prêt à sérialiser."""
    started = time.time()
    all_articles = []
    status = {}
    for feed in FEEDS:
        articles, error = fetch_feed(feed)
        status[feed["name"]] = {"count": len(articles), "error": error}
        all_articles.extend(articles)

    seen_links = set()
    deduped = []
    for art in sorted(all_articles, key=lambda a: a["published_ts"], reverse=True):
        if art["link"] in seen_links:
            continue
        seen_links.add(art["link"])
        deduped.append(art)

    deduped = deduped[:MAX_ARTICLES]
    translate_articles(deduped)

    snapshot = {
        "articles": deduped,
        "last_updated": datetime.now(timezone.utc).isoformat(),
        "feed_status": status,
    }
    print(f"[refresh] {len(deduped)} articles in {time.time() - started:.1f}s", flush=True)
    return snapshot
