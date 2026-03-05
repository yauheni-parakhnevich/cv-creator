initLangSelector();

// Redirect to login if no profile selected or profile data is stale
const profileId = localStorage.getItem("profileId");
const _hasName = localStorage.getItem("profileName");
if (!profileId || !_hasName) {
  localStorage.removeItem("profileId");
  localStorage.removeItem("profileName");
  localStorage.removeItem("profileCvStyle");
  localStorage.removeItem("profileCvFilename");
  window.location.href = "/";
}

let profileName = localStorage.getItem("profileName") || "";
let profileCvStyle = localStorage.getItem("profileCvStyle") || "executive";
let profileCvFilename = localStorage.getItem("profileCvFilename") || "";

// Apply translations to static elements
document.getElementById("profile-label").textContent = t("profileLabel");
document.getElementById("switch-profile-btn").textContent = t("switchProfile");
document.getElementById("new-task-title").textContent = t("newTask");
document.getElementById("label-vacancy").textContent = t("labelVacancy");
document.getElementById("vacancy_text").placeholder = t("vacancyPlaceholder");
document.getElementById("label-background").textContent = t("labelBackground");
document.getElementById("background_text").placeholder = t("backgroundPlaceholder");
document.getElementById("label-cv-override").textContent = t("labelCvFileOverride");
document.getElementById("label-output-format").textContent = t("labelOutputFormat");
document.getElementById("label-cv-style").textContent = t("labelCvStyle");
document.getElementById("submit-btn").textContent = t("createTask");
document.getElementById("tasks-title").textContent = t("tasksTitle");
document.getElementById("tasks-empty").textContent = t("noTasks");
document.getElementById("app-opt-executive").textContent = t("styleExecutive");
document.getElementById("app-opt-normal").textContent = t("styleNormal");

function updateProfileHeader() {
  document.getElementById("profile-name").textContent = profileName || "Unknown";
  const cvInfo = document.getElementById("profile-cv-info");
  if (profileCvFilename) {
    cvInfo.textContent = `(CV: ${profileCvFilename})`;
  } else {
    cvInfo.textContent = t("noCvUploaded");
  }
}

// Fetch fresh profile data from API to ensure localStorage is in sync
(async function refreshProfile() {
  try {
    const res = await fetch(`/api/profiles/${profileId}`);
    if (res.status === 404) {
      localStorage.removeItem("profileId");
      localStorage.removeItem("profileName");
      localStorage.removeItem("profileCvStyle");
      localStorage.removeItem("profileCvFilename");
      window.location.href = "/";
      return;
    }
    if (res.ok) {
      const p = await res.json();
      profileName = p.name;
      profileCvStyle = p.cv_style;
      profileCvFilename = p.cv_filename || "";
      localStorage.setItem("profileName", profileName);
      localStorage.setItem("profileCvStyle", profileCvStyle);
      localStorage.setItem("profileCvFilename", profileCvFilename);
      updateProfileHeader();
      document.getElementById("cv_style").value = profileCvStyle;
    }
  } catch {
    // offline — use cached values
  }
})();

updateProfileHeader();

// Set default CV style from profile
document.getElementById("cv_style").value = profileCvStyle;

// Show CV default hint
const cvHint = document.getElementById("cv-default-hint");
if (profileCvFilename) {
  cvHint.textContent = t("cvHintUsingProfile").replace("{0}", profileCvFilename);
} else {
  cvHint.textContent = t("cvHintNoProfile");
}

const form = document.getElementById("task-form");
const submitBtn = document.getElementById("submit-btn");
const tasksList = document.getElementById("tasks-list");
const tasksEmpty = document.getElementById("tasks-empty");
const tasksPager = document.getElementById("tasks-pager");

let currentPage = 1;
const perPage = 10;

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = t("creatingTask");

  const formData = new FormData();
  formData.append("profile_id", profileId);
  formData.append("vacancy_text", document.getElementById("vacancy_text").value);
  const bg = document.getElementById("background_text").value;
  if (bg.trim()) formData.append("background_text", bg);
  formData.append("output_format", document.getElementById("output_format").value);
  formData.append("cv_style", document.getElementById("cv_style").value);
  const cvFile = document.getElementById("cv_file").files[0];
  if (cvFile) formData.append("cv_file", cvFile);

  try {
    const res = await fetch("/api/tasks", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || t("failedCreateTask"));
      return;
    }
    form.reset();
    document.getElementById("cv_style").value = profileCvStyle;
    currentPage = 1;
    await loadTasks();
  } catch (err) {
    alert(t("networkError") + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = t("createTask");
  }
});

