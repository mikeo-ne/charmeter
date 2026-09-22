/* Chartmeter demo app — vanilla JS, no build step. */
(function () {
  "use strict";

  var main = document.getElementById("main");
  var modal = document.getElementById("modal");
  var modalBody = document.getElementById("modal-body");
  var modalTitle = document.getElementById("modal-title");
  var view = "overview";
  var cache = {};

  // ---------------------------------------------------------------- utils
  function api(path, opts) {
    return fetch("/api" + path, opts).then(function (r) {
      return r.json().then(function (body) {
        if (!r.ok) throw body;
        return body;
      });
    });
  }

  function esc(s) {
    return String(s == null ? "" : s).replace(/[&<>"']/g, function (c) {
      return { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c];
    });
  }

  function num(v) {
    if (v == null || v === "") return "—";
    if (typeof v !== "number") return esc(v);
    if (Math.abs(v) < 1 && v !== 0) return Math.round(v * 100) + "%";
    return v.toLocaleString();
  }

  function metricVal(key, v) {
    if (v == null) return "—";
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
    t._t = setTimeout(function () { t.className = "toast"; }, 2800);
  }

  function tierPill(t) {
    var cls = t === "upcoming" ? "up" : t === "mid" ? "mid" : "asp";
    var label = t === "upcoming" ? "Upcoming" : t === "mid" ? "Mid-level" : "Aspirational";
    return '<span class="pill ' + cls + '">' + label + "</span>";
  }

  function spinner() { main.innerHTML = '<div class="loading">Loading…</div>'; }

  // ---------------------------------------------------------------- views
  var views = {};

  views.overview = function () {
    return api("/overview").then(function (d) {
      var a = d.artist, c = d.counts;
      var m = a.metrics || {};
      var deficits = d.top_deficits.map(function (r, i) {
        return '<div class="action"><div class="n">' + (i + 1) + "</div><div>" +
          "<p><strong>" + esc(r.label) + "</strong> &middot; " +
          '<span class="pill def">' + pct(r.pct) + "</span></p>" +
          '<p class="sub">' + esc(r.action || "") + "</p></div></div>";
      }).join("") || '<p class="empty">No deficits against the peer median.</p>';

      var surplus = d.top_surpluses.map(function (r) {
        return '<div class="action"><div class="n">★</div><div>' +
          "<p><strong>" + esc(r.label) + "</strong> &middot; " +
          '<span class="pill sur">' + pct(r.pct) + "</span></p>" +
          '<p class="sub">This is the wedge — over-invest here before fixing anything else.</p>' +
          "</div></div>";
      }).join("") || '<p class="empty">No surplus yet. Manufacture one.</p>';

      return '<div class="page-head"><h1>' + esc(a.name) + "</h1>" +
        "<p>" + esc(a.city || "") + ", " + esc(a.country || "") + " &middot; " +
        esc(a.subgenre || "") + " &middot; " + esc(a.tier || "") + " tier</p></div>" +

        '<div class="grid g4">' +
          card_stat("Monthly listeners", metricVal("monthly_listeners", m.monthly_listeners), "manual — Spotify for Artists") +
          card_stat("Boomplay streams", metricVal("boomplay_streams", m.boomplay_streams), "auto — Boomplay API") +
          card_stat("DJ spins (30d)", metricVal("dj_spins_30d", m.dj_spins_30d), "manual — fieldwork") +
          card_stat("WhatsApp list", metricVal("whatsapp_list_size", m.whatsapp_list_size), "manual — your list") +
        "</div>" +

        '<div class="grid g3" style="margin-top:14px">' +
          '<div class="card"><div class="health">' +
            '<div class="ring" style="--p:' + d.health + '"><b>' + d.health + "%</b></div>" +
            "<div><div class=\"stat\"><span class=\"k\">Competitive health</span>" +
            '<span class="s">Share of dimensions at or above the peer median.</span></div></div>' +
          "</div></div>" +
          '<div class="card"><div class="stat"><span class="k">Peer set</span>' +
            '<span class="v">' + c.peers + "</span>" +
            '<span class="s">of ' + c.competitors + " tracked acts match tier + subgenre</span></div></div>" +
          '<div class="card"><div class="stat"><span class="k">Radar going cold</span>' +
            '<span class="v ' + (c.cold ? "bad" : "ok") + '">' + c.cold + "</span>" +
            '<span class="s">of ' + c.radar + " contacts not touched in 30 days</span></div></div>" +
        "</div>" +

        '<h2 class="sec">Highest-leverage deficits</h2><div class="card">' + deficits + "</div>" +
        '<h2 class="sec">Your wedge</h2><div class="card">' + surplus + "</div>";
    });
  };

  function card_stat(k, v, s) {
    return '<div class="card"><div class="stat"><span class="k">' + esc(k) + "</span>" +
      '<span class="v">' + v + '</span><span class="s">' + esc(s) + "</span></div></div>";
  }

  views.gaps = function () {
    return api("/gaps").then(function (d) {
      if (!d.peer_count) {
        return '<div class="page-head"><h1>Gap Analysis</h1></div>' +
          '<div class="note bad"><strong>No tier- and subgenre-matched peers.</strong> ' +
          "Benchmarking against acts in a different tier or subgenre produces " +
          "misleading numbers, so nothing is shown. Add matching competitors first.</div>";
      }
      var rows = d.rows.map(function (r) {
        var cls = r.read === "deficit" ? "def" : r.read === "surplus" ? "sur" : "par";
        var bars = "";
        if (r.median != null && r.best) {
          var scale = Math.max(r.ours || 0, r.median, r.best) || 1;
          bars = '<div class="cmp">' +
            '<div class="lbl"><span>you</span><span>' + metricVal(r.key, r.ours) + "</span></div>" +
            '<div class="bar"><i class="ours" style="width:' + ((r.ours || 0) / scale * 100) + '%"></i></div>' +
            '<div class="lbl"><span>peer median</span><span>' + metricVal(r.key, r.median) + "</span></div>" +
            '<div class="bar"><i class="med" style="width:' + (r.median / scale * 100) + '%"></i></div>' +
            "</div>";
        }
        return "<tr><td><strong>" + esc(r.label) + "</strong>" +
          (d.manual_only[r.key] ? '<br><span class="pill par" style="margin-top:4px">manual</span>' : "") +
          "</td><td>" + (bars || "—") + '</td><td class="num">' +
          (r.pct == null ? "—" : '<span class="pill ' + cls + '">' + pct(r.pct) + "</span>") +
          "</td><td>" + esc(r.action || "") + "</td></tr>";
      }).join("");

      return '<div class="page-head"><h1>Gap Analysis</h1>' +
        "<p>" + esc(d.artist) + " vs the median of <strong>" + d.peer_count +
        "</strong> tier- and subgenre-matched peers: " + esc(d.peers.join(", ")) + "</p></div>" +
        '<div class="note info">Benchmarked against the peer <strong>median</strong>, never the ' +
        "maximum — a single outlier should not set your targets. Acts outside your tier or " +
        "subgenre are excluded entirely.</div>" +
        '<div class="card pad0"><div class="tbl-wrap"><table><thead><tr>' +
        "<th>Dimension</th><th>You vs peer median</th><th class=\"num\">Delta</th><th>Next action</th>" +
        "</tr></thead><tbody>" + rows + "</tbody></table></div></div>";
    });
  };

  views.competitors = function () {
    return api("/competitors").then(function (d) {
      cache.meta = d;
      var art = d.artist;
      var rows = d.competitors.map(function (c) {
        var m = c.metrics || {};
        var isPeer = c.subgenre === art.subgenre && c.tier === art.tier;
        return "<tr><td><strong>" + esc(c.name) + "</strong><br>" +
          '<span class="tiny">' + esc(c.city || "") + ", " + esc(c.country || "") + "</span></td>" +
          "<td>" + esc(c.subgenre || "—") + "</td>" +
          "<td>" + tierPill(c.tier) + "</td>" +
          '<td class="num">' + metricVal("monthly_listeners", m.monthly_listeners) + "</td>" +
          '<td class="num">' + metricVal("boomplay_streams", m.boomplay_streams) + "</td>" +
          '<td class="num">' + metricVal("dj_spins_30d", m.dj_spins_30d) + "</td>" +
          '<td><span class="pill ' + (isPeer ? "peer" : "tactics") + '">' +
            (isPeer ? "peer" : "tactics only") + "</span></td>" +
          '<td><div class="row-actions">' +
          '<button class="ghost sm danger" data-del="' + esc(c.name) + '">Remove</button>' +
          "</div></td></tr>";
      }).join("");

      return '<div class="page-head"><h1>Competitor Matrix</h1>' +
        "<p>Only acts matching <strong>" + esc(art.subgenre) + "</strong> and the <strong>" +
        esc(art.tier) + "</strong> tier count as peers in the gap analysis.</p></div>" +
        '<div class="toolbar"><button class="btn" id="add">+ Add competitor</button>' +
        '<div class="spacer"></div></div>' +
        '<div class="card pad0"><div class="tbl-wrap"><table><thead><tr>' +
        "<th>Act</th><th>Subgenre</th><th>Tier</th><th class=\"num\">Listeners</th>" +
        "<th class=\"num\">Boomplay</th><th class=\"num\">DJ spins</th><th>Role</th><th></th>" +
        "</tr></thead><tbody>" + (rows || '<tr><td colspan="8" class="empty">No competitors yet.</td></tr>') +
        "</tbody></table></div></div>";
    });
  };

  views.radar = function () {
    return api("/radar").then(function (d) {
      var byCity = {};
      d.contacts.forEach(function (c) { (byCity[c.city || "Other"] = byCity[c.city || "Other"] || []).push(c); });
      var html = '<div class="page-head"><h1>DJ &amp; Radio Radar</h1>' +
        "<p>Contact CRM for Kampala, Nairobi and Dar es Salaam. No contact is approached " +
        "twice without an outcome logged.</p></div>";
      Object.keys(byCity).sort().forEach(function (city) {
        var rows = byCity[city].map(function (c) {
          var cold = (c.days || 0) > 30;
          return "<tr><td><strong>" + esc(c.name) + "</strong></td>" +
            "<td>" + esc(c.class) + "</td><td>" + esc(c.genre_lean || "") + "</td>" +
            "<td>" + esc(c.submission_route || "") + "</td>" +
            '<td class="num">' + (c.days == null ? "—" : c.days + "d") +
            (cold ? ' <span class="pill warn">cold</span>' : "") + "</td>" +
            "<td>" + esc(c.outcome || "") + "</td></tr>";
        }).join("");
        html += '<h2 class="sec">' + esc(city) + '</h2><div class="card pad0"><div class="tbl-wrap">' +
          "<table><thead><tr><th>Contact</th><th>Class</th><th>Genre</th><th>Route</th>" +
          "<th class=\"num\">Last</th><th>Outcome</th></tr></thead><tbody>" + rows +
          "</tbody></table></div></div>";
      });
      return html;
    });
  };

  views.swipe = function () {
    return api("/swipe").then(function (d) {
      var items = d.entries.map(function (e) {
        return '<div class="swipe-item"><h4>' + esc(e.source) + " &middot; " + esc(e.channel) + "</h4>" +
          '<div class="meta">' + esc(e.date) + " &middot; " + esc(e.format || "") +
          " &middot; " + esc(e.metrics || "") + "</div>" +
          "<div>" + esc(e.hook || "") + "</div>" +
          '<div class="prin">→ ' + esc(e.principle || "") + "</div></div>";
      }).join("") || '<p class="empty">No entries.</p>';
      return '<div class="page-head"><h1>Swipe File</h1>' +
        "<p>Real campaigns worth stealing the mechanism from. Every entry must carry a " +
        "transferable principle — otherwise it is decoration.</p></div>" +
        '<div class="card">' + items + "</div>";
    });
  };

  views.sources = function () {
    return api("/providers").then(function (d) {
      var rows = d.providers.map(function (p) {
        return "<tr><td><strong>" + esc(p.name) + "</strong></td>" +
          "<td>" + (p.ready ? '<span class="pill sur">ready</span>'
            : '<span class="pill par">needs ' + esc(p.missing.join(", ")) + "</span>") + "</td>" +
          "<td>" + p.metrics.map(function (m) { return "<code>" + esc(m) + "</code>"; }).join(" ") + "</td>" +
          "<td>" + esc(p.note) + "</td></tr>";
      }).join("");
      var manual = Object.keys(d.manual_only).map(function (k) {
        return "<tr><td><code>" + esc(k) + "</code></td><td>" + esc(d.manual_only[k]) + "</td></tr>";
      }).join("");
      return '<div class="page-head"><h1>Data Sources</h1>' +
        "<p>What updates itself, and what will always need a human.</p></div>" +
        '<div class="note bad"><strong>Spotify monthly listeners are not available from any ' +
        "official API.</strong> Extended quota requires 250,000+ monthly active users, which " +
        "rules out independent artists. Chartmeter refuses to auto-write this field rather than " +
        "scrape it — enter it from Spotify for Artists.</div>" +
        '<h2 class="sec">Automated providers</h2>' +
        '<div class="card pad0"><div class="tbl-wrap"><table><thead><tr><th>Provider</th>' +
        "<th>Status</th><th>Fills</th><th>Notes</th></tr></thead><tbody>" + rows +
        "</tbody></table></div></div>" +
        '<h2 class="sec">Manual by design</h2>' +
        '<div class="note">These are the highest-signal metrics in this market and no platform ' +
        "will ever hand them to you. The automation exists to clear the boring numbers so your " +
        "time goes to this fieldwork.</div>" +
        '<div class="card pad0"><div class="tbl-wrap"><table><thead><tr><th>Metric</th>' +
        "<th>Where it comes from</th></tr></thead><tbody>" + manual + "</tbody></table></div></div>";
    });
  };

  // ---------------------------------------------------------------- add form
  function openAddForm(errors) {
    var meta = cache.meta || { metrics: [], artist: {} };
    var art = meta.artist || {};
    modalTitle.textContent = "Add competitor";
    var metricFields = meta.metrics.map(function (m) {
      return '<div class="field"><label>' + esc(m.label) + "</label>" +
        '<input name="m_' + esc(m.key) + '" type="number" step="any" placeholder="—"></div>';
    }).join("");

    modalBody.innerHTML =
      (errors ? '<div class="errs"><strong>Could not save:</strong><ul>' +
        errors.map(function (e) { return "<li>" + esc(e) + "</li>"; }).join("") + "</ul></div>" : "") +
      '<form id="cform">' +
        '<div class="form-grid">' +
          '<div class="field"><label>Name *</label><input name="name" required></div>' +
          '<div class="field"><label>Subgenre</label><input name="subgenre" value="' +
            esc(art.subgenre || "") + '"><div class="hint">Must match ' +
            esc(art.subgenre || "your artist") + " to count as a peer.</div></div>" +
          '<div class="field"><label>City</label><input name="city"></div>' +
          '<div class="field"><label>Country</label><select name="country">' +
            ["UG", "KE", "TZ", "RW", "Other"].map(function (c) {
              return '<option value="' + c + '">' + c + "</option>"; }).join("") +
          "</select></div>" +
          '<div class="field"><label>Tier</label><select name="tier">' +
            '<option value="">auto from listeners</option>' +
            '<option value="upcoming">Upcoming (0–20k)</option>' +
            '<option value="mid">Mid-level (20k–500k)</option>' +
            '<option value="aspirational">Aspirational (500k+)</option>' +
          "</select></div>" +
          '<div class="field"><label>Last audited</label><input name="last_audit" type="date"></div>' +
        "</div>" +
        '<h2 class="sec">Metrics</h2><div class="form-grid">' + metricFields + "</div>" +
        '<h2 class="sec">SWOT</h2>' +
        '<div class="field"><label>Visual hooks</label><input name="visual_hooks"></div>' +
        '<div class="field"><label>Performance loop</label><input name="performance_loop"></div>' +
        '<div class="field"><label>Engagement drop-off</label><input name="dropoff"></div>' +
        '<div class="toolbar" style="margin-top:18px"><button class="btn" type="submit">Save competitor</button>' +
        '<button class="ghost" type="button" id="cancel">Cancel</button></div>' +
      "</form>";

    modal.hidden = false;
    document.getElementById("cancel").onclick = closeModal;
    document.getElementById("cform").onsubmit = function (ev) {
      ev.preventDefault();
      var fd = new FormData(ev.target), payload = { metrics: {} };
      fd.forEach(function (v, k) {
        if (k.indexOf("m_") === 0) { if (v !== "") payload.metrics[k.slice(2)] = v; }
        else payload[k] = v;
      });
      api("/competitors", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }).then(function () {
        closeModal();
        toast("Added " + payload.name);
        render();
      }).catch(function (err) {
        openAddForm(err && err.errors ? err.errors : ["Unexpected error."]);
      });
    };
  }

  function closeModal() { modal.hidden = true; modalBody.innerHTML = ""; }

  // ---------------------------------------------------------------- wiring
  function render() {
    spinner();
    views[view]().then(function (html) {
      main.innerHTML = html;
      main.scrollTop = 0;
      var add = document.getElementById("add");
      if (add) add.onclick = function () { openAddForm(); };
      Array.prototype.forEach.call(main.querySelectorAll("[data-del]"), function (b) {
        b.onclick = function () {
          var name = b.getAttribute("data-del");
          if (!confirm("Remove " + name + " from the matrix?")) return;
          api("/competitors/" + encodeURIComponent(name), { method: "DELETE" })
            .then(function () { toast("Removed " + name); render(); })
            .catch(function () { toast("Could not remove", true); });
        };
      });
    }).catch(function (e) {
      main.innerHTML = '<div class="note bad">Failed to load. ' + esc(e && e.error || e) + "</div>";
    });
  }

  document.getElementById("nav").addEventListener("click", function (ev) {
    var b = ev.target.closest("button[data-view]");
    if (!b) return;
    Array.prototype.forEach.call(this.querySelectorAll("button"), function (x) {
      x.classList.toggle("active", x === b);
    });
    view = b.getAttribute("data-view");
    location.hash = view;
    render();
  });

  document.getElementById("modal-close").onclick = closeModal;
  modal.addEventListener("click", function (e) { if (e.target === modal) closeModal(); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") closeModal(); });

  document.getElementById("reset").onclick = function () {
    if (!confirm("Reset all demo data back to the seed?")) return;
    api("/reset", { method: "POST" }).then(function () {
      toast("Demo data reset");
      render();
    });
  };

  var h = (location.hash || "").replace("#", "");
  if (views[h]) {
    view = h;
    var btn = document.querySelector('[data-view="' + h + '"]');
    if (btn) {
      Array.prototype.forEach.call(document.querySelectorAll("#nav button"), function (x) {
        x.classList.remove("active");
      });
      btn.classList.add("active");
    }
  }
  render();
})();
