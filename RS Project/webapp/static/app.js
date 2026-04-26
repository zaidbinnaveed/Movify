/* Movify — frontend
   - Beautiful generated SVG posters (genre‑themed)
   - Click any card → details modal → set as seed
   - Cold‑start by genres + warm‑start by seed movie
   - Side‑by‑side comparison of Content‑Based vs Collaborative methods
*/

const $  = (sel) => document.querySelector(sel);
const $$ = (sel) => Array.from(document.querySelectorAll(sel));

/* ─────────────── Tiny helpers ─────────────── */
function setStatus(ok, text){
  const dot = $("#statusDot");
  dot.classList.remove("ok","bad");
  dot.classList.add(ok ? "ok" : "bad");
  $("#statusText").textContent = text;
}
function escapeHtml(s){
  return String(s ?? "").replace(/[&<>"']/g, c => (
    { "&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#39;" }[c]
  ));
}
async function apiGet(path){
  const r = await fetch(path, { headers: { "Accept":"application/json" }});
  const data = await r.json().catch(() => ({}));
  if(!r.ok) throw new Error(data?.error || `Request failed (${r.status})`);
  return data;
}
async function apiPost(path, payload){
  const r = await fetch(path, {
    method: "POST",
    headers: { "Content-Type":"application/json", "Accept":"application/json" },
    body: JSON.stringify(payload),
  });
  const data = await r.json().catch(() => ({}));
  if(!r.ok) throw new Error(data?.error || `Request failed (${r.status})`);
  return data;
}

/* ─────────────── State ─────────────── */
let MOVIES = [];          // top rated movies (seed candidates)
let LAST_RECS = [];       // most recent rendered recommendations
let METHOD = "content";
let SEED   = null;
let SELECTED_GENRES = new Set();

/* ─────────────── Genre theming for posters ─────────────── */
/* Each genre maps to a curated colour palette + an icon glyph.
   We pick the movie's first matching genre to drive the look. */
const GENRE_THEMES = {
  Action:     { hues:[ 8, 18, 30], glyph:"💥", mood:"explosive" },
  Adventure:  { hues:[28, 42, 18], glyph:"🧭", mood:"grand" },
  Animation:  { hues:[200,320, 40], glyph:"✨", mood:"playful" },
  Biography:  { hues:[34, 14, 200], glyph:"✒︎", mood:"reflective" },
  Comedy:     { hues:[44, 12, 320], glyph:"☺︎", mood:"warm" },
  Crime:      { hues:[350, 12, 270], glyph:"●", mood:"noir" },
  Drama:      { hues:[260, 340, 12], glyph:"❖", mood:"intense" },
  Family:     { hues:[180, 40, 320], glyph:"❀", mood:"soft" },
  Fantasy:    { hues:[270, 200, 320], glyph:"✺", mood:"magical" },
  "Film-Noir":{ hues:[210, 240, 260], glyph:"◆", mood:"shadowed" },
  History:    { hues:[ 24, 40, 14], glyph:"❧", mood:"vintage" },
  Horror:     { hues:[  0, 320, 280], glyph:"☠︎", mood:"haunting" },
  Music:      { hues:[280, 320, 200], glyph:"♪", mood:"vibrant" },
  Musical:    { hues:[330, 280, 200], glyph:"♫", mood:"vibrant" },
  Mystery:    { hues:[240, 270, 200], glyph:"?",  mood:"shadowed" },
  Romance:    { hues:[340, 12, 320], glyph:"❤︎", mood:"warm" },
  "Sci-Fi":   { hues:[200, 260, 180], glyph:"◉", mood:"electric" },
  Sport:      { hues:[120, 180,  40], glyph:"▲", mood:"bold" },
  Thriller:   { hues:[350, 270,  10], glyph:"!",  mood:"intense" },
  War:        { hues:[ 18, 40,  90], glyph:"✕", mood:"weathered" },
  Western:    { hues:[ 30, 14, 38],  glyph:"★", mood:"sun‑baked" },
};
function themeFor(movie){
  const gs = movie?.genres || [];
  for(const g of gs){
    if(GENRE_THEMES[g]) return { genre: g, ...GENRE_THEMES[g] };
  }
  return { genre: gs[0] || "Drama", hues:[12, 280, 340], glyph:"❖", mood:"cinematic" };
}

