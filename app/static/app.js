const $ = (sel) => document.querySelector(sel);

function showStatus(el, text, isError = false) {
  el.hidden = false;
  el.textContent = text;
  el.classList.toggle("error", isError);
  el.classList.toggle("status", !isError);
}

async function api(path, options = {}) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
    ...options,
  });
  const text = await res.text();
  let data = null;
  try {
    data = text ? JSON.parse(text) : null;
  } catch {
    data = text;
  }
  if (!res.ok) {
    const detail = data?.detail || text || res.statusText;
    throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
  }
  return data;
}

document.querySelectorAll(".tab").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((b) => b.classList.remove("active"));
    document.querySelectorAll(".panel").forEach((p) => p.classList.remove("active"));
    btn.classList.add("active");
    $(`#${btn.dataset.tab}`).classList.add("active");
  });
});

async function loadDocuments() {
  const body = $("#docs-body");
  body.innerHTML = `<tr><td colspan="4">Загрузка…</td></tr>`;
  try {
    const docs = await api("/kb/documents");
    if (!docs.length) {
      body.innerHTML = `<tr><td colspan="4">Пока нет документов</td></tr>`;
      return;
    }
    body.innerHTML = docs
      .map(
        (d) => `
      <tr>
        <td>${escapeHtml(d.title)}</td>
        <td>${formatDate(d.created_at)}</td>
        <td><code>${escapeHtml(d.id)}</code></td>
        <td><button type="button" class="ghost" data-open-doc="${d.id}">Открыть</button></td>
      </tr>`
      )
      .join("");
    body.querySelectorAll("[data-open-doc]").forEach((btn) => {
      btn.addEventListener("click", () => {
        openDocument(btn.getAttribute("data-open-doc"));
      });
    });
  } catch (err) {
    body.innerHTML = `<tr><td colspan="4" class="error">${escapeHtml(err.message)}</td></tr>`;
  }
}

async function openDocument(id) {
  try {
    const doc = await api(`/kb/documents/${id}`);
    $("#dialog-title").textContent = doc.title;
    $("#dialog-meta").textContent = `${doc.id} · ${formatDate(doc.created_at)}`;
    $("#dialog-text").textContent = doc.text;
    $("#doc-dialog").showModal();
  } catch (err) {
    alert(`Не удалось открыть документ: ${err.message}`);
  }
}

$("#doc-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const status = $("#doc-form-status");
  try {
    const payload = {
      title: $("#doc-title").value.trim(),
      text: $("#doc-text").value.trim(),
    };
    const res = await api("/kb/documents", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    showStatus(status, `Сохранено: ${res.document_id}`);
    $("#doc-form").reset();
    await loadDocuments();
  } catch (err) {
    showStatus(status, err.message, true);
  }
});

$("#reload-docs").addEventListener("click", loadDocuments);

$("#ask-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const result = $("#ask-result");
  result.hidden = false;
  $("#ask-answer").textContent = "Думаю…";
  $("#ask-sources").innerHTML = "";
  $("#ask-error").hidden = true;
  $("#ask-badge").hidden = true;
  try {
    const res = await api("/kb/ask", {
      method: "POST",
      body: JSON.stringify({ question: $("#ask-question").value.trim() }),
    });
    $("#ask-answer").textContent = res.answer;
    if (res.needs_review) {
      $("#ask-badge").hidden = false;
    }
    if (res.error) {
      $("#ask-error").hidden = false;
      $("#ask-error").textContent = `Причина: ${res.error}`;
    }
    $("#ask-sources").innerHTML = renderSources(res.sources);
    bindSourceLinks($("#ask-sources"));
    await loadHistory();
  } catch (err) {
    $("#ask-answer").textContent = "";
    $("#ask-error").hidden = false;
    $("#ask-error").textContent = err.message;
  }
});

async function loadHistory() {
  const onlyReview = $("#filter-review").checked;
  const qaBody = $("#qa-body");
  const auditBody = $("#audit-body");
  qaBody.innerHTML = `<tr><td colspan="4">Загрузка…</td></tr>`;
  auditBody.innerHTML = `<tr><td colspan="4">Загрузка…</td></tr>`;
  try {
    const qs = onlyReview ? "?needs_review=true&limit=100" : "?limit=100";
    const [qa, audit] = await Promise.all([
      api(`/qa/runs${qs}`),
      api("/audit/runs?limit=100"),
    ]);
    qaBody.innerHTML = qa.length
      ? qa
          .map(
            (r) => `
        <tr>
          <td>${formatDate(r.created_at)}</td>
          <td>${escapeHtml(r.question)}</td>
          <td>${r.needs_review ? "да" : "нет"}</td>
          <td><button type="button" class="ghost" data-open-qa="${r.id}">Открыть</button></td>
        </tr>`
          )
          .join("")
      : `<tr><td colspan="4">Пусто</td></tr>`;
    qaBody.querySelectorAll("[data-open-qa]").forEach((btn) => {
      btn.addEventListener("click", () => {
        const id = btn.getAttribute("data-open-qa");
        openQa(id);
      });
    });
    auditBody.innerHTML = audit.length
      ? audit
          .map(
            (r) => `
        <tr title="${escapeHtml(r.error || "")}">
          <td>${formatDate(r.created_at)}</td>
          <td>${escapeHtml(r.action)}</td>
          <td>${escapeHtml(r.status)}</td>
          <td>${r.duration_ms}</td>
        </tr>`
          )
          .join("")
      : `<tr><td colspan="4">Пусто</td></tr>`;
  } catch (err) {
    qaBody.innerHTML = `<tr><td colspan="4" class="error">${escapeHtml(err.message)}</td></tr>`;
  }
}

async function openQa(id) {
  const status = $("#qa-open-status");
  status.hidden = true;
  try {
    const row = await api(`/qa/runs/${id}`);
    $("#qa-dialog-meta").textContent = `${row.id} · ${formatDate(row.created_at)}`;
    $("#qa-card-q").textContent = row.question;
    $("#qa-card-a").textContent = row.answer;
    $("#qa-dialog-badge").hidden = !row.needs_review;
    if (row.error) {
      $("#qa-card-error").hidden = false;
      $("#qa-card-error").textContent = `Причина проверки: ${row.error}`;
    } else {
      $("#qa-card-error").hidden = true;
    }
    $("#qa-card-sources").innerHTML = renderSources(row.sources);
    bindSourceLinks($("#qa-card-sources"));
    $("#qa-dialog").showModal();
  } catch (err) {
    status.hidden = false;
    status.textContent = `Не удалось открыть: ${err.message}`;
  }
}

$("#filter-review").addEventListener("change", loadHistory);
$("#reload-history").addEventListener("click", loadHistory);

function renderSources(sources) {
  if (!sources?.length) {
    return "<li>Источников нет</li>";
  }
  return sources
    .map(
      (s) =>
        `<li><button type="button" class="linkish" data-open-doc="${escapeHtml(
          s.document_id
        )}">${escapeHtml(s.document_id)}</button><br>${escapeHtml(s.quote)}</li>`
    )
    .join("");
}

function bindSourceLinks(root) {
  root.querySelectorAll("[data-open-doc]").forEach((btn) => {
    btn.addEventListener("click", () => {
      openDocument(btn.getAttribute("data-open-doc"));
    });
  });
}

function formatDate(value) {
  try {
    return new Date(value).toLocaleString("ru-RU");
  } catch {
    return value;
  }
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

loadDocuments();
loadHistory();