function statusLabel(status) {
  const map = {
    pending: t("statusPending"),
    processing: t("statusProcessing"),
    completed: t("statusCompleted"),
    failed: t("statusFailed"),
  };
  return map[status] || status;
}

function statusBadge(status) {
  const cls = {
    pending: "badge-pending",
    processing: "badge-processing",
    completed: "badge-completed",
    failed: "badge-failed",
  }[status] || "";
  return `<span class="badge ${cls}">${statusLabel(status)}</span>`;
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleDateString() + " " + d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

function renderTasks(data) {
  const { tasks, total, page, pages } = data;
  if (total === 0) {
    tasksList.classList.add("hidden");
    tasksPager.classList.add("hidden");
    tasksEmpty.classList.remove("hidden");
    return;
  }
  tasksEmpty.classList.add("hidden");
  tasksList.classList.remove("hidden");

  tasksList.innerHTML = tasks
    .map(
      (t_) => `
    <div class="task-card" onclick="window.location.href='/tasks/${t_.id}'">
      <div class="task-card-body">
        <div class="task-card-main">
          <div class="task-card-title">${t_.company_name || t("unknownCompany")}</div>
          <div class="task-card-meta">
            ${statusBadge(t_.status)}
            <span class="task-card-format">${t_.output_format.toUpperCase()}</span>
            <span class="task-card-date">${formatDate(t_.created_at)}</span>
          </div>
          ${t_.error_message ? `<div class="task-card-error">${t_.error_message.substring(0, 100)}</div>` : ""}
        </div>
      </div>
      <div class="task-card-actions" onclick="event.stopPropagation()">
        ${t_.status === "completed" ? `<a href="/api/tasks/${t_.id}/download" class="task-action-btn task-action-download" title="${t("downloadCvHint")}">&#11015;</a>` : ""}
        ${t_.status === "completed" && t_.cover_letter_filename ? `<a href="/api/tasks/${t_.id}/download-cover-letter" class="task-action-btn task-action-letter" title="${t("downloadClHint")}">&#9993;</a>` : ""}
        <button class="task-action-btn task-action-delete" onclick="deleteTask(${t_.id})" title="${t("deleteTaskHint")}">&times;</button>
      </div>
    </div>`
    )
    .join("");

  // Pagination
  if (pages > 1) {
    tasksPager.classList.remove("hidden");
    let pagerHtml = "";
    pagerHtml += `<button class="pager-btn" ${page <= 1 ? "disabled" : ""} onclick="goToPage(${page - 1})">&laquo;</button>`;
    const range = pagerRange(page, pages);
    for (const p of range) {
      if (p === "...") {
        pagerHtml += `<span class="pager-ellipsis">&hellip;</span>`;
      } else {
        pagerHtml += `<button class="pager-btn ${p === page ? "pager-active" : ""}" onclick="goToPage(${p})">${p}</button>`;
      }
    }
    pagerHtml += `<button class="pager-btn" ${page >= pages ? "disabled" : ""} onclick="goToPage(${page + 1})">&raquo;</button>`;
    tasksPager.innerHTML = pagerHtml;
  } else {
    tasksPager.classList.add("hidden");
  }
}

function pagerRange(current, total) {
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1);
  const pages = [];
  pages.push(1);
  if (current > 3) pages.push("...");
  for (let i = Math.max(2, current - 1); i <= Math.min(total - 1, current + 1); i++) {
    pages.push(i);
  }
  if (current < total - 2) pages.push("...");
  pages.push(total);
  return pages;
}

window.goToPage = function (page) {
  currentPage = page;
  loadTasks();
};

async function loadTasks() {
  try {
    const res = await fetch(`/api/tasks?profile_id=${profileId}&page=${currentPage}&per_page=${perPage}`);
    if (!res.ok) return;
    const data = await res.json();
    renderTasks(data);
  } catch {
    // ignore polling errors
  }
}

window.deleteTask = async function (id) {
  if (!confirm(t("confirmDeleteTask"))) return;
  try {
    await fetch(`/api/tasks/${id}`, { method: "DELETE" });
    await loadTasks();
  } catch {
    alert(t("failedDeleteTask"));
  }
};

// Initial load + polling
loadTasks();
setInterval(loadTasks, 5000);
