/* Chartmeter — homepage, auth, dashboard. Vanilla JS, no build step. */
(function () {
  "use strict";

  var home = document.getElementById("home");
  var appEl = document.getElementById("app");
  var main = document.getElementById("page");
var shell = document.getElementById("main");
  var modal = document.getElementById("modal");
  var modalBody = document.getElementById("modal-body");
  var modalTitle = document.getElementById("modal-title");
  var view = "overview";
  var cache = {};
  var session = { signed_in: false, user: null };

  // ------------------------------------------------------------- utils
  function api(path, opts) {
    return fetch("/api" + path, opts).then(function (r) {
      return r.json().then(function (b) { if (!r.ok) throw b; return b; });
    });
  }
  function post(path, data) {
    return api(path, {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data || {})
    });
  }
  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }
  function metricVal(key, v) {
    if (v == null || v === "") return "—";
    if (key === "crossborder_listener_share") return Math.round(v * 100) + "%";
    return typeof v === "number" ? v.toLocaleString() : esc(v);
  }
  function pct(p) {
    if (p == null || !isFinite(p)) return "—";
    return (p > 0 ? "+" : "") + Math.round(p) + "%";
  }
  function toast(msg, isErr) {
    var t = document.getElementById("toast");
    t.textContent = msg;
    t.className = "toast show" + (isErr ? " err" : "");
    clearTimeout(t._t);
    t._t = setTimeout(function () { t.className = "toast"; }, 3000);
  }
  function tierPill(t) {
    var cls = t === "upcoming" ? "up" : t === "mid" ? "mid" : "asp";
    var l = t === "upcoming" ? "Upcoming" : t === "mid" ? "Mid-level" : "Aspirational";
    return '<span class="pill ' + cls + '">' + l + "</span>";
  }
  function errBox(errors) {
    return '<div class="errs"><strong>Could not continue:</strong><ul>' +
      errors.map(function (e) { return "<li>" + esc(e) + "</li>"; }).join("") + "</ul></div>";
  }
  function demoBanner(on) {
    if (!on) return "";
    return '<div class="demo-banner"><span><strong>Demo workspace.</strong> ' +
      "You're exploring sample data. Create an account to track your own artist.</span>" +
      '<button class="btn sm" data-auth="signup">Create account</button></div>';
  }

  // ------------------------------------------------------------- auth UI
  function openAuth(mode, errors) {
    var isSignup = mode === "signup";
    modalTitle.textContent = isSignup ? "Create your account" : "Sign in";
    modalBody.innerHTML =
      (errors ? errBox(errors) : "") +
      '<form id="af">' +
        '<div class="field"><label>Email</label>' +
          '<input name="email" type="email" required autocomplete="email"></div>' +
        '<div class="field"><label>Password</label>' +
          '<input name="password" type="password" required minlength="8" ' +
          'autocomplete="' + (isSignup ? "new-password" : "current-password") + '">' +
          (isSignup ? '<div class="hint">At least 8 characters.</div>' : "") + "</div>" +
        (isSignup ?
          '<div class="field"><label>Artist name</label><input name="artist_name" required></div>' +
          '<div class="form-grid">' +
            '<div class="field"><label>City</label><input name="city" placeholder="Kampala"></div>' +
            '<div class="field"><label>Country</label><select name="country">' +
              ["UG", "KE", "TZ", "RW", "Other"].map(function (c) {
                return '<option>' + c + "</option>"; }).join("") + "</select></div>" +
          "</div>" +
          '<div class="field"><label>Subgenre</label>' +
            '<select name="subgenre">' +
            ["luganda-pop", "regional-afrobeats", "ea-amapiano", "dancehall-reggae",
             "kidandali", "gengetone", "bongo-flava", "afro-house"].map(function (g) {
              return "<option>" + g + "</option>"; }).join("") + "</select>" +
            '<div class="hint">You are only ever benchmarked against this exact subgenre.</div></div>'
          : "") +
        '<button class="btn lg" type="submit" style="width:100%;margin-top:6px">' +
          (isSignup ? "Create account" : "Sign in") + "</button>" +
      "</form>" +
      '<div class="auth-switch">' + (isSignup
        ? 'Already have an account? <button data-sw="login">Sign in</button>'
        : 'New here? <button data-sw="signup">Create an account</button>') + "</div>";

    modal.hidden = false;
    modalBody.querySelectorAll("[data-sw]").forEach(function (b) {
      b.onclick = function () { openAuth(b.getAttribute("data-sw")); };
    });
    document.getElementById("af").onsubmit = function (ev) {
      ev.preventDefault();
      var payload = {};
      new FormData(ev.target).forEach(function (v, k) { payload[k] = v; });
      post("/auth/" + (isSignup ? "signup" : "login"), payload)
        .then(function (r) {
          session = { signed_in: true, user: r.user };
          closeModal();
          toast(isSignup ? "Welcome to Chartmeter" : "Signed in");
          showApp();
          view = isSignup ? "connect" : "overview";
          syncNav();
          render();
        })
        .catch(function (e) { openAuth(mode, (e && e.errors) || ["Something went wrong."]); });
    };
  }
  function closeModal() { modal.hidden = true; modalBody.innerHTML = ""; }

  // ------------------------------------------------------------- views
  var views = {};

  views.overview = function () {
    return api("/overview").then(function (d) {
      var a = d.artist || {}, m = a.metrics || {}, c = d.counts;
      var linked = Object.keys(d.linked || {}).length;

      if (!linked && !m.monthly_listeners && !d.demo) {
        return demoBanner(false) +
          '<div class="page-head"><h1>Welcome, ' + esc(a.name || "") + "</h1>" +
          "<p>Two steps and your dashboard fills itself in.</p></div>" +
          '<div class="card"><div class="action"><div class="n">1</div><div>' +
          "<p><strong>Connect your platforms</strong></p>" +
          '<p class="sub">Paste your Spotify, Boomplay or YouTube artist links and sync.</p>' +
          '<div style="margin-top:10px"><button class="btn" data-go="connect">Connect platforms</button></div>' +
          "</div></div>" +
          '<div class="action"><div class="n">2</div><div>' +
          "<p><strong>Find your competition</strong></p>" +
          '<p class="sub">We shortlist acts in your subgenre and tier once your stats are in.</p>' +
          '<div style="margin-top:10px"><button class="ghost" data-go="discover">Find competition</button></div>' +
          "</div></div></div>";
      }

      var defs = (d.top_deficits || []).map(function (r, i) {
        return '<div class="action"><div class="n">' + (i + 1) + "</div><div>" +
          "<p><strong>" + esc(r.label) + '</strong> · <span class="pill def">' +
          pct(r.pct) + "</span></p>" +
          '<p class="sub">' + esc(r.action || "") + "</p></div></div>";
      }).join("") || '<p class="empty">No deficits — or no peer set yet.</p>';

      var surp = (d.top_surpluses || []).map(function (r) {
        return '<div class="action"><div class="n">★</div><div>' +
          "<p><strong>" + esc(r.label) + '</strong> · <span class="pill sur">' +
          pct(r.pct) + "</span></p>" +
          '<p class="sub">This is your wedge — over-invest here before fixing anything else.</p></div></div>';
      }).join("") || '<p class="empty">No surplus yet.</p>';

      return demoBanner(d.demo) +
        '<div class="page-head"><h1>' + esc(a.name || "Your artist") + "</h1><p>" +
        esc([a.city, a.country].filter(Boolean).join(", ")) +
        (a.subgenre ? " · " + esc(a.subgenre) : "") +
        (a.tier ? " · " + esc(a.tier) + " tier" : "") +
        (d.last_sync ? " · synced " + esc(d.last_sync) : "") + "</p></div>" +
        '<div class="grid g4">' +
          stat("Monthly listeners", metricVal("monthly_listeners", m.monthly_listeners), "manual — Spotify for Artists") +
          stat("Boomplay streams", metricVal("boomplay_streams", m.boomplay_streams), "auto — synced") +
          stat("DJ spins (30d)", metricVal("dj_spins_30d", m.dj_spins_30d), "manual — fieldwork") +
          stat("Platforms linked", String(linked), linked ? "syncing" : "none yet") +
        "</div>" +
        '<div class="grid g3" style="margin-top:13px">' +
          '<div class="card"><div class="scorewrap">' +
            ringHTML((d.cpp && d.cpp.score) || 0, "CPP score") +
            '<div class="catlist">' +
            Object.keys((d.cpp && d.cpp.categories) || {}).map(function (k) {
              return catBar(k, d.cpp.categories[k]); }).join("") +
            '<button class="ghost sm" data-go="cpp" style="margin-top:4px">View breakdown</button>' +
            "</div></div></div>" +
          '<div class="card"><div class="stat"><span class="k">Peer set</span><span class="v">' +
            c.peers + '</span><span class="s">of ' + c.competitors +
            " tracked acts match your tier + subgenre</span></div></div>" +
          '<div class="card"><div class="stat"><span class="k">Radar going cold</span><span class="v ' +
            (c.cold ? "bad" : "ok") + '">' + c.cold + '</span><span class="s">of ' + c.radar +
            " contacts untouched 30+ days</span></div></div>" +
        "</div>" +
        '<h2 class="sec">Highest-leverage deficits</h2><div class="card">' + defs + "</div>" +
        '<h2 class="sec">Your wedge</h2><div class="card">' + surp + "</div>" +
        '<h2 class="sec">Go deeper</h2><div class="grid g3">' +
        '<div class="card"><div class="stat"><span class="k">Auto SWOT</span>' +
        '<span class="s" style="margin:0 0 10px">Strengths, weaknesses, opportunities and ' +
        'threats derived from your gaps.</span></div>' +
        '<button class="ghost sm" data-go="swot">Open SWOT</button></div>' +
        '<div class="card"><div class="stat"><span class="k">Marketing plans</span>' +
        '<span class="s" style="margin:0 0 10px">Prioritised 30-day campaigns for your ' +
        'three biggest gaps.</span></div>' +
        '<button class="ghost sm" data-go="plans">Open plans</button></div>' +
        '<div class="card"><div class="stat"><span class="k">Head-to-head</span>' +
        '<span class="s" style="margin:0 0 10px">Bar-by-bar comparison against every ' +
        'matched peer.</span></div>' +
        '<button class="ghost sm" data-go="compare">Compare</button></div></div>';
    });
  };

  function stat(k, v, s) {
    return '<div class="card"><div class="stat"><span class="k">' + esc(k) +
      '</span><span class="v">' + v + '</span><span class="s">' + esc(s) + "</span></div></div>";
  }

  views.connect = function () {
    return api("/links").then(function (d) {
      var keys = Object.keys(d.links || {});
      var rows = keys.map(function (k) {
        var l = d.links[k];
        return '<div class="linkrow"><span class="plat">' + esc(l.label || k) + "</span>" +
          '<span class="id">' + esc(l.id) + "</span>" +
          '<span class="pill ' + (l.syncable ? "sur" : "par") + '">' +
            (l.syncable ? "syncable" : "no API") + "</span>" +
          '<button class="ghost sm danger" data-unlink="' + esc(k) + '">Remove</button></div>';
      }).join("") || '<p class="empty">No platforms linked yet.</p>';

      return demoBanner(d.demo) +
        '<div class="page-head"><h1>Connect platforms</h1>' +
        "<p>Paste your artist page links — one per line. We work out the IDs.</p></div>" +
        '<div class="card"><div class="field">' +
          "<label>Artist links</label>" +
          '<textarea id="urls" rows="5" placeholder="https://open.spotify.com/artist/...&#10;' +
            'https://www.boomplay.com/artists/...&#10;https://youtube.com/@yourhandle"></textarea>' +
          '<div class="hint">Supported: Spotify, Boomplay, YouTube, Last.fm, Audiomack, MusicBrainz.</div>' +
        "</div>" +
        '<div class="toolbar"><button class="btn" id="save-links">Save links</button>' +
        '<button class="ghost" id="do-sync">Sync stats now</button>' +
        (d.last_sync ? '<span class="tiny">Last synced ' + esc(d.last_sync) + "</span>" : "") +
        "</div></div>" +
        '<h2 class="sec">Linked platforms</h2><div class="card">' + rows + "</div>" +
        '<div id="sync-out"></div>';
    });
  };

  views.discover = function () {
    return api("/discover").then(function (d) {
      if (d.reason) {
        return '<div class="page-head"><h1>Find my competition</h1></div>' +
          '<div class="note bad">' + esc(d.reason) + "</div>" +
          '<button class="btn" data-go="connect">Connect platforms</button>';
      }
      var rows = d.suggestions.map(function (s) {
        return '<div class="sugg"><div class="score">' + Math.round(s.score) + "</div>" +
          '<div class="info"><strong>' + esc(s.name) + " " + tierPill(s.tier) + "</strong>" +
          "<span>" + esc([s.city, s.country].filter(Boolean).join(", ")) + " · " +
          esc(s.why) + "</span></div>" +
          '<button class="ghost sm" data-accept="' + esc(s.name) + '">Track</button></div>';
      }).join("");

      return '<div class="page-head"><h1>Find my competition</h1>' +
        "<p>Acts in <strong>" + esc(d.subgenre) + "</strong> at the <strong>" +
        esc(d.tier) + "</strong> tier, ranked by how close a benchmark they are to you.</p></div>" +
        '<div class="note info">Scores favour acts closest to your listener count and in your ' +
        "target markets. <strong>These are a shortlist to verify</strong>, not verified chart " +
        "data — confirm each act before trusting the comparison.</div>" +
        '<div class="toolbar"><button class="btn" id="accept-all">Track all shown</button></div>' +
        '<div class="card">' + (rows || '<p class="empty">No matches.</p>') + "</div>" +
        (d.rejected && d.rejected.length ?
          '<h2 class="sec">Filtered out (' + d.rejected.length + ")</h2>" +
          '<div class="card"><div class="tbl-wrap"><table><tbody>' +
          d.rejected.map(function (r) {
            return "<tr><td>" + esc(r.name) + '</td><td style="color:var(--mut)">' +
              esc(r.why) + "</td></tr>"; }).join("") +
          "</tbody></table></div></div>" : "");
    });
  };


  function ringHTML(score, label, color) {
    return '<div class="ring" style="--p:' + score + ';--c:' + (color || "var(--acc)") +
      '"><div class="in"><b>' + score + "</b><small>" + esc(label) + "</small></div></div>";
  }

  function catBar(name, val) {
    var c = val >= 66 ? "var(--ok)" : val >= 34 ? "var(--acc)" : "var(--bad)";
    return '<div class="catrow"><span class="cn">' + esc(name) + '</span>' +
      '<span class="cb"><i style="width:' + val + '%;background:' + c + '"></i></span>' +
      '<span class="cv">' + val + "</span></div>";
  }

  views.cpp = function () {
    return api("/cpp").then(function (d) {
      if (!d.peer_count) {
        return '<div class="page-head"><h1>Performance score</h1></div>' +
          '<div class="note bad">No matched peers yet — a percentile score needs a peer set.</div>' +
          '<button class="btn" data-go="discover">Find my competition</button>';
      }
      var cats = Object.keys(d.categories).map(function (k) {
        return catBar(k, d.categories[k]); }).join("");
      var rows = d.detail.map(function (r) {
        var c = r.percentile >= 66 ? "sur" : r.percentile >= 34 ? "par" : "def";
        return "<tr><td><strong>" + esc(r.label) + "</strong></td><td>" +
          '<span class="pill ' + c + '">' + r.percentile + "th pct</span></td>" +
          '<td style="width:45%"><div class="bar"><i style="width:' + r.percentile + '%"></i></div></td>' +
          '<td style="text-transform:capitalize;color:var(--mut)">' + esc(r.category) + "</td></tr>";
      }).join("");
      return '<div class="page-head"><h1>Cross-platform performance</h1>' +
        "<p>Your percentile against " + d.peer_count +
        " tier- and subgenre-matched peers, weighted toward active demand over raw audience size.</p></div>" +
        '<div class="card"><div class="card-b"><div class="scorewrap">' +
        ringHTML(d.score, "CPP score") +
        '<div class="catlist">' + cats +
        '<p class="tiny" style="margin:6px 0 0">Traction (DJ spins, short-form, radio) is ' +
        "weighted above Reach, because followers without rotation do not move this market.</p>" +
        "</div></div></div></div>" +
        '<h2 class="sec">Percentile by metric</h2>' +
        '<div class="card pad0"><div class="tbl-wrap"><table><thead><tr><th>Metric</th>' +
        "<th>Percentile</th><th></th><th>Category</th></tr></thead><tbody>" + rows +
        "</tbody></table></div></div>";
    });
  };

  views.swot = function () {
    return api("/swot").then(function (d) {
      if (!d.peer_count) {
        return '<div class="page-head"><h1>SWOT</h1></div>' +
          '<div class="note bad">SWOT is generated from your gaps against matched peers. ' +
          "Add competitors first.</div>" +
          '<button class="btn" data-go="discover">Find my competition</button>';
      }
      function block(items, cls, title, pill) {
        var body = items.map(function (x) {
          return '<div class="sw-item"><div class="h">' + esc(x.text) + "</div>" +
            (x.note ? '<div class="n">' + esc(x.note) + "</div>" : "") +
            (x.action ? '<div class="a">→ ' + esc(x.action) + "</div>" : "") + "</div>";
        }).join("") || '<p class="empty">Nothing detected.</p>';
        return '<div class="card ' + cls + ' pad0"><div class="card-h"><h3>' + esc(title) +
          '</h3><span class="pill ' + pill + '">' + items.length + "</span></div>" +
          '<div class="card-b">' + body + "</div></div>";
      }
      return demoBanner(d.demo) +
        '<div class="page-head"><h1>SWOT analysis</h1><p>Generated automatically from ' +
        esc(d.generated_from) + ". Every line cites the number that triggered it.</p></div>" +
        '<div class="swot">' +
        block(d.strengths, "s-card", "Strengths", "s") +
        block(d.weaknesses, "w-card", "Weaknesses", "w") +
        block(d.opportunities, "o-card", "Opportunities", "o") +
        block(d.threats, "t-card", "Threats", "t") +
        "</div>" +
        '<div class="note info">This updates itself every time your stats or peer set change — ' +
        "it is never a document you maintain by hand.</div>";
    });
  };

  views.plans = function () {
    return api("/plans").then(function (d) {
      if (!d.peer_count) {
        return '<div class="page-head"><h1>Marketing plans</h1></div>' +
          '<div class="note bad">Plans are built from your biggest gaps vs peers. Add competitors first.</div>' +
          '<button class="btn" data-go="discover">Find my competition</button>';
      }
      var html = demoBanner(d.demo) +
        '<div class="page-head"><h1>Marketing &amp; promotion plans</h1>' +
        "<p>Prioritised 30-day campaigns, generated from your largest gaps against the peer median.</p></div>";
      d.plans.forEach(function (p) {
        html += '<div class="card plan"><div class="card-b">' +
          '<div class="plan-h"><div class="pr">' + p.priority + "</div><div>" +
          "<h3>" + esc(p.title) + "</h3>" +
          '<p class="why">' + esc(p.why) + "</p></div></div>" +
          '<div class="trigger">Triggered by: ' + esc(p.trigger) + "</div>" +
          '<div class="weeks">' + p.weeks.map(function (w) {
            return '<div class="week"><h4>' + esc(w.label) + "</h4><ul>" +
              w.tasks.map(function (t) { return "<li>" + esc(t) + "</li>"; }).join("") +
              "</ul></div>";
          }).join("") + "</div>" +
          '<div class="kpi">Measure: <b>' + esc(p.kpi) + "</b></div>" +
          "</div></div>";
      });
      return html;
    });
  };

  views.compare = function () {
    return api("/compare").then(function (d) {
      if (!d.peers.length) {
        return '<div class="page-head"><h1>Head-to-head</h1></div>' +
          '<div class="note bad">No matched peers to compare against yet.</div>' +
          '<button class="btn" data-go="discover">Find my competition</button>';
      }
      var blocks = d.rows.filter(function (r) { return r.acts.length; }).map(function (r) {
        var all = r.acts.slice();
        if (typeof r.ours === "number") all.push({ name: d.artist, value: r.ours, me: true });
        all.sort(function (a, b) { return b.value - a.value; });
        var max = all[0] ? all[0].value : 1;
        return '<div class="card pad0"><div class="card-h"><h3>' + esc(r.label) + "</h3>" +
          '<span class="legend"><b style="background:var(--acc)"></b>' + esc(d.artist) +
          '<b style="background:#2b3a4d;margin-left:10px"></b>peers</span></div><div class="card-b">' +
          all.map(function (a) {
            return '<div class="cbar"><span class="nm' + (a.me ? " me" : "") + '">' +
              esc(a.name) + '</span><span class="tr"><i class="' + (a.me ? "me" : "") +
              '" style="width:' + (max ? (a.value / max * 100) : 0) + '%"></i></span>' +
              '<span class="vl">' + metricVal(r.key, a.value) + "</span></div>";
          }).join("") + "</div></div>";
      });
      return demoBanner(d.demo) +
        '<div class="page-head"><h1>Head-to-head</h1><p>You against each matched peer, ' +
        "metric by metric.</p></div>" +
        '<div class="grid g2">' + blocks.join("") + "</div>";
    });
  };

  views.gaps = function () {
    return api("/gaps").then(function (d) {
      if (!d.peer_count) {
        return demoBanner(d.demo) + '<div class="page-head"><h1>Gap analysis</h1></div>' +
          '<div class="note bad"><strong>No tier- and subgenre-matched peers yet.</strong> ' +
          "Comparing against acts in a different tier or subgenre produces misleading " +
          "numbers, so nothing is shown.</div>" +
          '<button class="btn" data-go="discover">Find my competition</button>';
      }
      var rows = d.rows.map(function (r) {
        var cls = r.read === "deficit" ? "def" : r.read === "surplus" ? "sur" : "par";
        var bars = "";
        if (r.median != null && r.best) {
          var scale = Math.max(r.ours || 0, r.median, r.best) || 1;
          bars = '<div class="cmp"><div class="lbl"><span>you</span><span>' +
            metricVal(r.key, r.ours) + '</span></div><div class="bar"><i class="ours" style="width:' +
            ((r.ours || 0) / scale * 100) + '%"></i></div>' +
            '<div class="lbl"><span>peer median</span><span>' + metricVal(r.key, r.median) +
            '</span></div><div class="bar"><i class="med" style="width:' +
            (r.median / scale * 100) + '%"></i></div></div>';
        }
        return "<tr><td><strong>" + esc(r.label) + "</strong>" +
          (d.manual_only[r.key] ? '<br><span class="pill par" style="margin-top:4px">manual</span>' : "") +
          "</td><td>" + (bars || "—") + '</td><td class="num">' +
          (r.pct == null ? "—" : '<span class="pill ' + cls + '">' + pct(r.pct) + "</span>") +
          "</td><td>" + esc(r.action || "") + "</td></tr>";
      }).join("");
      return demoBanner(d.demo) +
        '<div class="page-head"><h1>Gap analysis</h1><p>' + esc(d.artist) +
        " vs the median of <strong>" + d.peer_count + "</strong> matched peers: " +
        esc(d.peers.join(", ")) + "</p></div>" +
        '<div class="note info">Measured against the peer <strong>median</strong>, never the ' +
        "maximum. Acts outside your tier or subgenre are excluded entirely.</div>" +
        '<div class="card pad0"><div class="tbl-wrap"><table><thead><tr><th>Dimension</th>' +
        '<th>You vs peer median</th><th class="num">Delta</th><th>Next action</th></tr></thead>' +
        "<tbody>" + rows + "</tbody></table></div></div>";
    });
  };

  views.competitors = function () {
    return api("/competitors").then(function (d) {
      cache.meta = d;
      var art = d.artist || {};
      var rows = d.competitors.map(function (c) {
        var m = c.metrics || {};
        var peer = c.subgenre === art.subgenre && c.tier === art.tier;
        return "<tr><td><strong>" + esc(c.name) + '</strong><br><span class="tiny">' +
          esc([c.city, c.country].filter(Boolean).join(", ")) + "</span></td><td>" +
          esc(c.subgenre || "—") + "</td><td>" + tierPill(c.tier) + '</td><td class="num">' +
          metricVal("monthly_listeners", m.monthly_listeners) + '</td><td class="num">' +
          metricVal("boomplay_streams", m.boomplay_streams) + '</td><td class="num">' +
          metricVal("dj_spins_30d", m.dj_spins_30d) + '</td><td><span class="pill ' +
          (peer ? "peer" : "tactics") + '">' + (peer ? "peer" : "tactics only") +
          '</span></td><td><button class="ghost sm danger" data-del="' + esc(c.name) +
          '">Remove</button></td></tr>';
      }).join("");
      return demoBanner(d.demo) +
        '<div class="page-head"><h1>Competitor matrix</h1><p>Only acts matching <strong>' +
        esc(art.subgenre || "your subgenre") + "</strong> and the <strong>" +
        esc(art.tier || "your") + "</strong> tier count as peers.</p></div>" +
        '<div class="toolbar"><button class="btn" id="add">+ Add competitor</button>' +
        '<button class="ghost" data-go="discover">Find my competition</button></div>' +
        '<div class="card pad0"><div class="tbl-wrap"><table><thead><tr><th>Act</th>' +
        '<th>Subgenre</th><th>Tier</th><th class="num">Listeners</th><th class="num">Boomplay</th>' +
        '<th class="num">DJ spins</th><th>Role</th><th></th></tr></thead><tbody>' +
        (rows || '<tr><td colspan="8" class="empty">No competitors yet.</td></tr>') +
        "</tbody></table></div></div>";
    });
  };

  views.radar = function () {
    return api("/radar").then(function (d) {
      if (!d.contacts.length) {
        return demoBanner(d.demo) + '<div class="page-head"><h1>DJ &amp; radio radar</h1></div>' +
          '<div class="note">Your radar is empty. It tracks FM stations, club DJs, ' +
          "tastemakers and promo networks across Kampala, Nairobi and Dar es Salaam.</div>";
      }
      var byCity = {};
      d.contacts.forEach(function (c) {
        (byCity[c.city || "Other"] = byCity[c.city || "Other"] || []).push(c);
      });
      var html = demoBanner(d.demo) + '<div class="page-head"><h1>DJ &amp; radio radar</h1>' +
        "<p>No contact is approached twice without an outcome logged.</p></div>";
      Object.keys(byCity).sort().forEach(function (city) {
        html += '<h2 class="sec">' + esc(city) + '</h2><div class="card pad0"><div class="tbl-wrap">' +
          "<table><thead><tr><th>Contact</th><th>Class</th><th>Genre</th><th>Route</th>" +
          '<th class="num">Last</th><th>Outcome</th></tr></thead><tbody>' +
          byCity[city].map(function (c) {
            return "<tr><td><strong>" + esc(c.name) + "</strong></td><td>" + esc(c.class) +
              "</td><td>" + esc(c.genre_lean || "") + "</td><td>" + esc(c.submission_route || "") +
              '</td><td class="num">' + (c.days == null ? "—" : c.days + "d") +
              ((c.days || 0) > 30 ? ' <span class="pill warn">cold</span>' : "") +
              "</td><td>" + esc(c.outcome || "") + "</td></tr>";
          }).join("") + "</tbody></table></div></div>";
      });
      return html;
    });
  };

  views.swipe = function () {
    return api("/swipe").then(function (d) {
      var items = d.entries.map(function (e) {
        return '<div class="swipe-item"><h4>' + esc(e.source) + " · " + esc(e.channel) +
          '</h4><div class="meta">' + esc(e.date) + " · " + esc(e.format || "") + " · " +
          esc(e.metrics || "") + "</div><div>" + esc(e.hook || "") +
          '</div><div class="prin">→ ' + esc(e.principle || "") + "</div></div>";
      }).join("") || '<p class="empty">No entries yet.</p>';
      return demoBanner(d.demo) + '<div class="page-head"><h1>Swipe file</h1>' +
        "<p>Campaigns worth stealing the mechanism from. Every entry needs a transferable " +
        "principle.</p></div><div class=\"card\">" + items + "</div>";
    });
  };

  views.sources = function () {
    return api("/providers").then(function (d) {
      var rows = d.providers.map(function (p) {
        return "<tr><td><strong>" + esc(p.name) + "</strong></td><td>" +
          (p.ready ? '<span class="pill sur">ready</span>'
                   : '<span class="pill par">needs ' + esc(p.missing.join(", ")) + "</span>") +
          "</td><td>" + p.metrics.map(function (m) {
            return "<code>" + esc(m) + "</code>"; }).join(" ") +
          "</td><td>" + esc(p.note) + "</td></tr>";
      }).join("");
      var manual = Object.keys(d.manual_only).map(function (k) {
        return "<tr><td><code>" + esc(k) + "</code></td><td>" + esc(d.manual_only[k]) + "</td></tr>";
      }).join("");
      return '<div class="page-head"><h1>Data sources</h1>' +
        "<p>What updates itself, and what will always need a human.</p></div>" +
        '<div class="note bad"><strong>Spotify monthly listeners are not available from any ' +
        "official API.</strong> Extended access requires 250,000+ monthly active users, which " +
        "excludes independent artists. We never fake or scrape this — enter it from Spotify " +
        "for Artists.</div>" +
        '<h2 class="sec">Automated providers</h2><div class="card pad0"><div class="tbl-wrap">' +
        "<table><thead><tr><th>Provider</th><th>Status</th><th>Fills</th><th>Notes</th></tr>" +
        "</thead><tbody>" + rows + "</tbody></table></div></div>" +
        '<h2 class="sec">Manual by design</h2><div class="note">These are the highest-signal ' +
        "metrics in this market, and no platform will ever hand them to you.</div>" +
        '<div class="card pad0"><div class="tbl-wrap"><table><thead><tr><th>Metric</th>' +
        "<th>Where it comes from</th></tr></thead><tbody>" + manual +
        "</tbody></table></div></div>";
    });
  };

  // ------------------------------------------------------------- add competitor
  function openAddForm(errors) {
    var meta = cache.meta || { metrics: [], artist: {} };
    var art = meta.artist || {};
    modalTitle.textContent = "Add competitor";
    modalBody.innerHTML = (errors ? errBox(errors) : "") +
      '<form id="cform"><div class="form-grid">' +
        '<div class="field"><label>Name *</label><input name="name" required></div>' +
        '<div class="field"><label>Subgenre</label><input name="subgenre" value="' +
          esc(art.subgenre || "") + '"><div class="hint">Must match yours to count as a peer.</div></div>' +
        '<div class="field"><label>City</label><input name="city"></div>' +
        '<div class="field"><label>Country</label><select name="country">' +
          ["UG", "KE", "TZ", "RW", "Other"].map(function (c) {
            return "<option>" + c + "</option>"; }).join("") + "</select></div>" +
        '<div class="field"><label>Tier</label><select name="tier">' +
          '<option value="">auto from listeners</option>' +
          '<option value="upcoming">Upcoming (0–20k)</option>' +
          '<option value="mid">Mid-level (20k–500k)</option>' +
          '<option value="aspirational">Aspirational (500k+)</option></select></div>' +
      "</div>" +
      '<h2 class="sec">Metrics</h2><div class="form-grid">' +
      meta.metrics.map(function (m) {
        return '<div class="field"><label>' + esc(m.label) + '</label><input name="m_' +
          esc(m.key) + '" type="number" step="any"></div>';
      }).join("") + "</div>" +
      '<h2 class="sec">SWOT</h2>' +
      '<div class="field"><label>Visual hooks</label><input name="visual_hooks"></div>' +
      '<div class="field"><label>Performance loop</label><input name="performance_loop"></div>' +
      '<div class="field"><label>Engagement drop-off</label><input name="dropoff"></div>' +
      '<div class="toolbar" style="margin-top:16px"><button class="btn" type="submit">Save</button>' +
      '<button class="ghost" type="button" id="cancel">Cancel</button></div></form>';
    modal.hidden = false;
    document.getElementById("cancel").onclick = closeModal;
    document.getElementById("cform").onsubmit = function (ev) {
      ev.preventDefault();
      var payload = { metrics: {} };
      new FormData(ev.target).forEach(function (v, k) {
        if (k.indexOf("m_") === 0) { if (v !== "") payload.metrics[k.slice(2)] = v; }
        else payload[k] = v;
      });
      post("/competitors", payload).then(function () {
        closeModal(); toast("Added " + payload.name); render();
      }).catch(function (e) { openAddForm((e && e.errors) || ["Unexpected error."]); });
    };
  }

  // ------------------------------------------------------------- render + wiring
  function updateTopbar() {
    api("/overview").then(function (d) {
      var a = d.artist || {};
      document.getElementById("t-name").textContent = a.name || "Your artist";
      document.getElementById("t-meta").textContent =
        [a.subgenre, a.tier ? a.tier + " tier" : "", d.last_sync ? "synced " + d.last_sync : ""]
          .filter(Boolean).join("  ·  ");
    }).catch(function () {});
  }

  function render() {
    main.innerHTML = '<div class="loading">Loading…</div>';
    views[view]().then(function (html) {
      main.innerHTML = html;
      updateTopbar();
      wire();
    }).catch(function (e) {
      main.innerHTML = '<div class="note bad">Failed to load. ' +
        esc((e && (e.error || e.message)) || e) + "</div>";
    });
  }

  function wire() {
    var add = document.getElementById("add");
    if (add) add.onclick = function () { openAddForm(); };

    main.querySelectorAll("[data-go]").forEach(function (b) {
      b.onclick = function () { view = b.getAttribute("data-go"); syncNav(); render(); };
    });
    main.querySelectorAll("[data-auth]").forEach(function (b) {
      b.onclick = function () { openAuth(b.getAttribute("data-auth")); };
    });
    main.querySelectorAll("[data-del]").forEach(function (b) {
      b.onclick = function () {
        var n = b.getAttribute("data-del");
        if (!confirm("Remove " + n + "?")) return;
        api("/competitors/" + encodeURIComponent(n), { method: "DELETE" })
          .then(function () { toast("Removed " + n); render(); })
          .catch(function () { toast("Could not remove", true); });
      };
    });
    main.querySelectorAll("[data-unlink]").forEach(function (b) {
      b.onclick = function () {
        post("/links/remove", { platform: b.getAttribute("data-unlink") })
          .then(function () { toast("Link removed"); render(); });
      };
    });
    main.querySelectorAll("[data-accept]").forEach(function (b) {
      b.onclick = function () {
        post("/discover/accept", { names: [b.getAttribute("data-accept")] })
          .then(function (r) {
            toast(r.added.length ? "Now tracking " + r.added.join(", ") : "Already tracked");
            render();
          });
      };
    });
    var all = document.getElementById("accept-all");
    if (all) all.onclick = function () {
      var names = Array.prototype.map.call(
        main.querySelectorAll("[data-accept]"),
        function (x) { return x.getAttribute("data-accept"); });
      post("/discover/accept", { names: names }).then(function (r) {
        toast("Now tracking " + r.added.length + " acts");
        view = "gaps"; syncNav(); render();
      });
    };

    var save = document.getElementById("save-links");
    if (save) save.onclick = function () {
      var text = document.getElementById("urls").value;
      if (!text.trim()) return toast("Paste at least one link", true);
      post("/links", { text: text }).then(function (r) {
        if (r.unknown && r.unknown.length) {
          toast("Not recognised: " + r.unknown.join(", "), true);
        } else {
          toast("Saved " + r.added.length + " link(s)");
        }
        render();
      });
    };

    var sync = document.getElementById("do-sync");
    if (sync) sync.onclick = function () {
      sync.disabled = true; sync.textContent = "Syncing…";
      post("/sync", {}).then(function (r) {
        var out = document.getElementById("sync-out");
        out.innerHTML = '<h2 class="sec">Sync results</h2><div class="card">' +
          r.results.map(function (x) {
            var cls = x.status === "ok" ? "sur" : x.status === "needs_key" ? "warn" : "def";
            return '<div class="res"><span class="st"><span class="pill ' + cls + '">' +
              esc(x.status) + '</span></span><span><strong>' + esc(x.label) +
              "</strong> — " + esc(x.detail) + "</span></div>";
          }).join("") + "</div>" +
          '<div class="note">Manual metrics (monthly listeners, DJ spins, WhatsApp list, ' +
          "radio adds) are never overwritten by a sync — no API provides them.</div>";
        toast(Object.keys(r.metrics).length + " metric(s) updated");
      }).catch(function (e) {
        toast((e && e.errors && e.errors[0]) || "Sync failed", true);
      }).then(function () {
        sync.disabled = false; sync.textContent = "Sync stats now";
      });
    };
  }

  function syncNav() {
    document.querySelectorAll("#nav button").forEach(function (b) {
      b.classList.toggle("active", b.getAttribute("data-view") === view);
    });
    location.hash = view;
  }

  function showApp() {
    home.hidden = true;
    appEl.hidden = false;
    var who = document.getElementById("who");
    var acct = document.getElementById("acct");
    if (session.signed_in) {
      who.textContent = session.user.artist_name || session.user.email;
      acct.innerHTML = '<div class="acct-line"><strong>' + esc(session.user.email) +
        '</strong></div><button class="ghost sm" id="logout" style="width:100%">Sign out</button>';
      document.getElementById("logout").onclick = function () {
        post("/auth/logout", {}).then(function () {
          session = { signed_in: false, user: null };
          showHome();
        });
      };
    } else {
      who.textContent = "Demo workspace";
      acct.innerHTML = '<button class="btn sm" data-auth="signup" style="width:100%">' +
        'Create account</button><button class="ghost sm" id="back-home" style="width:100%;' +
        'margin-top:7px">Back to homepage</button>';
      acct.querySelector("[data-auth]").onclick = function () { openAuth("signup"); };
      document.getElementById("back-home").onclick = showHome;
    }
  }

  function showHome() {
    appEl.hidden = true;
    home.hidden = false;
    location.hash = "";
  }

  document.getElementById("nav").addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-view]");
    if (!b) return;
    view = b.getAttribute("data-view");
    syncNav();
    render();
  });
  document.getElementById("t-sync").onclick = function () {
    var b = document.getElementById("t-sync");
    b.disabled = true; b.textContent = "Syncing…";
    post("/sync", {}).then(function (r) {
      var n = Object.keys(r.metrics || {}).length;
      toast(n ? n + " metric(s) updated" : "No new data — check platform keys");
      render();
    }).catch(function (e) {
      toast((e && e.errors && e.errors[0]) || "Add platform links first", true);
      view = "connect"; syncNav(); render();
    }).then(function () { b.disabled = false; b.textContent = "Sync stats"; });
  };

  document.getElementById("modal-close").onclick = closeModal;
  modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeModal(); });
  home.querySelectorAll("[data-auth]").forEach(function (b) {
    b.onclick = function () { openAuth(b.getAttribute("data-auth")); };
  });
  document.getElementById("try-demo").onclick = function () {
    view = "overview"; syncNav(); showApp(); render();
  };

  // boot
  api("/auth/session").then(function (s) {
    session = s;
    var h = (location.hash || "").replace("#", "");
    if (s.signed_in) {
      if (views[h]) view = h;
      syncNav(); showApp(); render();
    } else if (views[h]) {
      view = h; syncNav(); showApp(); render();
    } else {
      home.hidden = false;
    }
  }).catch(function () { home.hidden = false; });
})();
