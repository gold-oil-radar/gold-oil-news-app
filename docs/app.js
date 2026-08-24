const state = {
  articles: [],
  filter: "all",
  query: "",
};

const SEEN_KEY = "goldOilNewsRadar_seenLinks";
const SEEN_MAX = 600;
let isFirstLoad = true;

const feedListEl = document.getElementById("feed-list");
const lastUpdatedEl = document.getElementById("last-updated");
const articleCountEl = document.getElementById("article-count");
const searchEl = document.getElementById("search");
const refreshBtn = document.getElementById("refresh-btn");
const alertBtn = document.getElementById("alert-btn");
const toastContainer = document.getElementById("toast-container");

document.querySelectorAll(".tab").forEach((tab) => {
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.remove("active"));
    tab.classList.add("active");
    state.filter = tab.dataset.filter;
    render();
  });
});

searchEl.addEventListener("input", () => {
  state.query = searchEl.value.trim().toLowerCase();
  render();
});

refreshBtn.addEventListener("click", () => loadNews());

function timeAgo(iso) {
  if (!iso) return "";
  const diffMs = Date.now() - new Date(iso).getTime();
  const mins = Math.floor(diffMs / 60000);
  if (mins < 1) return "à l'instant";
  if (mins < 60) return `il y a ${mins} min`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `il y a ${hours} h`;
  const days = Math.floor(hours / 24);
  return `il y a ${days} j`;
}

const TAG_LABELS = {
  "or": "🥇 Or",
  "petrole": "🛢️ Pétrole",
  "matieres-premieres": "⛏️ Matières premières",
  "macro": "🏦 Banques centrales",
};

// --- Alertes navigateur ---

function updateAlertBtn() {
  if (!("Notification" in window)) {
    alertBtn.style.display = "none";
    return;
  }
  if (Notification.permission === "granted") {
    alertBtn.textContent = "🔔 Alertes activées";
    alertBtn.disabled = true;
  } else if (Notification.permission === "denied") {
    alertBtn.textContent = "🔕 Alertes bloquées";
    alertBtn.disabled = true;
  } else {
    alertBtn.textContent = "🔔 Activer les alertes";
    alertBtn.disabled = false;
  }
}

alertBtn.addEventListener("click", async () => {
  if ("Notification" in window) {
    await Notification.requestPermission();
    updateAlertBtn();
  }
});

function loadSeenLinks() {
  try {
    return new Set(JSON.parse(localStorage.getItem(SEEN_KEY) || "[]"));
  } catch (e) {
    return new Set();
  }
}

function saveSeenLinks(set) {
  const arr = Array.from(set).slice(-SEEN_MAX);
  try {
    localStorage.setItem(SEEN_KEY, JSON.stringify(arr));
  } catch (e) { /* quota dépassé ou navigation privée: on ignore */ }
}

function showToast(article) {
  const toast = document.createElement("div");
  toast.className = "toast";
  toast.innerHTML = `
    <div class="toast-header">🚨 Info importante — ${escapeHtml(article.source)}</div>
    <a class="toast-title" href="${escapeHtml(article.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(article.title)}</a>
    <button class="toast-close" aria-label="Fermer">×</button>
  `;
  toast.querySelector(".toast-close").addEventListener("click", () => toast.remove());
  toastContainer.appendChild(toast);
  setTimeout(() => toast.remove(), 20000);
}

function notifyImportant(articles) {
  articles.slice(0, 5).forEach((a) => {
    showToast(a);
    if ("Notification" in window && Notification.permission === "granted") {
      const n = new Notification(`🚨 ${a.source}`, {
        body: a.title,
        tag: a.link,
      });
      n.onclick = () => { window.open(a.link, "_blank"); n.close(); };
    }
  });
}

function render() {
  let items = state.articles;

  if (state.filter !== "all") {
    items = items.filter((a) => a.tags.includes(state.filter));
  }
  if (state.query) {
    items = items.filter((a) =>
      (a.title + " " + a.summary + " " + a.source).toLowerCase().includes(state.query)
    );
  }

  articleCountEl.textContent = `${items.length} article${items.length > 1 ? "s" : ""}`;

  if (!items.length) {
    feedListEl.innerHTML = `<p class="loading">Aucun article ne correspond à ce filtre.</p>`;
    return;
  }

  feedListEl.innerHTML = items.map((a) => `
    <article class="card ${a.important ? "card-important" : ""}">
      <div class="card-top">
        <span class="source">${escapeHtml(a.source)}</span>
        <span class="time">${timeAgo(a.published_iso)}</span>
      </div>
      <h2><a href="${escapeHtml(a.link)}" target="_blank" rel="noopener noreferrer">${a.important ? "🚨 " : ""}${escapeHtml(a.title)}</a></h2>
      ${a.summary ? `<p class="summary">${escapeHtml(a.summary)}</p>` : ""}
      <div class="badges">
        ${a.important ? `<span class="badge important">🚨 Important</span>` : ""}
        ${a.tags.map((t) => `<span class="badge ${t}">${TAG_LABELS[t] || t}</span>`).join("")}
      </div>
    </article>
  `).join("");
}

function escapeHtml(str) {
  const div = document.createElement("div");
  div.textContent = str || "";
  return div.innerHTML;
}

async function loadNews() {
  refreshBtn.classList.add("spinning");
  try {
    const res = await fetch(`news.json?t=${Date.now()}`);
    const data = await res.json();
    const articles = data.articles || [];

    if (!isFirstLoad) {
      const seen = loadSeenLinks();
      const newImportant = articles.filter((a) => a.important && !seen.has(a.link));
      if (newImportant.length) notifyImportant(newImportant);
    }

    const seen = loadSeenLinks();
    articles.forEach((a) => seen.add(a.link));
    saveSeenLinks(seen);
    isFirstLoad = false;

    state.articles = articles;
    if (data.last_updated) {
      const d = new Date(data.last_updated);
      lastUpdatedEl.textContent = `Dernière mise à jour : ${d.toLocaleString("fr-FR")}`;
    }
    render();
  } catch (e) {
    lastUpdatedEl.textContent = "Erreur de chargement";
  } finally {
    refreshBtn.classList.remove("spinning");
  }
}

updateAlertBtn();
loadNews();
setInterval(loadNews, 2 * 60 * 1000);
