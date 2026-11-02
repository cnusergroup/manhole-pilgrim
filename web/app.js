/* Manhole Pilgrim — 蓋めぐり
 * 前端：MapLibre GL + Amazon Location Service (Maps / Places / Routes v2, API Key 鉴权)
 */
(() => {
  "use strict";
  const CFG = window.MP_CONFIG;
  const KEY = encodeURIComponent(CFG.apiKey);
  const R = CFG.region;
  const API = {
    style: `https://maps.geo.${R}.amazonaws.com/v2/styles/${CFG.mapStyle}/descriptor?key=${KEY}&color-scheme=${CFG.colorScheme}`,
    searchText: `https://places.geo.${R}.amazonaws.com/v2/search-text?key=${KEY}`,
    isolines: `https://routes.geo.${R}.amazonaws.com/v2/isolines?key=${KEY}`,
    optimize: `https://routes.geo.${R}.amazonaws.com/v2/optimize-waypoints?key=${KEY}`,
    routes: `https://routes.geo.${R}.amazonaws.com/v2/routes?key=${KEY}`,
    matrix: `https://routes.geo.${R}.amazonaws.com/v2/route-matrix?key=${KEY}`,
  };

  const PTYPES = {
    sewer:     { label: "Sewage & water plants", color: "#e8502d" },
    tourist:   { label: "Tourist info",          color: "#e6b44c" },
    community: { label: "Community centers",     color: "#bdb6a8" },
    museum:    { label: "Museums & heritage",    color: "#c792ea" },
    roadside:  { label: "Michi-no-eki",          color: "#9ccc65" },
    cityhall:  { label: "City halls",            color: "#64b5f6" },
    park:      { label: "Parks & sports",        color: "#4dd0c1" },
    shop:      { label: "Shops",                 color: "#a1887f" },
    station:   { label: "Stations",              color: "#f48fb1" },
    onsen:     { label: "Onsen",                 color: "#ff8a80" },
    library:   { label: "Libraries",             color: "#ffd180" },
    other:     { label: "Other",                 color: "#78909c" },
  };

  const $ = (s) => document.querySelector(s);
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmtInt = (n) => n.toLocaleString("en-US");
  const toast = (msg, ms = 3200) => {
    const t = $("#toast"); t.textContent = msg; t.classList.add("show");
    clearTimeout(toast._t); toast._t = setTimeout(() => t.classList.remove("show"), ms);
  };
  const km = ([lon1, lat1], [lon2, lat2]) => {
    const r = Math.PI / 180, dLat = (lat2 - lat1) * r, dLon = (lon2 - lon1) * r;
    const h = Math.sin(dLat / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(dLon / 2) ** 2;
    return 12742 * Math.asin(Math.sqrt(h));
  };
  const fmtDur = (s) => { const h = Math.floor(s / 3600), m = Math.round((s % 3600) / 60); return h ? (m ? `${h} h ${m} min` : `${h} h`) : `${m} min`; };
  const fmtTime = (iso) => iso ? new Date(iso).toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Tokyo" }) : "";

  async function post(url, body) {
    const res = await fetch(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`${res.status} ${(await res.text()).slice(0, 160)}`);
    return res.json();
  }

  // 射线法点在多边形内（支持 MultiPolygon，含洞）
  function inRing(pt, ring) {
    let inside = false;
    for (let i = 0, j = ring.length - 1; i < ring.length; j = i++) {
      const [xi, yi] = ring[i], [xj, yj] = ring[j];
      if ((yi > pt[1]) !== (yj > pt[1]) && pt[0] < ((xj - xi) * (pt[1] - yi)) / (yj - yi) + xi) inside = !inside;
    }
    return inside;
  }
  const inPolys = (pt, polys) => polys.some((rings) => inRing(pt, rings[0]) && !rings.slice(1).some((h) => inRing(pt, h)));

  // ---------------- state ----------------
  const S = {
    all: [], seriesDate: {}, maxSeries: 29,
    series: 29, ptypes: new Set(Object.keys(PTYPES)), pref: "", q: "", hideEnded: false,
    origin: null, originLabel: "", iso: null, reach: null, picking: false, playing: null,
  };

  // ---------------- map ----------------
  const map = new maplibregl.Map({
    container: "map", style: API.style, center: [137.6, 37.2], zoom: 4.6, minZoom: 3.5, maxZoom: 17,
    attributionControl: { compact: true }, hash: false,
  });
  map.addControl(new maplibregl.NavigationControl({ visualizePitch: false }), "bottom-left");
  map.addControl(new maplibregl.ScaleControl({ unit: "metric" }), "bottom-left");

  const empty = { type: "FeatureCollection", features: [] };
  let originMarker = null, stopMarkers = [];

  map.on("load", async () => {
    const gj = await fetch(`data/cards.geojson?v=${encodeURIComponent(CFG.dataVersion || "")}`).then((r) => r.json());
    S.all = gj.features;
    for (const f of S.all) {
      const p = f.properties;
      if (p.series && (!S.seriesDate[p.series] || p.issued < S.seriesDate[p.series])) S.seriesDate[p.series] = p.issued;
    }
    S.maxSeries = Math.max(...S.all.map((f) => f.properties.series || 0));
    S.series = S.maxSeries;
    $("#series").max = S.maxSeries; $("#series").value = S.maxSeries;
    $("#total").textContent = fmtInt(S.all.length);

    map.addSource("iso", { type: "geojson", data: empty });
    map.addLayer({ id: "iso-fill", type: "fill", source: "iso", paint: { "fill-color": "#3fa796", "fill-opacity": 0.13 } });
    map.addLayer({ id: "iso-line", type: "line", source: "iso", paint: { "line-color": "#3fa796", "line-width": 2, "line-dasharray": [2, 1.5] } });

    map.addSource("route", { type: "geojson", data: empty });
    map.addLayer({ id: "route-casing", type: "line", source: "route", layout: { "line-join": "round", "line-cap": "round" }, paint: { "line-color": "#000", "line-width": 7, "line-opacity": 0.6 } });
    map.addLayer({ id: "route", type: "line", source: "route", layout: { "line-join": "round", "line-cap": "round" }, paint: { "line-color": "#d9a441", "line-width": 3.5 } });

    map.addSource("cards", { type: "geojson", data: empty });
    const colorExpr = ["match", ["get", "ptype"], ...Object.entries(PTYPES).flatMap(([k, v]) => [k, v.color]), "#78909c"];
    map.addLayer({
      id: "cards-glow", type: "circle", source: "cards", filter: ["==", ["get", "isNew"], true],
      paint: {
        "circle-color": "#e8502d", "circle-blur": 0.9, "circle-opacity": 0.85,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 12, 10, 26],
      },
    });
    map.addLayer({
      id: "cards", type: "circle", source: "cards",
      paint: {
        "circle-color": colorExpr,
        "circle-radius": ["interpolate", ["linear"], ["zoom"], 4, 3.2, 8, 5.5, 12, 9, 15, 12],
        "circle-stroke-color": "#0d0e0f",
        "circle-stroke-width": ["interpolate", ["linear"], ["zoom"], 4, 0.8, 12, 2.5],
        "circle-opacity": ["case", ["==", ["get", "dim"], true], 0.18, ["==", ["get", "ended"], true], 0.45, 1],
        "circle-stroke-opacity": ["case", ["==", ["get", "dim"], true], 0.2, 1],
      },
    });
    // 高缩放时显示“井盖”内环
    map.addLayer({
      id: "cards-core", type: "circle", source: "cards", minzoom: 9,
      filter: ["!=", ["get", "dim"], true],
      paint: { "circle-color": "#0d0e0f", "circle-radius": ["interpolate", ["linear"], ["zoom"], 9, 1.5, 15, 4] },
    });

    buildControls();
    buildInsights();
    render();

    // 数据血缘：本页数据导出自哪个 Iceberg snapshot
    fetch(`data/lake.json?v=${encodeURIComponent(CFG.dataVersion || "")}`).then((r) => (r.ok ? r.json() : null)).then((lake) => {
      if (!lake?.latest) return;
      $("#lake").innerHTML = `<br>Served from Iceberg table <code>${esc(lake.table)}</code> · ${lake.snapshots} snapshots · latest ${esc(lake.latest.committed_at.slice(0, 16))} UTC`;
    }).catch(() => {});
  });

  // ---------------- filtering / render ----------------
  function matches(p) {
    if (p.series > S.series) return false;
    if (!S.ptypes.has(p.ptype)) return false;
    if (S.pref && p.pref !== S.pref) return false;
    if (S.hideEnded && p.ended) return false;
    if (S.q) {
      const hay = `${p.pref} ${p.muni} ${p.place} ${p.address} ${p.code} ${p.id}`.toLowerCase();
      if (!hay.includes(S.q)) return false;
    }
    return true;
  }

  function visible() { return S.all.filter((f) => matches(f.properties)); }

  function render() {
    if (S.iso) recomputeReach();
    const vis = visible();
    const reachIds = S.reach ? new Set(S.reach.map((f) => f.properties.id)) : null;
    const feats = vis.map((f) => ({
      type: "Feature", geometry: f.geometry,
      properties: { ...f.properties, isNew: f.properties.series === S.series, dim: reachIds ? !reachIds.has(f.properties.id) : false },
    }));
    map.getSource("cards")?.setData({ type: "FeatureCollection", features: feats });
    $("#visible-count").textContent = fmtInt(vis.length);
    $("#series-num").textContent = S.series;
    $("#series-date").textContent = S.seriesDate[S.series] || "";
    document.querySelectorAll("#spark i").forEach((el, i) => {
      el.classList.toggle("on", i + 1 < S.series); el.classList.toggle("now", i + 1 === S.series);
    });
  }

  function buildControls() {
    // spark：每弾新增卡数
    const per = {};
    S.all.forEach((f) => (per[f.properties.series] = (per[f.properties.series] || 0) + 1));
    const mx = Math.max(...Object.values(per));
    $("#spark").innerHTML = Array.from({ length: S.maxSeries }, (_, i) =>
      `<i style="height:${Math.max(8, (100 * (per[i + 1] || 0)) / mx)}%" title="Series ${i + 1}: ${per[i + 1] || 0} cards"></i>`).join("");

    $("#series").addEventListener("input", (e) => { stopPlay(); S.series = +e.target.value; render(); });
    $("#play").addEventListener("click", () => (S.playing ? stopPlay() : startPlay()));

    // place type chips
    const counts = {};
    S.all.forEach((f) => (counts[f.properties.ptype] = (counts[f.properties.ptype] || 0) + 1));
    const box = $("#ptype-chips");
    Object.entries(PTYPES).sort((a, b) => (counts[b[0]] || 0) - (counts[a[0]] || 0)).forEach(([k, v]) => {
      const b = document.createElement("button");
      b.type = "button"; b.className = "chip"; b.dataset.k = k; b.setAttribute("aria-pressed", "true");
      b.innerHTML = `<span class="dot" style="background:${v.color}"></span>${esc(v.label)} <span class="n">${counts[k] || 0}</span>`;
      b.addEventListener("click", (e) => {
        // Alt/Shift + 点击 = 只看这一类
        if (e.shiftKey || e.altKey) { S.ptypes = new Set([k]); }
        else if (S.ptypes.has(k)) S.ptypes.delete(k); else S.ptypes.add(k);
        syncChips(); recomputeReach(); render();
      });
      box.appendChild(b);
    });
    const hint = document.createElement("p"); hint.className = "hint"; hint.textContent = "Shift-click a chip to show only that type.";
    box.appendChild(hint);

    // pref select
    const prefs = [...new Map(S.all.map((f) => [f.properties.pref_code, f.properties.pref])).entries()].sort();
    const pc = {}; S.all.forEach((f) => (pc[f.properties.pref] = (pc[f.properties.pref] || 0) + 1));
    $("#pref").insertAdjacentHTML("beforeend", prefs.map(([, n]) => `<option value="${esc(n)}">${esc(n)} (${pc[n]})</option>`).join(""));
    $("#pref").addEventListener("change", (e) => { S.pref = e.target.value; recomputeReach(); render(); if (S.pref) fitTo(visible()); });

    let qt;
    $("#q").addEventListener("input", (e) => {
      clearTimeout(qt); qt = setTimeout(() => { S.q = e.target.value.trim().toLowerCase(); recomputeReach(); render(); }, 180);
    });
    $("#q").addEventListener("keydown", (e) => { if (e.key === "Enter") fitTo(visible()); });
    $("#hide-ended").addEventListener("change", (e) => { S.hideEnded = e.target.checked; recomputeReach(); render(); });

    // tabs
    const tabs = [...document.querySelectorAll('[role="tab"]')];
    tabs.forEach((t, i) => {
      t.addEventListener("click", () => selectTab(t));
      t.addEventListener("keydown", (e) => {
        if (e.key === "ArrowRight" || e.key === "ArrowLeft") {
          const n = tabs[(i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length]; n.focus(); selectTab(n);
        }
      });
    });

    // planner
    $("#start-form").addEventListener("submit", async (e) => {
      e.preventDefault();
      const q = $("#start-q").value.trim(); if (!q) return;
      try {
        const r = await post(API.searchText, { QueryText: q, BiasPosition: map.getCenter().toArray(), Filter: { IncludeCountries: ["JPN"] }, Language: "ja", MaxResults: 1 });
        const it = r.ResultItems?.[0];
        if (!it) return toast("No place found. Try a station name.");
        setOrigin(it.Position, it.Title);
      } catch (err) { toast("Place search failed: " + err.message); }
    });
    $("#pick-on-map").addEventListener("click", () => { S.picking = true; document.body.classList.add("picking"); toast("Click the map to set your start point"); });
    document.querySelectorAll('input[name="budget"]').forEach((r) => r.addEventListener("change", () => S.origin && runIsoline()));
    $("#stops").addEventListener("input", (e) => ($("#stops-n").textContent = e.target.value));
    $("#plan-route").addEventListener("click", planRoute);

    // map interactions
    map.on("mouseenter", "cards", () => (map.getCanvas().style.cursor = "pointer"));
    map.on("mouseleave", "cards", () => (map.getCanvas().style.cursor = ""));
    map.on("click", (e) => {
      if (S.picking) {
        S.picking = false; document.body.classList.remove("picking");
        setOrigin(e.lngLat.toArray(), `${e.lngLat.lat.toFixed(4)}, ${e.lngLat.lng.toFixed(4)}`);
        return;
      }
      const fs = map.queryRenderedFeatures(e.point, { layers: ["cards"] }).filter((f) => !f.properties.dim);
      if (fs.length) openPopup(fs.map((f) => S.all.find((a) => a.properties.id === f.properties.id)).filter(Boolean));
    });
  }

  function selectTab(t) {
    document.querySelectorAll('[role="tab"]').forEach((x) => {
      const on = x === t; x.setAttribute("aria-selected", on); x.tabIndex = on ? 0 : -1;
      document.getElementById(x.getAttribute("aria-controls")).hidden = !on;
    });
  }

  function syncChips() {
    document.querySelectorAll(".chip").forEach((c) => c.setAttribute("aria-pressed", S.ptypes.has(c.dataset.k)));
  }

  function fitTo(feats, maxZoom = 11) {
    if (!feats.length) return toast("No cards match.");
    const b = new maplibregl.LngLatBounds();
    feats.forEach((f) => b.extend(f.geometry.coordinates));
    map.fitBounds(b, { padding: { top: 90, bottom: 60, left: 60, right: 430 }, maxZoom, duration: 1200 });
  }

  // ---------------- timeline ----------------
  function startPlay() {
    selectTab($("#t-explore"));
    $("#play").setAttribute("aria-pressed", "true"); $("#play").textContent = "❚❚ Pause";
    if (S.series >= S.maxSeries) S.series = 0;
    map.flyTo({ center: [137.6, 37.2], zoom: 4.6, duration: 800 });
    S.playing = setInterval(() => {
      S.series += 1; $("#series").value = S.series; render();
      if (S.series >= S.maxSeries) stopPlay();
    }, 520);
  }
  function stopPlay() {
    if (!S.playing) return;
    clearInterval(S.playing); S.playing = null;
    $("#play").setAttribute("aria-pressed", "false"); $("#play").textContent = "▶ Play 2016→2026";
    render();
  }

  // ---------------- popup ----------------
  let popup = null;
  function openPopup(list, idx = 0) {
    const f = list[idx], p = f.properties;
    const pt = PTYPES[p.ptype] || PTYPES.other;
    const official = `https://www.gk-p.jp/mhcard/?pref=${p.pref_code === "00" ? "13" : p.pref_code}#mhcard_result`;
    const html = `
      <article class="pop">
        <div class="img">${p.image ? `<img src="${esc(p.image)}" alt="Manhole card design for ${esc(p.muni)}" loading="lazy" referrerpolicy="no-referrer" />` : ""}</div>
        <div class="body">
          <h3>${esc(p.muni)}${p.ended ? '<span class="badge ended">ENDED</span>' : p.series === S.maxSeries ? '<span class="badge">NEW</span>' : ""}</h3>
          <div class="meta">${esc(p.pref)} · <b>Series ${p.series}</b> · ${esc(p.issued)} · ${esc(p.code || p.id)}</div>
          <div class="place"><span style="color:${pt.color}">●</span> ${esc(p.place || "—")}
            <small>${esc(p.address || "")}${p.precision !== "address" ? ` · located by ${p.precision === "poi" ? "place search" : "city centroid"}` : ""}</small>
            ${p.hours ? `<small>🕘 ${esc(p.hours.slice(0, 140))}</small>` : ""}
          </div>
          <div class="acts">
            <a href="${official}" target="_blank" rel="noopener">Official info ↗</a>
            <button type="button" data-act="start">Start trip here</button>
            ${list.length > 1 ? `<button type="button" data-act="next">${idx + 1}/${list.length} ▸</button>` : ""}
          </div>
        </div>
      </article>`;
    popup?.remove();
    popup = new maplibregl.Popup({ offset: 12, maxWidth: "300px", focusAfterOpen: true }).setLngLat(f.geometry.coordinates).setHTML(html).addTo(map);
    const el = popup.getElement();
    el.querySelector('[data-act="start"]').addEventListener("click", () => { popup.remove(); selectTab($("#t-plan")); setOrigin(f.geometry.coordinates, `${p.muni} · ${p.place || ""}`); });
    el.querySelector('[data-act="next"]')?.addEventListener("click", () => openPopup(list, (idx + 1) % list.length));
  }

  // ---------------- planner ----------------
  function setOrigin(pos, label) {
    S.origin = pos; S.originLabel = label;
    $("#start-q").value = label;
    originMarker?.remove();
    const el = document.createElement("div");
    el.style.cssText = "width:22px;height:22px;border-radius:50%;background:#ece6da;border:4px solid #141618;box-shadow:0 0 0 3px #3fa796,0 4px 14px #000";
    el.setAttribute("aria-label", "Trip start");
    originMarker = new maplibregl.Marker({ element: el }).setLngLat(pos).addTo(map);
    clearRoute();
    return runIsoline();
  }

  async function runIsoline() {
    const t = +document.querySelector('input[name="budget"]:checked').value;
    $("#reach").innerHTML = `<p>Computing ${fmtDur(t)} drive area with Amazon Location…</p>`;
    $("#plan-route").disabled = true;
    try {
      const r = await post(API.isolines, { Origin: S.origin, Thresholds: { Time: [t] }, TravelMode: "Car", IsolineGeometryFormat: "Simple" });
      // 吸附到道路网的起点；车站等 POI 坐标可能在建筑内部，直接用于路线计算会失败
      S.snapped = r.SnappedOrigin || S.origin;
      const polys = r.Isolines.flatMap((iso) => iso.Geometries.map((g) => g.Polygon || g.MultiPolygon).filter(Boolean));
      S.iso = polys;
      map.getSource("iso").setData({ type: "Feature", geometry: { type: "MultiPolygon", coordinates: polys }, properties: {} });
      clearRoute();
      recomputeReach(); render();
      const b = new maplibregl.LngLatBounds();
      polys.forEach((p) => p[0].forEach((c) => b.extend(c)));
      map.fitBounds(b, { padding: { top: 80, bottom: 50, left: 50, right: 420 }, duration: 1100 });
    } catch (err) {
      $("#reach").innerHTML = ""; toast("Isoline failed: " + err.message);
    }
  }

  function recomputeReach() {
    if (!S.iso) { S.reach = null; return; }
    S.reach = visible().filter((f) => inPolys(f.geometry.coordinates, S.iso));
    const t = +document.querySelector('input[name="budget"]:checked').value;
    const n = S.reach.length;
    const bySeries = new Set(S.reach.map((f) => f.properties.muni)).size;
    const sewer = S.reach.filter((f) => f.properties.ptype === "sewer").length;
    $("#reach").innerHTML = `<span class="big">${n}</span>
      <p>cards within a <b>${fmtDur(t)}</b> drive of ${esc(S.originLabel)}, from <b>${bySeries}</b> municipalities${sewer ? ` · ${sewer} handed out at sewage plants` : ""}.</p>`;
    $("#plan-route").disabled = n < 1;
  }

  function clearRoute() {
    map.getSource("route")?.setData(empty);
    stopMarkers.forEach((m) => m.remove()); stopMarkers = [];
    $("#itinerary").innerHTML = "";
  }

  /* 决定访问顺序。
   * 1) Amazon Location OptimizeWaypoints（环线，回到起点）
   * 2) 失败时：CalculateRouteMatrix 取真实驾车时间 → 最近邻 + 2-opt（单程，起点固定）
   * 返回 { order: picks 的下标数组, loop, method, times: { depart, arrive[] } } */
  async function orderStops(origin, picks) {
    const now = Date.now();
    try {
      const opt = await post(API.optimize, {
        Origin: origin, Destination: origin, TravelMode: "Car",
        Waypoints: picks.map((f, i) => ({ Id: String(i), Position: f.geometry.coordinates })),
      });
      const ws = opt.OptimizedWaypoints.filter((w) => /^\d+$/.test(w.Id));
      const o = opt.OptimizedWaypoints.find((w) => w.Id === "Origin");
      return {
        order: ws.map((w) => +w.Id), loop: true, method: "Amazon Location OptimizeWaypoints",
        times: { depart: o?.DepartureTime, arrive: ws.map((w) => w.ArrivalTime || w.DepartureTime) },
      };
    } catch (err) {
      console.warn("OptimizeWaypoints failed, falling back to route matrix:", err.message);
    }
    const pts = [origin, ...picks.map((f) => f.geometry.coordinates)].map((p) => ({ Position: p }));
    const m = await post(API.matrix, { Origins: pts, Destinations: pts, TravelMode: "Car", RoutingBoundary: { Unbounded: true } });
    const D = m.RouteMatrix.map((row) => row.map((c) => (c.Duration ?? Infinity)));
    const n = picks.length;
    // 最近邻
    const path = [0], left = new Set(Array.from({ length: n }, (_, i) => i + 1));
    while (left.size) {
      const cur = path.at(-1);
      let best = null;
      for (const j of left) if (best === null || D[cur][j] < D[cur][best]) best = j;
      path.push(best); left.delete(best);
    }
    // 2-opt（起点固定，单程）
    const cost = (p) => p.slice(1).reduce((s, v, i) => s + D[p[i]][v], 0);
    let improved = true;
    while (improved) {
      improved = false;
      for (let i = 1; i < path.length - 1; i++) {
        for (let k = i + 1; k < path.length; k++) {
          const cand = [...path.slice(0, i), ...path.slice(i, k + 1).reverse(), ...path.slice(k + 1)];
          if (cost(cand) < cost(path)) { path.splice(0, path.length, ...cand); improved = true; }
        }
      }
    }
    let t = 0;
    const arrive = path.slice(1).map((v, i) => { t += D[path[i]][v]; return new Date(now + t * 1000).toISOString(); });
    return {
      order: path.slice(1).map((v) => v - 1), loop: false,
      method: "Amazon Location route matrix + 2-opt",
      times: { depart: new Date(now).toISOString(), arrive },
    };
  }

  async function planRoute() {
    if (!S.reach?.length) return;
    const want = +$("#stops").value;
    // 最近优先，同一坐标只取一次
    const seen = new Set(), picks = [];
    for (const f of [...S.reach].sort((a, b) => km(S.origin, a.geometry.coordinates) - km(S.origin, b.geometry.coordinates))) {
      const k = f.geometry.coordinates.join(",");
      // 跳过已停发的卡和只定位到市町村中心的近似点
      if (seen.has(k) || f.properties.ended || f.properties.precision === "municipality") continue;
      seen.add(k); picks.push(f);
      if (picks.length >= want) break;
    }
    if (!picks.length) return toast("No active cards in range.");
    const btn = $("#plan-route"); btn.disabled = true; btn.textContent = "Optimizing with Amazon Location…";
    try {
      const origin = S.snapped || S.origin;
      const plan = await orderStops(origin, picks);
      const ordered = plan.order.map((i) => picks[i]);
      const times = plan.times;
      let route;
      try {
        if (!plan.loop) throw new Error("open");
        route = (await post(API.routes, {
          Origin: origin, Destination: origin, TravelMode: "Car", LegGeometryFormat: "Simple",
          Waypoints: ordered.map((f) => ({ Position: f.geometry.coordinates })),
        })).Routes[0];
      } catch {
        // 起点不可作为终点时，改为单程：起点 → … → 最后一张卡
        plan.loop = false;
        route = (await post(API.routes, {
          Origin: origin, Destination: ordered.at(-1).geometry.coordinates, TravelMode: "Car", LegGeometryFormat: "Simple",
          Waypoints: ordered.slice(0, -1).map((f) => ({ Position: f.geometry.coordinates })),
        })).Routes[0];
      }
      const coords = route.Legs.flatMap((l) => l.Geometry?.LineString || []);
      map.getSource("route").setData({ type: "Feature", geometry: { type: "LineString", coordinates: coords }, properties: {} });

      stopMarkers.forEach((m) => m.remove()); stopMarkers = [];
      ordered.forEach((f, i) => {
        const el = document.createElement("div");
        el.textContent = i + 1;
        el.style.cssText = "width:24px;height:24px;border-radius:50%;background:#d9a441;color:#111;display:grid;place-items:center;font:600 12px 'Azeret Mono',monospace;border:2px solid #111;box-shadow:0 3px 10px #000";
        stopMarkers.push(new maplibregl.Marker({ element: el }).setLngLat(f.geometry.coordinates).addTo(map));
      });

      const sum = route.Summary || {};
      $("#itinerary").innerHTML =
        `<li class="origin"><div>${esc(S.originLabel)}<div class="t">depart ${fmtTime(times.depart)}</div></div></li>` +
        ordered.map((f, i) => {
          const p = f.properties;
          return `<li data-i="${i}"><div><b>${esc(p.muni)}</b> · Series ${p.series}<div class="t">${esc(p.place || "")} · arrive ${fmtTime(times.arrive[i])}</div></div></li>`;
        }).join("") +
        `<li class="sum">${plan.loop ? "Loop" : "One way"}: ${(sum.Distance / 1000).toFixed(1)} km · ${fmtDur(sum.Duration)} driving · ${ordered.length} cards<br><span class="t">ordered by ${plan.method}</span></li>`;
      $("#itinerary").querySelectorAll("li[data-i]").forEach((li) =>
        li.addEventListener("click", () => { const f = ordered[+li.dataset.i]; map.flyTo({ center: f.geometry.coordinates, zoom: 14 }); openPopup([f]); }));
      const b = new maplibregl.LngLatBounds(); coords.forEach((c) => b.extend(c));
      map.fitBounds(b, { padding: { top: 80, bottom: 50, left: 50, right: 420 }, duration: 1100 });
    } catch (err) {
      toast("Route failed: " + err.message);
    } finally {
      btn.disabled = false; btn.textContent = "Plan optimal pilgrimage route";
    }
  }

  // ---------------- discoveries ----------------
  function resetFilters() {
    stopPlay();
    S.series = S.maxSeries; $("#series").value = S.maxSeries;
    S.ptypes = new Set(Object.keys(PTYPES)); syncChips();
    S.pref = ""; $("#pref").value = ""; S.q = ""; $("#q").value = "";
    // 清掉行程规划的可达圈与路线，避免卡片保持变暗
    S.iso = null; S.reach = null; map.getSource("iso").setData(empty); clearRoute();
    originMarker?.remove(); originMarker = null; S.origin = null;
    $("#reach").innerHTML = ""; $("#plan-route").disabled = true;
  }

  function buildInsights() {
    const all = S.all, N = all.length;
    const sewer = all.filter((f) => f.properties.ptype === "sewer");
    const prefCount = {}; all.forEach((f) => (prefCount[f.properties.pref] = (prefCount[f.properties.pref] || 0) + 1));
    const [topPref, topN] = Object.entries(prefCount).sort((a, b) => b[1] - a[1])[0];
    const s1 = all.filter((f) => f.properties.series === 1);
    const road = all.filter((f) => f.properties.ptype === "roadside");
    const crossBorder = all.find((f) => f.properties.geo_pref && f.properties.geo_pref !== f.properties.pref && f.properties.pref_code !== "00");
    // 最孤独的卡：离最近的另一张卡最远
    let lonely = null, lonelyD = 0;
    for (const a of all) {
      let best = Infinity;
      for (const b of all) { if (a === b) continue; const d = km(a.geometry.coordinates, b.geometry.coordinates); if (d < best) best = d; }
      if (best > lonelyD) { lonelyD = best; lonely = a; }
    }
    // 同一地点最多卡
    const byPt = {}; all.forEach((f) => (byPt[f.geometry.coordinates.join()] ||= []).push(f));
    const crowd = Object.values(byPt).sort((a, b) => b.length - a.length)[0];

    const items = [
      { k: `1 in ${Math.round(N / sewer.length)}`, t: `cards (${sewer.length} in total) can only be picked up at a sewage or water plant. The cards exist to pull people into infrastructure they never see.`, s: "Shows sewage & water plants only",
        go: () => { resetFilters(); S.ptypes = new Set(["sewer"]); syncChips(); render(); fitTo(sewer, 6); } },
      { k: `${s1.length} → ${fmtInt(N)}`, t: `Series 1 launched in April 2016 with ${s1.length} cards. Watch ten years of releases spread across every prefecture.`, s: "Plays the timeline",
        go: () => { resetFilters(); startPlay(); } },
      { k: `${topN}`, t: `cards in ${topPref}, the most of any prefecture.`, s: `Filters to ${topPref}`,
        go: () => { resetFilters(); S.pref = topPref; $("#pref").value = topPref; render(); fitTo(visible()); } },
      { k: `${Math.round(lonelyD)} km`, t: `to the next nearest card: ${lonely.properties.muni} (${lonely.properties.pref}) is the loneliest card in Japan.`, s: "Flies there",
        go: () => { resetFilters(); render(); map.flyTo({ center: lonely.geometry.coordinates, zoom: 8, duration: 2200 }); setTimeout(() => openPopup([lonely]), 2300); } },
      crossBorder && { k: "Wrong prefecture?", t: `A ${crossBorder.properties.pref} card you can only get in ${crossBorder.properties.geo_pref}: ${crossBorder.properties.place}, a ${crossBorder.properties.pref} facility that sits across the border.`, s: "Flies there",
        go: () => { resetFilters(); render(); map.flyTo({ center: crossBorder.geometry.coordinates, zoom: 12, duration: 2000 }); setTimeout(() => openPopup([crossBorder]), 2100); } },
      { k: `${crowd.length} cards`, t: `at a single counter: ${crowd[0].properties.place} (${crowd[0].properties.pref}). The most efficient stop in the country.`, s: "Flies there",
        go: () => { resetFilters(); render(); map.flyTo({ center: crowd[0].geometry.coordinates, zoom: 13, duration: 2000 }); setTimeout(() => openPopup(crowd), 2100); } },
      { k: `${road.length}`, t: `cards wait at michi-no-eki roadside stations. Japan's manhole cards are a road-trip game.`, s: "Shows roadside stations only",
        go: () => { resetFilters(); S.ptypes = new Set(["roadside"]); syncChips(); render(); fitTo(road, 6); } },
    ].filter(Boolean);

    S.insights = items;
    $("#insights").innerHTML = items.map((it, i) => `<li><button type="button" data-i="${i}"><span class="k">${esc(it.k)}</span>${esc(it.t)}<small>→ ${esc(it.s)}</small></button></li>`).join("");
    $("#insights").querySelectorAll("button").forEach((b) => b.addEventListener("click", () => { popup?.remove(); items[+b.dataset.i].go(); }));
    window.dispatchEvent(new Event("mp:ready"));
  }

  // 供 demo.js（?demo=1 自动演示）调用的最小接口
  window.MP = {
    S, map, PTYPES, render, selectTab, syncChips, fitTo, resetFilters, startPlay, stopPlay,
    setOrigin, planRoute, openPopup: (fs) => openPopup(fs), closePopup: () => popup?.remove(),
    visible,
  };
})();
