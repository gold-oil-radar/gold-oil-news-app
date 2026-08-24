"""
Gold & Oil News Radar — serveur local (usage optionnel : Wi-Fi / tunnel).
Pour la version 100% autonome (hébergée, sans le Mac), voir refresh.py + docs/.
"""
import threading
import time

from flask import Flask, jsonify, render_template

import core

app = Flask(__name__)

REFRESH_INTERVAL_SECONDS = 10 * 60  # rafraîchit les flux toutes les 10 minutes

_lock = threading.Lock()
_state = {"articles": [], "last_updated": None, "feed_status": {}}


def refresh_all():
    snapshot = core.build_snapshot()
    with _lock:
        _state.update(snapshot)


def background_refresher():
    while True:
        try:
            refresh_all()
        except Exception as exc:
            print("Refresh error:", exc)
        time.sleep(REFRESH_INTERVAL_SECONDS)


@app.route("/")
def index():
    return render_template("index.html", feeds=core.FEEDS)


@app.route("/api/news")
def api_news():
    with _lock:
        return jsonify(_state)


@app.route("/api/refresh", methods=["POST"])
def api_refresh():
    threading.Thread(target=refresh_all, daemon=True).start()
    return jsonify({"status": "refresh started"})


if __name__ == "__main__":
    core.load_translation_cache()
    t = threading.Thread(target=background_refresher, daemon=True)
    t.start()
    app.run(host="0.0.0.0", port=5055, debug=False)