/* ─────────────── Poster renderer (SVG → data URI) ─────────────── */
/* Beautiful, distinct, no external assets. Uses genre theme + the title.
   Layered gradients, subtle film‑grain pattern, big initial, clean type. */
function posterDataUri(movie){
  const theme = themeFor(movie);
  const [h1, h2, h3] = theme.hues;
  const title = String(movie?.title || "Movify");
  const initial = (title.match(/[A-Za-z0-9]/) || ["M"])[0].toUpperCase();
  const year = movie?.year ?? "";
  const mid = Number(movie?.movieId || 1);
  const seed = (mid * 9301 + 49297) % 233280; // deterministic accent
  const accentX = 30 + (seed % 40);
  const accentY = 20 + ((seed >> 3) % 30);

  // Title wrapping: split into 1‑3 lines for the lower band
  const words = title.split(/\s+/);
  const lines = [];
  let cur = "";
  for(const w of words){
    if((cur + " " + w).trim().length > 16 && cur){
      lines.push(cur.trim()); cur = w;
    } else { cur = (cur + " " + w).trim(); }
    if(lines.length === 2) break;
  }
  if(cur) lines.push(cur);
  if(words.join(" ").length > lines.join(" ").length){
    const last = lines[lines.length - 1];
    if(last && last.length < 14) lines[lines.length - 1] = last + "…";
  }
  const titleLines = lines.slice(0, 3);

  const id = `g${mid}`;
  const svg = `
<svg xmlns="http://www.w3.org/2000/svg" width="400" height="600" viewBox="0 0 400 600" preserveAspectRatio="xMidYMid slice">
  <defs>
    <linearGradient id="${id}-bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0"   stop-color="hsl(${h1}, 78%, 48%)"/>
      <stop offset=".55" stop-color="hsl(${h2}, 60%, 22%)"/>
      <stop offset="1"   stop-color="hsl(${h3}, 70%, 10%)"/>
    </linearGradient>
    <radialGradient id="${id}-glow" cx="${accentX}%" cy="${accentY}%" r="60%">
      <stop offset="0"  stop-color="rgba(255,255,255,0.35)"/>
      <stop offset=".6" stop-color="rgba(255,255,255,0.05)"/>
      <stop offset="1"  stop-color="rgba(255,255,255,0)"/>
    </radialGradient>
    <linearGradient id="${id}-fade" x1="0" y1="0" x2="0" y2="1">
      <stop offset="0"   stop-color="rgba(0,0,0,0)"/>
      <stop offset=".55" stop-color="rgba(0,0,0,0)"/>
      <stop offset="1"   stop-color="rgba(0,0,0,0.92)"/>
    </linearGradient>
    <pattern id="${id}-grain" width="3" height="3" patternUnits="userSpaceOnUse">
      <rect width="3" height="3" fill="rgba(255,255,255,0)"/>
      <circle cx="1" cy="1" r=".5" fill="rgba(255,255,255,0.06)"/>
    </pattern>
  </defs>

  <rect width="400" height="600" fill="url(#${id}-bg)"/>
  <rect width="400" height="600" fill="url(#${id}-glow)"/>
  <rect width="400" height="600" fill="url(#${id}-grain)"/>

  <!-- Decorative concentric rings -->
  <g opacity=".22" stroke="rgba(255,255,255,.5)" fill="none">
    <circle cx="${accentX*4}" cy="${accentY*6}" r="120"/>
    <circle cx="${accentX*4}" cy="${accentY*6}" r="180"/>
    <circle cx="${accentX*4}" cy="${accentY*6}" r="260"/>
  </g>

  <!-- Big initial letter watermark -->
  <text x="50%" y="48%" text-anchor="middle"
        font-family="'Playfair Display', Georgia, serif"
        font-size="320" font-weight="900"
        fill="rgba(255,255,255,0.10)"
        style="dominant-baseline:middle">${escapeHtml(initial)}</text>

  <!-- Bottom fade for text legibility -->
  <rect width="400" height="600" fill="url(#${id}-fade)"/>

  <!-- Title -->
  ${titleLines.map((l, i) => `
    <text x="24" y="${500 + i*36}"
          font-family="'Playfair Display', Georgia, serif"
          font-size="30" font-weight="900"
          fill="#ffffff"
          style="paint-order:stroke;stroke:rgba(0,0,0,.45);stroke-width:.5px">
      ${escapeHtml(l)}
    </text>`).join("")}

  <!-- Sub line: year + genre -->
  <text x="24" y="${500 + titleLines.length*36 + 22}"
        font-family="Inter, Arial, sans-serif"
        font-size="13" font-weight="600"
        letter-spacing="1.2"
        fill="rgba(255,255,255,0.78)">
    ${escapeHtml(String(year || ""))}${year ? "  ·  " : ""}${escapeHtml(theme.genre.toUpperCase())}
  </text>
</svg>`.trim();

  return "data:image/svg+xml;charset=utf-8," + encodeURIComponent(svg);
}

