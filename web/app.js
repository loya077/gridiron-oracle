/* Gridiron Oracle front end. All model math mirrors oracle/*.py. */
(() => {
  "use strict";
  const $app = document.getElementById("app");
  const S = { app: null, ledger: { picks: {} }, settings: { influence: 0, w_astro: 25, w_num: 75 }, byId: {} };
  const HFA = 30, NUM_MAX = 48, AST_MAX = 4;
  const PLAYOFF = { 19: "Wild Card", 20: "Divisional", 21: "Conference", 22: "Super Bowl" };

  // ---------------------------------------------------------------- math
  const sigmoid = x => 1 / (1 + Math.exp(-x));
  const logit = p => { p = Math.min(Math.max(p, 1e-9), 1 - 1e-9); return Math.log(p / (1 - p)); };
  const readVal = (r, s) => (s.w_astro / 10) * (r.astro / AST_MAX) + (s.w_num / 10) * (r.num / NUM_MAX) * 2;
  function evalGame(g, s = S.settings) {
    const rh = readVal(g.read_home, s), ra = readVal(g.read_away, s);
    const od = rh - ra;
    const lam = (s.influence / 100) * 0.3;
    const pHome = sigmoid(logit(g.p_elo) + lam * od);
    const pick = pHome >= 0.5 ? g.home : g.away;
    const strengthPick = g.p_elo >= 0.5 ? g.home : g.away;
    const pRead = sigmoid(od / 2.5);
    let badge, fav = null;
    if (Math.abs(od) < 1e-9) badge = "even";
    else { fav = od > 0 ? g.home : g.away; badge = fav === pick ? "agree" : "favor"; }
    return { rh, ra, od, lam, pHome, pick, conf: Math.max(pHome, 1 - pHome), strengthPick, pRead, badge, fav };
  }
  const played = g => g.home_score !== null && g.away_score !== null;
  const winner = g => g.home_score > g.away_score ? g.home : g.away_score > g.home_score ? g.away : null;

  // ---------------------------------------------------------------- format
  const pct = (x, d = 1) => x == null ? "—" : (100 * x).toFixed(d) + "%";
  const sgn = (x, d = 1) => (x > 0 ? "+" : x < 0 ? "−" : "±") + Math.abs(x).toFixed(d);
  const esc = s => String(s ?? "").replace(/[&<>"]/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));
  const tname = a => (S.app.teams[a] || {}).name || a;
  const weekName = w => PLAYOFF[w] || "Week " + w;
  function kickoff(g) {
    const d = new Date(g.gameday + "T12:00:00");
    const day = d.toLocaleDateString(undefined, { weekday: "short", month: "short", day: "numeric" });
    if (!g.gametime) return day;
    let [h, m] = g.gametime.split(":").map(Number);
    const ap = h >= 12 ? "PM" : "AM"; h = h % 12 || 12;
    return `${day} · ${h}:${String(m).padStart(2, "0")} ${ap} ET`;
  }
  function spreadText(team, pts) {
    if (Math.abs(pts) < 0.05) return "Pick'em";
    return `${team} −${Math.abs(pts).toFixed(1)}`;
  }
  const modelSpread = g => { const s = g.diff / 25; return spreadText(s >= 0 ? g.home : g.away, s); };
  const marketSpread = g => g.spread_line == null ? null : spreadText(g.spread_line >= 0 ? g.home : g.away, g.spread_line);
  function marketDisagrees(g, ev) {
    if (g.spread_line == null || g.spread_line === 0) return false;
    return (g.spread_line > 0 ? g.home : g.away) !== ev.pick;
  }
  function badgeText(ev) {
    return ev.badge === "agree" ? "Readings agree" : ev.badge === "even" ? "Readings even" : `Readings favor ${ev.fav}`;
  }

  // ---------------------------------------------------------------- data
  async function load() {
    try {
      const [a, l] = await Promise.all([fetch("data/app.json").then(r => { if (!r.ok) throw 0; return r.json(); }),
        fetch("data/ledger.json").then(r => r.ok ? r.json() : { picks: {} }).catch(() => ({ picks: {} }))]);
      S.app = a; S.ledger = l;
      a.games.forEach(g => (S.byId[g.id] = g));
      S.settings = Object.assign({}, a.settings);
      try {
        const r = await fetch("api/settings");
        if (r.ok && (r.headers.get("Content-Type") || "").includes("json")) S.settings = await r.json();
        else throw 0;
      } catch (e) {
        // Hosted (static) copy: no server to save to, so use this device's saved sliders if any.
        S.hosted = true;
        try { const ls = JSON.parse(localStorage.getItem("oracle-settings") || "null"); if (ls) Object.assign(S.settings, ls); } catch (e2) {}
      }
      document.getElementById("stamp").textContent =
        `Data refreshed ${new Date(a.generated_at).toLocaleString()}. Settings: readings influence ${S.settings.influence}, astrology ${S.settings.w_astro}, numerology ${S.settings.w_num}.`;
    } catch (e) {
      $app.innerHTML = `<div class="empty"><h2>No data yet</h2><p>Run <code>make refresh</code>, then <code>make run</code> and open the address it prints.</p></div>`;
      return false;
    }
    return true;
  }

  // ---------------------------------------------------------------- router
  function route() {
    if (!S.app) return;
    const h = location.hash.replace(/^#\/?/, "").split("/");
    const tab = h[0] === "ledger" ? "ledger" : h[0] === "backtest" ? "backtest" : h[0] === "settings" ? "settings" : "slate";
    document.querySelectorAll("#tabs a").forEach(a => a.classList.toggle("on", a.dataset.tab === tab));
    if (h[0] === "g" && S.byId[h[1]]) renderGame(S.byId[h[1]]);
    else if (h[0] === "w") renderSlate(+h[1], +h[2]);
    else if (tab === "ledger") renderLedger(+h[1] || S.app.current.season);
    else if (tab === "backtest") renderBacktest();
    else if (tab === "settings") renderSettings();
    else renderSlate(S.app.current.season, S.app.current.week);
    window.scrollTo(0, 0);
  }

  // ---------------------------------------------------------------- slate
  function renderSlate(season, week) {
    const weeks = S.app.weeks[season];
    if (!weeks || !weeks.includes(week)) { season = S.app.current.season; week = S.app.current.week; }
    const games = S.app.games.filter(g => g.season === season && g.week === week);
    const wl = S.app.weeks[season], i = wl.indexOf(week);
    const seasons = Object.keys(S.app.weeks).map(Number);
    const prev = i > 0 ? [season, wl[i - 1]] : S.app.weeks[season - 1] ? [season - 1, S.app.weeks[season - 1].slice(-1)[0]] : null;
    const next = i < wl.length - 1 ? [season, wl[i + 1]] : S.app.weeks[season + 1] ? [season + 1, S.app.weeks[season + 1][0]] : null;
    const isCur = season === S.app.current.season && week === S.app.current.week;
    let wins = 0, losses = 0;
    const cards = games.map(g => {
      const ev = evalGame(g);
      let res = "";
      if (played(g)) {
        const w = winner(g);
        if (!w) res = `<span class="result tie">Tie</span>`;
        else if (w === ev.pick) { wins++; res = `<span class="result win">✓ Hit</span>`; }
        else { losses++; res = `<span class="result loss">✗ Miss</span>`; }
      }
      const mk = marketSpread(g);
      const row = (t, rec, sc) => `<div class="trow ${t === ev.pick ? "picked" : ""}"><span class="ab">${t}</span><span class="nm">${esc(tname(t))}</span><span class="rec">${rec}</span>${played(g) ? `<span class="sc">${sc}</span>` : ""}</div>`;
      return `<a class="card" href="#/g/${g.id}">
        <div class="when"><span>${kickoff(g)}</span><span>${g.neutral ? "Neutral site" : ""}</span></div>
        <div class="teams">${row(g.away, g.rec_away, g.away_score)}${row(g.home, g.rec_home, g.home_score)}</div>
        <div class="pickline"><span class="lbl">Pick</span><span class="who">${ev.pick} ${esc(tname(ev.pick))}</span><span class="pct">${pct(ev.conf)}</span></div>
        <div class="bar"><span style="width:${(100 * ev.conf).toFixed(1)}%"></span></div>
        <div class="meta"><span>Model <b>${modelSpread(g)}</b></span>${mk ? `<span>Market <b>${mk}</b></span>` : `<span>Market —</span>`}${marketDisagrees(g, ev) ? `<span class="flag">⚑ Market picks ${g.spread_line > 0 ? g.home : g.away}</span>` : ""}</div>
        <div class="badges"><span class="rbadge">${badgeText(ev)}</span>${res}</div>
      </a>`;
    }).join("");
    $app.innerHTML = `
      <div class="weekbar">
        <h1>${weekName(week)}<small>${season} season${isCur ? " · this week" : ""}${wins + losses ? ` · ${wins}–${losses}` : ""}</small></h1>
        <div class="seg">
          <button ${prev ? "" : "disabled"} id="prev" aria-label="Previous week">‹</button>
          <select id="season">${seasons.map(s => `<option ${s === season ? "selected" : ""}>${s}</option>`).join("")}</select>
          <select id="week">${wl.map(w => `<option value="${w}" ${w === week ? "selected" : ""}>${weekName(w)}</option>`).join("")}</select>
          <button ${next ? "" : "disabled"} id="next" aria-label="Next week">›</button>
          ${isCur ? "" : `<button id="today">This week</button>`}
        </div>
      </div>
      <div class="legend"><span><i style="background:var(--pick)"></i>Model pick (strength + home${S.settings.influence ? ` + readings at ${S.settings.influence}` : ""})</span><span><i style="background:var(--read)"></i>Your readings</span><span><i style="background:var(--warn)"></i>Model and market disagree</span></div>
      ${games.length ? `<div class="grid">${cards}</div>` : `<div class="empty">No games this week.</div>`}`;
    const go = (s, w) => (location.hash = `#/w/${s}/${w}`);
    document.getElementById("prev").onclick = () => prev && go(...prev);
    document.getElementById("next").onclick = () => next && go(...next);
    document.getElementById("season").onchange = e => go(+e.target.value, S.app.weeks[e.target.value][0]);
    document.getElementById("week").onchange = e => go(season, +e.target.value);
    const t = document.getElementById("today"); if (t) t.onclick = () => (location.hash = "#/");
  }

  // ---------------------------------------------------------------- game detail
  function readingsTable(g, side, ev) {
    const r = side === "home" ? g.read_home : g.read_away, team = side === "home" ? g.home : g.away;
    const prof = S.app.teams[team];
    const val = side === "home" ? ev.rh : ev.ra;
    const rows = r.factors.map(f => `<tr><td>${f.factor} <span class="muted">${f.team}</span></td><td>vs ${f.vs} <span class="muted">${f.game}</span></td><td>${f.rel}</td><td class="r">${sgn(f.points, 0)}</td><td class="r">×${f.weight}</td><td class="r ${f.weighted > 0 ? "pos" : f.weighted < 0 ? "neg" : ""}">${sgn(f.weighted, 0)}</td></tr>`).join("");
    return `<h2>${team} ${esc(prof.name)} <span class="muted small">(${prof.born_day}, ${prof.life_path}, ${prof.pinnacle}, ${prof.animal})</span></h2>
      <div class="tablewrap"><table>
        <thead><tr><th>Team number</th><th>Against</th><th>Relationship</th><th class="r">Pts</th><th class="r">Wt</th><th class="r">Score</th></tr></thead>
        <tbody>${rows}
          <tr class="tot"><td colspan="5">Numerology total (max 48)</td><td class="r">${sgn(r.num, 0)}</td></tr>
          <tr><td>Animal <span class="muted">${prof.animal}</span></td><td>vs year <span class="muted">${g.gnums.animal}</span></td><td>${r.astro_rel}</td><td class="r">${sgn(r.astro, 0)}</td><td class="r"></td><td class="r ${r.astro > 0 ? "pos" : r.astro < 0 ? "neg" : ""}">${sgn(r.astro, 0)}</td></tr>
          <tr class="tot"><td colspan="5">Readings score <span class="muted small">(${S.settings.w_astro}/10 × ${r.astro}/4 + ${S.settings.w_num}/10 × ${r.num}/48 × 2)</span></td><td class="r read-ink">${val.toFixed(2)}</td></tr>
        </tbody></table></div>`;
  }
  function renderGame(g) {
    const ev = evalGame(g);
    const hfa = g.neutral ? 0 : HFA;
    const mk = marketSpread(g);
    const w = played(g) ? winner(g) : undefined;
    const led = S.ledger.picks[g.id];
    $app.innerHTML = `
      <a class="back" href="#/w/${g.season}/${g.week}">‹ ${weekName(g.week)}, ${g.season}</a>
      <div class="matchup"><h1>${g.away} @ ${g.home}</h1><span class="muted">${kickoff(g)}${g.stadium ? " · " + esc(g.stadium) : ""}${g.neutral ? " · neutral site" : ""}</span>
        ${played(g) ? `<span class="result ${w === null ? "tie" : w === ev.pick ? "win" : "loss"}">Final ${g.away} ${g.away_score}, ${g.home} ${g.home_score}</span>` : ""}</div>
      <div class="panel pickp">
        <h2>Combined pick: ${ev.pick} ${esc(tname(ev.pick))} · ${pct(ev.conf)}</h2>
        <dl class="kv">
          <dt>Strength + home</dt><dd>${g.home} ${pct(g.p_elo)} · ${g.away} ${pct(1 - g.p_elo)} → ${ev.strengthPick}</dd>
          <dt class="read-ink">Readings lean</dt><dd class="read-ink">${g.home} ${pct(ev.pRead)} · ${g.away} ${pct(1 - ev.pRead)} → ${ev.badge === "even" ? "even" : ev.fav}</dd>
          <dt>Readings influence</dt><dd>${S.settings.influence} → λ = ${ev.lam.toFixed(3)}</dd>
          <dt>Combined</dt><dd>${g.home} ${pct(ev.pHome)} · ${g.away} ${pct(1 - ev.pHome)}</dd>
          <dt>Spread</dt><dd>Model ${modelSpread(g)} · Market ${mk || "—"} ${marketDisagrees(g, ev) ? `<span class="flag">⚑ disagree</span>` : ""}</dd>
          ${led ? `<dt>Ledger</dt><dd>Saved pick ${led.pick} ${pct(led.conf)} (${led.source}${led.outcome ? ", " + led.outcome : ""})</dd>` : ""}
        </dl>
        <div class="formula">pHome = sigmoid(logit(${g.p_elo.toFixed(4)}) + ${ev.lam.toFixed(3)} × ${ev.od.toFixed(3)}) = ${ev.pHome.toFixed(4)}</div>
      </div>
      <div class="panel">
        <h2>Strength rating</h2>
        <dl class="kv">
          <dt>${g.home} (home)</dt><dd>${g.elo_home.toFixed(1)} · ${g.rec_home}</dd>
          <dt>${g.away} (away)</dt><dd>${g.elo_away.toFixed(1)} · ${g.rec_away}</dd>
          <dt>Home field</dt><dd>${hfa ? "+" + hfa : "0 (neutral site)"}</dd>
          <dt>Difference</dt><dd>${sgn(g.diff)} rating points → ${modelSpread(g)}</dd>
        </dl>
        <div class="formula">diff = ${g.elo_home.toFixed(1)} + ${hfa} − ${g.elo_away.toFixed(1)} = ${g.diff.toFixed(1)}; pElo = 1/(1+10^(−diff/400)) = ${g.p_elo.toFixed(4)}</div>
      </div>
      <div class="panel read">
        <h2>Your readings</h2>
        <div class="chips"><span class="chip">Game day ${g.gnums.day}</span><span class="chip">Game life path ${g.gnums.life_path}</span><span class="chip">Year of the ${g.gnums.animal}</span><span class="chip">${badgeText(ev)}</span></div>
        <div class="muted small">oDiff = ${ev.rh.toFixed(2)} − ${ev.ra.toFixed(2)} = ${sgn(ev.od, 2)} (positive favors ${g.home})</div>
      </div>
      <div class="cols">
        <div class="panel read">${readingsTable(g, "away", ev)}</div>
        <div class="panel read">${readingsTable(g, "home", ev)}</div>
      </div>`;
  }

  // ---------------------------------------------------------------- ledger
  function rec(list) {
    const d = list.filter(e => e.outcome === "win" || e.outcome === "loss");
    const w = d.filter(e => e.outcome === "win").length;
    return { w, l: d.length - w, hit: d.length ? w / d.length : null };
  }
  function tile(label, r, cls = "") {
    return `<div class="tile ${cls}"><span>${label}</span><b>${pct(r.hit)}</b><em>${r.w}–${r.l}</em></div>`;
  }
  function renderLedger(season) {
    const all = Object.values(S.ledger.picks);
    const seasons = [...new Set(all.map(e => e.season))].sort();
    if (!seasons.includes(season) && seasons.length) season = seasons[seasons.length - 1];
    const list = all.filter(e => e.season === season).sort((a, b) => b.week - a.week || a.gameday.localeCompare(b.gameday));
    const weeks = [...new Set(list.map(e => e.week))];
    const body = weeks.map(w => {
      const ws = list.filter(e => e.week === w), r = rec(ws);
      return `<tr><th colspan="7">${weekName(w)}${r.w + r.l ? ` · ${r.w}–${r.l}` : ""}</th></tr>` + ws.map(e => `
        <tr><td><a href="#/g/${e.id}">${e.away} @ ${e.home}</a></td><td class="pick-ink"><b>${e.pick}</b></td><td class="r">${pct(e.conf)}</td>
        <td class="read-ink">${e.readings === "agree" ? "agree" : e.readings === "even" ? "even" : "favor " + e.readings_fav}</td>
        <td>${e.score || "—"}</td>
        <td>${e.outcome ? `<span class="result ${e.outcome}">${e.outcome === "win" ? "✓" : e.outcome === "loss" ? "✗" : "Tie"}</span>` : "pending"}</td>
        <td class="muted small">${e.source === "backfill" ? "backfilled" : e.source}</td></tr>`).join("");
    }).join("");
    const nBack = list.filter(e => e.source === "backfill").length;
    $app.innerHTML = `
      <div class="weekbar"><h1>Ledger<small>${season} season to date</small></h1>
        <div class="seg"><select id="ls">${seasons.map(s => `<option ${s === season ? "selected" : ""}>${s}</option>`).join("")}</select></div></div>
      <div class="tiles">
        ${tile("All picks", rec(list))}
        ${tile("80%+ picks", rec(list.filter(e => e.conf >= 0.8)))}
        ${tile("Readings agreed", rec(list.filter(e => e.readings === "agree")), "read")}
        ${tile("Readings disagreed", rec(list.filter(e => e.readings === "favor")), "read")}
        ${tile("Readings even", rec(list.filter(e => e.readings === "even")), "read")}
      </div>
      ${nBack ? `<p class="note">${nBack} picks are marked “backfilled”: they were recorded after the fact for weeks before the ledger started (or weeks you didn't refresh). They use only results available before each kickoff, so there's no hindsight, but they weren't saved in advance.</p>` : ""}
      <div class="panel tablewrap"><table>
        <thead><tr><th>Game</th><th>Pick</th><th class="r">Conf.</th><th>Readings</th><th>Score</th><th>Result</th><th>Saved</th></tr></thead>
        <tbody>${body || `<tr><td colspan="7" class="muted">No picks yet. Run a refresh.</td></tr>`}</tbody></table></div>`;
    const sel = document.getElementById("ls"); if (sel) sel.onchange = e => (location.hash = "#/ledger/" + e.target.value);
  }

  // ---------------------------------------------------------------- backtest
  function backtestSeason(season, s) {
    const P_HOME = 1 / (1 + Math.pow(10, -HFA / 400));
    const mk = () => ({ w: 0, l: 0, b: 0 });
    const add = (st, ph, hw) => { ((ph >= 0.5) === hw ? st.w++ : st.l++); st.b += (ph - (hw ? 1 : 0)) ** 2; };
    const strat = { home: mk(), readings: mk(), strength: mk(), combined: mk() };
    const buckets = { "50–59": mk(), "60–69": mk(), "70–79": mk(), "80+": mk() };
    const agr = { agree: mk(), disagree: mk(), even: mk() };
    for (const g of S.app.games) {
      if (g.season !== season || !played(g) || g.home_score === g.away_score) continue;
      const hw = g.home_score > g.away_score, ev = evalGame(g, s);
      strat.home[hw ? "w" : "l"]++; strat.home.b += ((g.neutral ? 0.5 : P_HOME) - (hw ? 1 : 0)) ** 2;
      add(strat.readings, ev.pRead, hw); add(strat.strength, g.p_elo, hw); add(strat.combined, ev.pHome, hw);
      const c = ev.conf; add(buckets[c >= 0.8 ? "80+" : c >= 0.7 ? "70–79" : c >= 0.6 ? "60–69" : "50–59"], ev.pHome, hw);
      const k = Math.abs(ev.od) < 1e-9 ? "even" : ((ev.od > 0) === (g.p_elo >= 0.5) ? "agree" : "disagree");
      add(agr[k], g.p_elo, hw);
    }
    return { strat, buckets, agr };
  }
  function btRow(label, st, showBrier = true) {
    const n = st.w + st.l;
    return `<tr><td>${label}</td><td class="r">${st.w}–${st.l}</td><td class="r">${n ? pct(st.w / n) : "—"}</td>${showBrier ? `<td class="r">${n ? (st.b / n).toFixed(4) : "—"}</td>` : ""}</tr>`;
  }
  function renderBacktest() {
    const s = S.settings;
    const seasons = Object.keys(S.app.weeks).map(Number).filter(se => S.app.games.some(g => g.season === se && played(g)));
    const blocks = seasons.map(se => {
      const r = backtestSeason(se, s);
      const tuned = se === 2024 ? "tuned on this season" : "out of sample";
      return `<div class="panel">
        <h2>${se}${se === S.app.current.season ? " (to date)" : ""} <span class="muted small">· ${tuned}</span></h2>
        <div class="tablewrap"><table><thead><tr><th>Strategy</th><th class="r">Record</th><th class="r">Hit rate</th><th class="r">Brier</th></tr></thead><tbody>
          ${btRow("Always pick the home team", r.strat.home)}
          ${btRow('<span class="read-ink">Readings only (pRead)</span>', r.strat.readings)}
          ${btRow('<span class="pick-ink">Strength + home field</span>', r.strat.strength)}
          ${btRow(`Strength + home + readings <span class="muted small">(influence ${s.influence}, astro ${s.w_astro}, num ${s.w_num})</span>`, r.strat.combined)}
        </tbody></table></div>
        <div class="cols" style="margin-top:12px">
          <div class="tablewrap"><table><thead><tr><th>Confidence (current setting)</th><th class="r">Record</th><th class="r">Hit rate</th></tr></thead><tbody>
            ${Object.entries(r.buckets).map(([k, v]) => btRow(k + "%", v, false)).join("")}</tbody></table></div>
          <div class="tablewrap"><table><thead><tr><th>Strength pick when readings…</th><th class="r">Record</th><th class="r">Hit rate</th></tr></thead><tbody>
            ${btRow('<span class="read-ink">agree</span>', r.agr.agree, false)}${btRow('<span class="read-ink">disagree</span>', r.agr.disagree, false)}${btRow('<span class="read-ink">are even</span>', r.agr.even, false)}</tbody></table></div>
        </div></div>`;
    }).join("");
    $app.innerHTML = `
      <div class="weekbar"><h1>Backtest<small>ties excluded · playoffs included</small></h1></div>
      <p class="note">The strength settings (start 1505, K 25, home field 30) were tuned on 2024, so 2024 numbers flatter the model. Judge it on seasons it wasn't tuned on: 2025 and 2026. Brier score is the average squared error of the probability (lower is better; always saying 50% scores 0.25). “Always home” uses the home-field-only probability (${pct(1 / (1 + Math.pow(10, -HFA / 400)))}) for its Brier score.</p>
      ${blocks}`;
  }

  // ---------------------------------------------------------------- settings
  let saveTimer = null;
  function renderSettings() {
    const s = S.settings;
    const slider = (key, label, help, cls = "") => `<div class="slider ${cls}"><label for="${key}">${label}<output id="${key}-o">${s[key]}</output></label>
      <input type="range" id="${key}" min="0" max="100" step="1" value="${s[key]}"><p>${help}</p></div>`;
    $app.innerHTML = `
      <div class="weekbar"><h1>Settings</h1></div>
      <div class="panel">
        ${slider("influence", "Readings influence", "0 = strength + home field only (the default, because readings didn't improve accuracy in testing). At 100, λ = 0.3 per point of readings difference.", "inf")}
        ${slider("w_astro", "Astrology weight", "Weight of the team animal vs. year animal score.")}
        ${slider("w_num", "Numerology weight", "Weight of the six weighted number comparisons.")}
        <div class="seg"><button id="reset">Reset to defaults (0 / 25 / 75)</button><span class="muted small" id="saved" style="align-self:center"></span></div>
      </div>
      <p class="note">The slate, game pages and backtest update as soon as you move a slider. The ledger saves picks with whatever settings are here when you run the weekly refresh.</p>`;
    const save = () => {
      clearTimeout(saveTimer);
      saveTimer = setTimeout(async () => {
        if (S.hosted) {
          try { localStorage.setItem("oracle-settings", JSON.stringify(S.settings)); document.getElementById("saved").textContent = "Saved on this device. Ledger picks use config/settings.json in the repo."; }
          catch (e) { document.getElementById("saved").textContent = "Couldn't save on this device."; }
          return;
        }
        try {
          const r = await fetch("api/settings", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(S.settings) });
          document.getElementById("saved").textContent = r.ok ? "Saved." : "Couldn't save (is the app running with make run?)";
        } catch (e) { document.getElementById("saved").textContent = "Couldn't save (is the app running with make run?)"; }
      }, 300);
    };
    ["influence", "w_astro", "w_num"].forEach(k => {
      const el = document.getElementById(k);
      el.oninput = () => { S.settings[k] = +el.value; document.getElementById(k + "-o").textContent = el.value; save(); };
    });
    document.getElementById("reset").onclick = () => { S.settings = { influence: 0, w_astro: 25, w_num: 75 }; renderSettings(); save(); };
  }

  window.addEventListener("hashchange", route);
  load().then(ok => ok && route());
})();
