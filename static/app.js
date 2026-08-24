const state = {
  articles: [],
  filter: "all",
  query: "",
};

const feedListEl = document.getElementById("feed-list");
const lastUpdatedEl = document.getElementById("last-updated");
const articleCountEl = document.getElementById("article-count");
const searchEl = document.getElementById("search");
const refreshBtn = document.getElementById("refresh-btn");

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

refreshBtn.addEventListener("click", async () => {
  refreshBtn.classList.add("spinning");
  refreshBtn.textContent = "↻ Actualisation…";
  await fetch("/api/refresh", { method: "POST" });
  setTimeout(loadNews, 4000);
});

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
};

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
    <article class="card">
      <div class="card-top">
        <span class="source">${escapeHtml(a.source)}</span>
        <span class="time">${timeAgo(a.published_iso)}</span>
      </div>
      <h2><a href="${escapeHtml(a.link)}" target="_blank" rel="noopener noreferrer">${escapeHtml(a.title)}</a></h2>
      ${a.summary ? `<p class="summary">${escapeHtml(a.summary)}</p>` : ""}
      <div class="badges">
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
  try {
    const res = await fetch("/api/news");
    const data = await res.json();
    state.articles = data.articles || [];
    if (data.last_updated) {
      lastUpdatedEl.textContent = `Dernière mise à jour : ${new Date(data.last_updated).toLocaleTimeString("fr-FR")}`;
    }
    render();
  } catch (e) {
    lastUpdatedEl.textContent = "Erreur de chargement";
  } finally {
    refreshBtn.classList.remove("spinning");
    refreshBtn.textContent = "↻ Rafraîchir";
  }
}

loadNews();
setInterval(loadNews, 60 * 1000);
