const form = document.getElementById("task-form");
const submitBtn = document.getElementById("submit-btn");
const tasksTable = document.getElementById("tasks-table");
const tasksBody = document.getElementById("tasks-body");
const tasksEmpty = document.getElementById("tasks-empty");

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  submitBtn.textContent = "Creating...";

  const formData = new FormData();
  formData.append("cv_file", document.getElementById("cv_file").files[0]);
  formData.append("vacancy_text", document.getElementById("vacancy_text").value);
  const bg = document.getElementById("background_text").value;
  if (bg.trim()) formData.append("background_text", bg);
  formData.append("output_format", document.getElementById("output_format").value);
  formData.append("cv_style", document.getElementById("cv_style").value);

  try {
    const res = await fetch("/api/tasks", { method: "POST", body: formData });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || "Failed to create task");
      return;
    }
    form.reset();
    await loadTasks();
  } catch (err) {
    alert("Network error: " + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = "Create Task";
  }
});

function statusBadge(status) {
  const cls = {
    pending: "badge-pending",
    processing: "badge-processing",
    completed: "badge-completed",
    failed: "badge-failed",
  }[status] || "";
  return `<span class="badge ${cls}">${status}</span>`;
}

function formatDate(iso) {
  const d = new Date(iso);
  return d.toLocaleString();
}

function renderTasks(tasks) {
  if (tasks.length === 0) {
    tasksTable.classList.add("hidden");
    tasksEmpty.classList.remove("hidden");
    return;
  }
  tasksTable.classList.remove("hidden");
  tasksEmpty.classList.add("hidden");

  tasksBody.innerHTML = tasks
    .map(
      (t) => `
    <tr>
      <td><a href="/tasks/${t.id}">${t.id}</a></td>
      <td>${t.company_name || "\u2014"}</td>
      <td title="${t.cv_filename}">${t.cv_filename}</td>
      <td>${t.output_format.toUpperCase()}</td>
      <td>${statusBadge(t.status)}${t.error_message ? `<div class="error-msg" title="${t.error_message}">${t.error_message.substring(0, 80)}</div>` : ""}</td>
      <td>${formatDate(t.created_at)}</td>
      <td class="actions">
        ${t.status === "completed" ? `<a href="/api/tasks/${t.id}/download" class="btn btn-download">Download CV</a>` : ""}
        ${t.status === "completed" && t.cover_letter_filename ? `<a href="/api/tasks/${t.id}/download-cover-letter" class="btn btn-download">Cover Letter</a>` : ""}
        <button class="btn btn-delete" onclick="deleteTask(${t.id})">Delete</button>
      </td>
    </tr>`
    )
    .join("");
}

async function loadTasks() {
  try {
    const res = await fetch("/api/tasks");
    if (!res.ok) return;
    const data = await res.json();
    renderTasks(data.tasks);
  } catch {
    // ignore polling errors
  }
}

async function deleteTask(id) {
  if (!confirm("Delete this task?")) return;
  try {
    await fetch(`/api/tasks/${id}`, { method: "DELETE" });
    await loadTasks();
  } catch {
    alert("Failed to delete task");
  }
}

// Initial load + polling
loadTasks();
setInterval(loadTasks, 5000);
