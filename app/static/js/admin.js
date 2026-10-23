// Admin dashboard.
(function () {
  const $ = (id) => document.getElementById(id);
  const LABELS = ["query", "suggestion", "bug", "junk"];
  let suggestionsById = {};
  let issuesById = {};

  function esc(s) {
    return String(s ?? "").replace(/[&<>"']/g, (c) =>
      ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
  }

  function when(iso) {
    const d = new Date(iso);
    return d.toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" });
  }

  async function api(path, opts = {}) {
    const resp = await fetch(path, {
      headers: { "Content-Type": "application/json" },
      ...opts,
      body: opts.body ? JSON.stringify(opts.body) : undefined,
    });
    if (resp.status === 401) {
      location.href = "/admin/login";
      throw new Error("login required");
    }
    const data = await resp.json();
    if (!resp.ok) throw new Error(data.error || resp.statusText);
    return data;
  }

  // ---------------------------------------------------------------- tabs
  const loaders = {};
  function showTab(name) {
    document.querySelectorAll(".tabs button").forEach((b) => b.classList.toggle("on", b.dataset.tab === name));
    document.querySelectorAll("[data-panel]").forEach((p) => (p.hidden = p.dataset.panel !== name));
    history.replaceState(null, "", `#${name}`);
    loaders[name]();
  }
  document.querySelectorAll(".tabs button").forEach((b) => (b.onclick = () => showTab(b.dataset.tab)));

  function pipelineBanner(status) {
    const b = $("pipeline-banner");
    if (status === "ready") {
      b.hidden = true;
      return;
    }
    b.hidden = false;
    b.className = `banner ${status === "error" ? "err" : "warn"}`;
    b.innerHTML = status === "error"
      ? "⚠️ The ML pipeline failed to load. Feedback is stored but not classified. See the <b>Model</b> tab."
      : "ℹ️ No trained model yet. Feedback is stored but not classified. Implement <code>ml/pipeline.py</code>, run <code>python -m ml.train</code>, then press <b>Reload model</b>.";
  }

  // ---------------------------------------------------------------- lookups for match column
  async function refreshLookups() {
    const [s, i] = await Promise.all([api("/api/admin/suggestions"), api("/api/admin/issues")]);
    suggestionsById = Object.fromEntries(s.items.map((x) => [x.id, x]));
    issuesById = Object.fromEntries(i.items.map((x) => [x.id, x]));
    return { suggestions: s.items, issues: i.items };
  }

  function matchCell(row) {
    if (!row.match_id) return row.label === "bug" ? `<span class="badge">no known issue</span>` : "";
    const ref = row.match_kind === "suggestion" ? suggestionsById[row.match_id] : issuesById[row.match_id];
    const text = ref ? (ref.text || ref.title) : "";
    const newBadge = row.created_new ? ` <span class="badge new">new</span>` : "";
    return `<span class="match-id">${esc(row.match_id)}</span>${newBadge}<span class="match-text">${esc(text)}</span>`;
  }

  function labelCell(row) {
    const opts = LABELS.map((l) => `<option ${row.label === l ? "selected" : ""}>${l}</option>`).join("");
    const none = row.label ? "" : `<option selected disabled>unclassified</option>`;
    const src = row.label_source === "admin" ? ` <span class="badge admin">corrected</span>` : "";
    const conf = row.confidence != null ? ` <span class="badge">${Math.round(row.confidence * 100)}%</span>` : "";
    const err = row.pipeline_error ? ` <span class="err-dot" title="${esc(row.pipeline_error)}">●</span>` : "";
    return `<select data-relabel="${row.id}">${none}${opts}</select>${conf}${src}${err}`;
  }

  // ---------------------------------------------------------------- overview
  loaders.overview = async () => {
    const s = await api("/api/admin/summary");
    pipelineBanner(s.pipeline_status);
    const t = (k, v, cls = "") => `<div class="tile ${cls}"><div class="k">${k}</div><div class="v">${v}</div></div>`;
    $("tiles").innerHTML =
      t("Total feedback", s.total) +
      t("Queries", s.by_label.query || 0, "query") +
      t("Suggestions", s.by_label.suggestion || 0, "suggestion") +
      t("Bug reports", s.by_label.bug || 0, "bug") +
      t("Junk", s.by_label.junk || 0, "junk") +
      t("Unclassified", s.by_label.unclassified || 0) +
      t("New ideas added", s.new_suggestions) +
      t("Unmatched bugs", s.unmatched_bugs) +
      t("Open issues", s.open_issues);
    $("top-suggestions").innerHTML = s.top_suggestions.map((x) =>
      `<li>${esc(x.text)} <span class="n">${x.count}</span></li>`).join("");
    $("top-issues").innerHTML = s.top_issues.length
      ? s.top_issues.map((x) =>
        `<li>${esc(x.title)} <span class="badge ${x.status}">${x.status}</span> <span class="n">${x.reports}</span></li>`).join("")
      : `<li class="empty" style="list-style:none;padding:0">No bug reports matched yet.</li>`;
  };

  // ---------------------------------------------------------------- inbox
  loaders.inbox = async () => {
    await refreshLookups();
    const qs = new URLSearchParams();
    if ($("f-label").value) qs.set("label", $("f-label").value);
    if ($("f-unmatched").checked) qs.set("unmatched", "1");
    if ($("f-q").value.trim()) qs.set("q", $("f-q").value.trim());
    const { items } = await api(`/api/admin/feedback?${qs}`);
    $("inbox-empty").hidden = items.length > 0;
    $("inbox-body").innerHTML = items.map((r) => `
      <tr>
        <td>${r.id}</td>
        <td class="when">${when(r.created_at)}</td>
        <td class="msg">${esc(r.text)}</td>
        <td>${labelCell(r)}</td>
        <td>${matchCell(r)}</td>
        <td class="reply">${esc(r.reply)}</td>
      </tr>`).join("");
  };
  ["f-label", "f-unmatched"].forEach((id) => $(id).addEventListener("change", loaders.inbox));
  let qTimer;
  $("f-q").addEventListener("input", () => {
    clearTimeout(qTimer);
    qTimer = setTimeout(loaders.inbox, 250);
  });

  document.addEventListener("change", async (e) => {
    const id = e.target.dataset.relabel;
    if (!id) return;
    await api(`/api/admin/feedback/${id}`, { method: "PATCH", body: { label: e.target.value } });
    loaders.inbox();
  });

  // ---------------------------------------------------------------- suggestions
  loaders.suggestions = async () => {
    const { suggestions } = await refreshLookups();
    const sorted = [...suggestions].sort((a, b) => b.count - a.count || a.id.localeCompare(b.id));
    const max = Math.max(1, ...sorted.map((x) => x.count));
    $("sugg-body").innerHTML = sorted.map((x) => `
      <tr>
        <td class="match-id">${esc(x.id)}</td>
        <td>${esc(x.text)}</td>
        <td><span class="bar"><span style="width:${(x.count / max) * 100}%"></span></span><span class="bar-n">${x.count}</span></td>
        <td><span class="badge ${x.source}">${x.source === "user" ? "from users" : "original list"}</span></td>
      </tr>`).join("");
  };

  // ---------------------------------------------------------------- issues
  loaders.issues = async () => {
    const { issues } = await refreshLookups();
    $("issues-body").innerHTML = issues.map((x) => `
      <tr data-issue="${esc(x.id)}">
        <td class="match-id">${esc(x.id)}</td>
        <td>${esc(x.title)}</td>
        <td><span class="badge">${esc(x.component || "—")}</span></td>
        <td>${x.reports}</td>
        <td><select class="st">
          <option value="open" ${x.status === "open" ? "selected" : ""}>open</option>
          <option value="fixed" ${x.status === "fixed" ? "selected" : ""}>fixed</option>
        </select></td>
        <td><input type="text" class="fx" placeholder="e.g. 2.4.2" value="${esc(x.fixed_in || "")}"></td>
        <td><button class="icon-btn save-issue">Save</button></td>
      </tr>`).join("");

    const { items } = await api("/api/admin/feedback?label=bug&unmatched=1");
    $("unmatched-empty").hidden = items.length > 0;
    $("unmatched-body").innerHTML = items.map((r) => `
      <tr>
        <td>${r.id}</td>
        <td class="when">${when(r.created_at)}</td>
        <td class="msg">${esc(r.text)}</td>
        <td><button class="icon-btn" data-promote="${r.id}" data-text="${esc(r.text)}">Make known issue</button></td>
      </tr>`).join("");
  };

  document.addEventListener("click", async (e) => {
    const save = e.target.closest(".save-issue");
    if (save) {
      const row = save.closest("tr");
      await api(`/api/admin/issues/${row.dataset.issue}`, {
        method: "PATCH",
        body: { status: row.querySelector(".st").value, fixed_in: row.querySelector(".fx").value },
      });
      save.textContent = "Saved ✓";
      setTimeout(loaders.issues, 600);
      return;
    }
    const promote = e.target.closest("[data-promote]");
    if (promote) {
      const title = prompt("Title for the new known issue:", promote.dataset.text);
      if (!title) return;
      await api("/api/admin/issues", { method: "POST", body: { title, feedback_id: Number(promote.dataset.promote) } });
      loaders.issues();
    }
  });

  // ---------------------------------------------------------------- model
  function pct(x) {
    return x == null ? "n/a" : `${(x * 100).toFixed(1)}%`;
  }

  function renderMetrics(m) {
    if (!m) {
      $("metrics").innerHTML = `<div class="card" style="margin-top:16px"><p class="empty">
        No evaluation yet. Run <code>python -m scripts.evaluate</code> to create <code>ml/artifacts/metrics.json</code>.</p></div>`;
      return;
    }
    const t = (k, v) => `<div class="tile"><div class="k">${k}</div><div class="v">${v}</div></div>`;
    const max = Math.max(...m.confusion_matrix.flat(), 1);
    const cells = m.confusion_matrix.map((row, i) => `<tr><th>${m.labels[i]}</th>${row.map((v, j) => {
      const a = v / max;
      const bg = i === j ? `rgba(22,163,74,${0.15 + a * 0.6})` : v ? `rgba(220,38,38,${0.12 + a * 0.6})` : "transparent";
      return `<td style="background:${bg}">${v}</td>`;
    }).join("")}</tr>`).join("");
    const errors = (m.errors || []).slice(0, 40).map((e) => `
      <tr><td><span class="badge">${e.kind}</span></td><td>${esc(e.gold)}</td><td>${esc(e.pred)}</td><td class="msg">${esc(e.text)}</td></tr>`).join("");

    $("metrics").innerHTML = `
      <div class="tiles" style="margin-top:16px">
        ${t("Label accuracy", pct(m.accuracy))}
        ${t("Macro F1", pct(m.macro_f1))}
        ${t("Duplicate hit rate", pct(m.duplicate_hit_rate))}
        ${t("Duplicate reject rate", pct(m.duplicate_reject_rate))}
      </div>
      <div class="metrics-grid">
        <div class="card">
          <h2>Confusion matrix</h2>
          <table class="cm">
            <tr><th class="axis">true ↓ / predicted →</th>${m.labels.map((l) => `<th>${l}</th>`).join("")}</tr>
            ${cells}
          </table>
          <p class="counter" style="margin-top:10px">Held-out ${m.n} messages (test_size=${m.test_size}, seed=${m.seed}), generated ${esc(m.generated_at)}.</p>
        </div>
        <div class="card">
          <h2>Per-class F1</h2>
          <ol class="rank" style="list-style:none;padding:0">${m.labels.map((l) =>
            `<li>${l} <span class="n">${pct(m.f1[l])}</span></li>`).join("")}</ol>
        </div>
      </div>
      <div class="card table-card" style="margin-top:16px">
        <table class="table">
          <thead><tr><th>Mistake</th><th>Expected</th><th>Got</th><th>Message</th></tr></thead>
          <tbody>${errors || `<tr><td colspan="4" class="empty">No mistakes 🎉</td></tr>`}</tbody>
        </table>
      </div>`;
  }

  loaders.model = async () => {
    const m = await api("/api/admin/model");
    pipelineBanner(m.status);
    const cls = m.status === "ready" ? "fixed" : "open";
    $("model-status").innerHTML = `<span class="badge ${cls}">${m.status}</span>
      <span class="counter">loaded ${when(m.loaded_at)}${m.has_proba ? " · predict_proba ✓" : ""}</span>`;
    $("model-detail").textContent = m.detail;
    renderMetrics(m.metrics);
  };

  $("reload-model").onclick = async () => {
    $("reload-model").disabled = true;
    try {
      await api("/api/admin/model/reload", { method: "POST" });
      await loaders.model();
    } finally {
      $("reload-model").disabled = false;
    }
  };

  const initial = location.hash.slice(1);
  showTab(loaders[initial] ? initial : "overview");
})();