/* ─────────────── Card ─────────────── */
function rankFor(movie){
  // Top 250 are stored 1..N so movieId is a great surrogate rank
  return Number(movie?.movieId || 0);
}
function buildWhy(expl){
  if(!expl) return "";
  if(expl.type === "content"){
    const terms = (expl.top_terms || []).slice(0,4);
    if(terms.length){
      return `<b>Why:</b> shared ${escapeHtml(terms.join(", "))}`;
    }
    return `<b>Why:</b> ${escapeHtml(expl.why || "Similar content features.")}`;
  }
  if(expl.type === "collaborative"){
    return `<b>Why:</b> ${escapeHtml(expl.why || "Audience co‑rates these similarly.")}`;
  }
  return `<b>Why:</b> ${escapeHtml(expl.why || "Explainable recommendation.")}`;
}
function renderCard(movie){
  const title  = escapeHtml(movie.title);
  const yr     = movie.year ?? "—";
  const rating = (typeof movie.rating === "number") ? movie.rating.toFixed(1) : (movie.rating ?? "N/A");
  const genres = (movie.genres || []).slice(0,2).join(" · ");
  const bg     = posterDataUri(movie);
  const rank   = rankFor(movie);
  const why    = movie.explanation ? buildWhy(movie.explanation) : "";
  const whyHtml = why ? `<div class="whyBox">${why}</div>` : "";
  const tagline = movie.tagline
    ? `<div class="poster__hover-text">"${escapeHtml(movie.tagline)}"</div>` : "";

  return `
    <article class="cardMovie" data-id="${movie.movieId}">
      <div class="poster" style="background-image: url('${bg}')">
        ${rank && rank <= 250 ? `<span class="poster__rank">#${rank}</span>` : ""}
        <span class="poster__rating">★ ${escapeHtml(String(rating))}</span>
        <div class="poster__hover">${tagline}</div>
      </div>
      <div class="cardMovie__meta">
        <div class="cardMovie__title">${title}</div>
        <div class="cardMovie__sub">
          <span>${escapeHtml(String(yr))}</span>
          <span class="sep">·</span>
          <span>${escapeHtml(genres || "—")}</span>
        </div>
        ${whyHtml}
      </div>
    </article>
  `;
}

/* ─────────────── Method, seed ─────────────── */
function setMethod(m){
  METHOD = m;
  $("#methodContent").classList.toggle("chip--on", METHOD === "content");
  $("#methodCollab").classList.toggle("chip--on",  METHOD === "collaborative");
  $("#primaryLabel").textContent = METHOD === "content"
    ? "Content‑based picks · explained by shared features"
    : "Collaborative picks · explained by audience similarity";
  $("#compareLabel").textContent = METHOD === "content"
    ? "Same seed, ranked by collaborative filtering"
    : "Same seed, ranked by content‑based filtering";
}
function setSeed(movie){
  SEED = movie;
  $("#seedTitle").textContent = movie ? movie.title : "Choose a movie above";
  $("#seedSub").textContent   = movie
    ? `${movie.year ?? "—"} · ★ ${(movie.rating ?? "N/A")} · ${(movie.genres || []).join(", ")}`
    : "Click any card to set it as the seed, then we'll find you something to watch next.";
  $("#seedPoster").setAttribute("style",
    movie ? `background-image: url('${posterDataUri(movie)}')` : "");
  $("#recommendBtn").disabled = !movie;
}

/* ─────────────── Rails ─────────────── */
function railMount(railEl, movies, onCardClick){
  if(!movies || movies.length === 0){
    railEl.classList.add("rail--empty");
    railEl.innerHTML = `<div class="empty">${railEl.dataset.empty || "Nothing here yet."}</div>`;
    return;
  }
  railEl.classList.remove("rail--empty");
  railEl.innerHTML = movies.map(renderCard).join("");
  railEl.querySelectorAll(".cardMovie").forEach(el => {
    el.addEventListener("click", () => {
      const id = Number(el.getAttribute("data-id"));
      const movie = movies.find(x => x.movieId === id) || MOVIES.find(x => x.movieId === id);
      if(movie && onCardClick) onCardClick(movie);
    });
  });
}

/* Rail arrow buttons */
function wireRailArrows(){
  $$(".rail-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      const target = document.getElementById(btn.dataset.target);
      if(!target) return;
      const dir = btn.classList.contains("rail-btn--left") ? -1 : 1;
      target.scrollBy({ left: dir * Math.min(target.clientWidth * .8, 800), behavior: "smooth" });
    });
  });
}

/* ─────────────── Modal ─────────────── */
async function openModal(movie){
  const modal = $("#modal");
  $("#modalKicker").textContent  = (movie.genres || []).slice(0, 3).join(" · ") || "Movie";
  $("#modalTitle").textContent   = movie.title || "—";
  $("#modalPoster").setAttribute("style", `background-image: url('${posterDataUri(movie)}')`);
  $("#modalTagline").textContent = movie.tagline ? `"${movie.tagline}"` : "";
  $("#modalMeta").innerHTML = `
    <span>${escapeHtml(String(movie.year ?? "—"))}</span>
    <span>·</span>
    <span class="badge">★ ${escapeHtml(String((movie.rating ?? "N/A")))}</span>
    ${rankFor(movie) ? `<span>·</span><span>#${rankFor(movie)} on IMDB Top 250</span>` : ""}
  `;
  $("#modalGrid").innerHTML = `<div><h4>Loading…</h4><p class="muted">Fetching details</p></div>`;

  modal.hidden = false;
  document.body.style.overflow = "hidden";

  // Hydrate full details
  try{
    const data = await apiGet(`/api/movie/${movie.movieId}`);
    const m = data.movie || movie;
    const cell = (label, value) => `
      <div>
        <h4>${escapeHtml(label)}</h4>
        <p>${escapeHtml(value || "—")}</p>
      </div>`;
    $("#modalGrid").innerHTML = [
      cell("Director(s)", (m.directors || []).join(", ")),
      cell("Writer(s)",   (m.writers   || []).join(", ")),
      cell("Cast",        (m.cast      || []).slice(0,8).join(", ")),
      cell("Runtime · Cert", `${m.run_time || "—"}${m.certificate ? `  ·  ${m.certificate}` : ""}`),
    ].join("");
  }catch(e){
    $("#modalGrid").innerHTML = `<div><h4>Could not load details</h4><p class="muted">${escapeHtml(e.message)}</p></div>`;
  }

  $("#modalSeedBtn").onclick = () => {
    setSeed(movie);
    closeModal();
    recommendFromSeed();
  };
}
function closeModal(){
  $("#modal").hidden = true;
  document.body.style.overflow = "";
}
function wireModal(){
  $("#modal").addEventListener("click", (e) => {
    if(e.target.dataset.close) closeModal();
  });
  document.addEventListener("keydown", (e) => { if(e.key === "Escape") closeModal(); });
}

/* ─────────────── API actions ─────────────── */
async function loadFeatured(){
  const data = await apiGet("/api/featured");
  const f = data.featured;
  if(!f) return;
  $("#heroTitle").textContent   = f.title;
  $("#heroTagline").textContent = f.tagline || "Pick a movie and compare content‑based vs. collaborative recommendations.";
  $("#heroBg").setAttribute("style",
    `background-image: url('${posterDataUri(f)}'); background-size: cover; background-position: center;`);
  $("#heroMeta").innerHTML = `
    <span class="badge">★ ${escapeHtml(String((f.rating ?? "N/A")))}</span>
    <span>${escapeHtml(String(f.year ?? "—"))}</span>
    <span>·</span>
    <span>${escapeHtml((f.genres || []).join(" · "))}</span>
  `;
}
async function loadGenres(){
  const data = await apiGet("/api/genres");
  const genres = data.genres || [];
  const box = $("#genreChips");
  box.innerHTML = "";
  for(const g of genres){
    const b = document.createElement("button");
    b.className = "chip";
    b.innerHTML = `<span class="chip__dot"></span> ${escapeHtml(g)}`;
    b.addEventListener("click", () => {
      if(SELECTED_GENRES.has(g)) SELECTED_GENRES.delete(g);
      else SELECTED_GENRES.add(g);
      b.classList.toggle("chip--on", SELECTED_GENRES.has(g));
    });
    box.appendChild(b);
  }
}
async function loadTop(){
  const data = await apiGet("/api/movies?limit=60");
  MOVIES = data.results || [];
  $("#topCount").textContent = `· ${MOVIES.length}`;
  railMount($("#railTop"), MOVIES, openModal);
}
async function searchMovies(q){
  const data = await apiGet(`/api/movies?q=${encodeURIComponent(q)}&limit=60`);
  const results = data.results || [];
  $("#topCount").textContent = `· ${results.length}`;
  railMount($("#railTop"), results, openModal);
}
async function recommendFromSeed(){
  $("#recErr").textContent = "";
  if(!SEED) return;
  setRecommendBusy(true);
  try{
    const data = await apiPost("/api/recommend", { method: METHOD, seed_movieId: SEED.movieId, n: 14 });
    LAST_RECS = data.primary || [];
    railMount($("#railPrimary"),    data.primary    || [], openModal);
    railMount($("#railComparison"), data.comparison || [], openModal);
    document.querySelector("#recommend")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }catch(e){
    $("#recErr").textContent = e?.message || String(e);
  }finally{
    setRecommendBusy(false);
  }
}
async function recommendColdStart(){
  $("#recErr").textContent  = "";
  $("#coldErr").textContent = "";
  const preferred_genres = Array.from(SELECTED_GENRES);
  if(preferred_genres.length === 0){
    $("#coldErr").textContent = "Pick at least one genre to get recommendations.";
    return;
  }
  setRecommendBusy(true);
  try{
    const data = await apiPost("/api/recommend",
      { method: METHOD, preferred_genres, liked_movieIds: [], n: 14 });
    railMount($("#railPrimary"),    data.primary    || [], openModal);
    railMount($("#railComparison"), data.comparison || [], openModal);
    document.querySelector("#recommend")?.scrollIntoView({ behavior: "smooth", block: "start" });
  }catch(e){
    $("#coldErr").textContent = e?.message || String(e);
    $("#recErr").textContent  = e?.message || String(e);
  }finally{
    setRecommendBusy(false);
  }
}
function setRecommendBusy(b){
  const btn = $("#recommendBtn");
  if(!btn) return;
  btn.disabled = b || !SEED;
  btn.textContent = b ? "Finding picks…" : "";
  if(!b){
    btn.innerHTML = `
      <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M12 2 14.39 8.26 21 9.27l-5 4.87L17.18 21 12 17.77 6.82 21 8 14.14l-5-4.87 6.61-1.01L12 2Z"/></svg>
      Get Recommendations
    `;
  }
}

/* ─────────────── Boot ─────────────── */
async function boot(){
  setStatus(false, "Connecting…");
  try{
    const h = await apiGet("/api/health");
    setStatus(true, `Online · ${h.movies} movies · ${h.genres} genres`);
  }catch(e){
    setStatus(false, `Offline · ${e.message}`);
    return;
  }
  setMethod("content");
  await Promise.all([loadFeatured(), loadGenres(), loadTop()]);
}

/* ─────────────── Wire UI ─────────────── */
$("#methodContent").addEventListener("click", () => setMethod("content"));
$("#methodCollab").addEventListener("click",  () => setMethod("collaborative"));

$("#searchBtn").addEventListener("click", async () => {
  const q = $("#searchInput").value.trim();
  if(!q) return loadTop();
  await searchMovies(q);
});
$("#searchInput").addEventListener("keydown", (e) => {
  if(e.key === "Enter") $("#searchBtn").click();
});

$("#recommendBtn").addEventListener("click", recommendFromSeed);
$("#coldStartBtn").addEventListener("click", recommendColdStart);
$("#clearGenresBtn").addEventListener("click", () => {
  SELECTED_GENRES.clear();
  $$("#genreChips .chip").forEach(c => c.classList.remove("chip--on"));
  $("#coldErr").textContent = "";
});

wireRailArrows();
wireModal();
boot();
