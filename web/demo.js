/* Scripted demo tour — open the site with ?demo=1 to auto-play (used to record the < 3 min video).
 * Captions are rendered on top of the live app; every step drives the real UI and real Amazon Location calls. */
(() => {
  "use strict";
  if (!new URLSearchParams(location.search).has("demo")) return;

  const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
  const $ = (s) => document.querySelector(s);

  const css = document.createElement("style");
  css.textContent = `
    .demo-cap { position: fixed; left: 50%; bottom: 46px; transform: translateX(-50%); z-index: 30; max-width: min(860px, calc(100vw - 480px));
      margin-left: -200px; background: #0d0e0fe8; border: 1px solid #3a3f45; border-left: 4px solid #e8502d; border-radius: 12px;
      padding: 14px 20px; font: 500 21px/1.45 "Zen Kaku Gothic New", sans-serif; color: #ece6da; box-shadow: 0 12px 40px #000c;
      opacity: 0; transition: opacity .35s, transform .35s; }
    .demo-cap.on { opacity: 1; }
    .demo-cap b { color: #e8502d; font-weight: 700; }
    .demo-cap code { font: 600 17px "Azeret Mono", monospace; color: #d9a441; }
    .demo-card { position: fixed; inset: 0; z-index: 40; display: grid; place-items: center; background: radial-gradient(circle at 50% 40%, #1d2023f2, #0b0c0df8);
      opacity: 0; transition: opacity .6s; pointer-events: none; }
    .demo-card.on { opacity: 1; }
    .demo-card .in { text-align: center; color: #ece6da; font-family: "Zen Kaku Gothic New", sans-serif; max-width: 1100px; padding: 0 40px; }
    .demo-card h1 { font: 800 76px/1.05 "Shippori Mincho B1", serif; margin: 0 0 14px; }
    .demo-card h1 span { color: #e8502d; }
    .demo-card p { font-size: 26px; color: #cfc8ba; margin: 8px 0; }
    .demo-card .k { font: 600 20px "Azeret Mono", monospace; color: #d9a441; margin-top: 26px; }
    .demo-arch { display: grid; grid-template-columns: repeat(5, 1fr); gap: 14px; align-items: stretch; margin-top: 28px; text-align: left; }
    .demo-arch div { border: 1px solid #3a3f45; border-radius: 14px; padding: 14px; background: #141618; font-size: 16px; line-height: 1.45; color: #cfc8ba; position: relative; }
    .demo-arch div b { display: block; font: 700 17px "Zen Kaku Gothic New"; color: #ece6da; margin-bottom: 6px; }
    .demo-arch div i { font-style: normal; color: #e8502d; font: 600 13px "Azeret Mono", monospace; display: block; margin-bottom: 6px; }
    .demo-arch div:not(:last-child)::after { content: "→"; position: absolute; right: -14px; top: 40%; color: #e8502d; font-size: 20px; }
  `;
  document.head.appendChild(css);
  const cap = Object.assign(document.createElement("div"), { className: "demo-cap" });
  const card = Object.assign(document.createElement("div"), { className: "demo-card" });
  document.body.append(cap, card);

  async function say(html, ms) {
    cap.classList.remove("on"); await sleep(250);
    cap.innerHTML = html; cap.classList.add("on");
    if (ms) await sleep(ms);
  }
  async function show(html, ms) {
    card.innerHTML = `<div class="in">${html}</div>`; card.classList.add("on");
    await sleep(ms); card.classList.remove("on"); await sleep(600);
  }
  const fly = (center, zoom, duration = 2500) => MP.map.flyTo({ center, zoom, duration, essential: true });
  const byId = (id) => MP.S.all.find((f) => f.properties.id === id);

  async function tour() {
    const { S, map } = MP;
    await sleep(800);
    // 0:00 title
    await show(`<h1>Manhole Pilgrim <span>蓋めぐり</span></h1>
      <p>Japan hid its sewers underground, then printed them as trading cards.</p>
      <p>Here is where to collect all <b>1,313</b>.</p>
      <div class="k">Amazon Location Service · Apache Iceberg on Amazon S3</div>`, 5500);

    // 0:06 context
    await say("Since 2016, Japan's sewer agencies have turned their decorated manhole covers into <b>free collectible cards</b>.", 5500);
    await say("The catch: you can't buy or trade them. You have to <b>show up in person</b> at one specific counter.", 5500);
    await say("We took the official registry (47 prefectures, free-text Japanese addresses, no coordinates) and geocoded every counter with <b>Amazon Location Places</b>.", 7000);

    // 0:25 timeline
    await say("Ten years of releases in fifteen seconds. Each new series glows as it lands.");
    MP.startPlay();
    await sleep(800);
    await say("April 2016, <b>Series 1</b>: 30 cards.", 5000);
    await say("Every few months, a new series. Small towns, islands, mountain villages…", 6500);
    while (S.playing) await sleep(200);
    await say("<b>29 series, 1,313 cards, all 47 prefectures.</b>", 3500);

    // 0:48 popup
    const tokyo = byId("13-100-A-01") || S.all[0];
    fly(tokyo.geometry.coordinates, 13, 2600); await sleep(2800);
    MP.openPopup([tokyo]);
    await say("Click any card for the design, where to pick it up, opening hours, and a link to the official page.", 6500);
    MP.closePopup();

    // 0:57 sewer filter
    MP.resetFilters(); S.ptypes = new Set(["sewer"]); MP.syncChips(); MP.render();
    fly([137.6, 37.2], 4.6, 2000); await sleep(1500);
    await say("Filter by where you pick them up. <b>1 in 5 cards</b> is only handed out at a <b>sewage or water plant</b>. The cards pull people into infrastructure they never see.", 7500);
    MP.resetFilters(); MP.render();

    // 1:06 planner – Kyoto
    MP.selectTab($("#t-plan"));
    await say("Now the real question: <b>how many can I collect this weekend?</b>", 3500);
    $("#start-q").value = "京都駅";
    const kyoto = await (async () => {
      const r = await fetch(`https://places.geo.${window.MP_CONFIG.region}.amazonaws.com/v2/search-text?key=${encodeURIComponent(window.MP_CONFIG.apiKey)}`,
        { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ QueryText: "京都駅", BiasPosition: [135.76, 34.99], Filter: { IncludeCountries: ["JPN"] }, Language: "ja", MaxResults: 1 }) });
      return (await r.json()).ResultItems[0];
    })();
    document.querySelector('input[name="budget"][value="3600"]').checked = true;
    await MP.setOrigin(kyoto.Position, kyoto.Title);
    await sleep(1200);
    await say(`From Kyoto Station, <b>Amazon Location CalculateIsolines</b> draws the real 1-hour drive area: <b>${S.reach.length} cards</b> inside it.`, 7000);
    await MP.planRoute(); await sleep(1500);
    await say("<b>OptimizeWaypoints</b> orders the six nearest into a loop, with arrival times. Every stop is a real counter you can walk up to.", 8000);

    // 1:30 Sapporo fallback
    $("#start-q").value = "札幌駅";
    document.querySelector('input[name="budget"][value="7200"]').checked = true;
    await MP.setOrigin([141.35075, 43.06859], "札幌駅"); await sleep(1000);
    await MP.planRoute(); await sleep(1500);
    await say("Some starts, like the inside of Sapporo Station, can't be driven back to. The app falls back to a <b>route matrix + 2-opt</b> one-way plan, still using real drive times.", 8500);

    // 1:45 discoveries
    MP.resetFilters(); MP.render(); MP.selectTab($("#t-discover"));
    await say("And the map revealed things we didn't expect.", 3000);
    S.insights[3].go(); await sleep(2600);
    await say("The <b>loneliest card</b> in Japan: Ogasawara, <b>898 km</b> from any other, a 24-hour ferry from Tokyo.", 6500);
    MP.closePopup();
    S.insights[4].go(); await sleep(2300);
    await say("A <b>Hyōgo</b> card you can only get in <b>Osaka</b>. Our geocoder flagged it as an error. It wasn't: the plant sits across the border.", 7500);
    MP.closePopup();
    S.insights[6].go(); await sleep(1800);
    await say("98 cards wait at <b>michi-no-eki</b> roadside stations. Manhole cards are a road-trip game.", 5500);
    MP.resetFilters(); MP.render();

    // 2:12 architecture
    cap.classList.remove("on");
    await show(`<h1 style="font-size:52px">How it works</h1>
      <div class="demo-arch">
        <div><i>SOURCE</i><b>GKP registry</b>47 prefecture pages, scraped politely and cached</div>
        <div><i>AMAZON LOCATION</i><b>Places</b>Geocode + SearchText<br>IntendedUse = Storage<br>1,304 / 1,313 precise</div>
        <div><i>ICEBERG ON S3</i><b>Athena MERGE</b>1 snapshot per series<br>time travel: <code style="font-size:13px">FOR VERSION AS OF</code></div>
        <div><i>AWS AMPLIFY</i><b>GeoJSON export</b>static site on CloudFront, no backend</div>
        <div><i>AMAZON LOCATION</i><b>Maps + Routes</b>Isolines · OptimizeWaypoints · RouteMatrix · Routes</div>
      </div>
      <div class="k">Swap the scraper, keep the rest: temple stamps, station stamps, dam cards…</div>`, 11000);

    // 2:24 iceberg time travel callout
    MP.selectTab($("#t-explore"));
    S.series = 1; $("#series").value = 1; MP.render(); fly([137.6, 37.2], 4.6, 1500);
    await say("Every series is an <b>Iceberg snapshot</b>. <code>SELECT … FOR VERSION AS OF</code> series 1 → 30 cards. Re-scrapes MERGE in changes, so history is never lost.", 7500);
    S.series = S.maxSeries; $("#series").value = S.maxSeries; MP.render();

    // 2:33 outro
    cap.classList.remove("on");
    await show(`<h1>Manhole Pilgrim <span>蓋めぐり</span></h1>
      <p>Go find the sewers.</p>
      <div class="k">main.d1y4wxk0wltj16.amplifyapp.com<br>github.com/cnusergroup/manhole-pilgrim</div>`, 6500);
    window.__demoDone = true;
  }

  window.addEventListener("mp:ready", () => tour().catch((e) => { console.error(e); window.__demoDone = "error: " + e.message; }), { once: true });
})();
