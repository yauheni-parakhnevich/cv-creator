const taskId = window.location.pathname.split("/").pop();
let pollTimer = null;

function statusBadge(status) {
  const cls = {
    pending: "badge-pending",
    processing: "badge-processing",
    completed: "badge-completed",
    failed: "badge-failed",
  }[status] || "";
  return { cls, label: status };
}

function formatDate(iso) {
  return new Date(iso).toLocaleString();
}

function render(task) {
  document.getElementById("task-id").textContent = task.id;

  const badge = statusBadge(task.status);
  const statusEl = document.getElementById("task-status");
  statusEl.textContent = badge.label;
  statusEl.className = "badge " + badge.cls;

  document.getElementById("task-company").textContent = task.company_name || "\u2014";
  document.getElementById("task-cv-filename").textContent = task.cv_filename;
  document.getElementById("task-format").textContent = task.output_format.toUpperCase();
  document.getElementById("task-style").textContent = (task.cv_style || "executive").charAt(0).toUpperCase() + (task.cv_style || "executive").slice(1);
  document.getElementById("task-created").textContent = formatDate(task.created_at);
  document.getElementById("task-updated").textContent = formatDate(task.updated_at);
  document.getElementById("task-vacancy").textContent = task.vacancy_text;

  const bgBlock = document.getElementById("background-block");
  if (task.background_text) {
    bgBlock.style.display = "";
    document.getElementById("task-background").textContent = task.background_text;
  } else {
    bgBlock.style.display = "none";
  }

  const errorBlock = document.getElementById("error-block");
  if (task.error_message) {
    errorBlock.style.display = "";
    document.getElementById("task-error").textContent = task.error_message;
  } else {
    errorBlock.style.display = "none";
  }

  const downloadBtn = document.getElementById("download-btn");
  if (task.status === "completed") {
    downloadBtn.style.display = "";
    downloadBtn.href = `/api/tasks/${task.id}/download`;
  } else {
    downloadBtn.style.display = "none";
  }

  const clBtn = document.getElementById("download-cover-letter-btn");
  if (task.status === "completed" && task.cover_letter_filename) {
    clBtn.style.display = "";
    clBtn.href = `/api/tasks/${task.id}/download-cover-letter`;
  } else {
    clBtn.style.display = "none";
  }

  // Load summary for completed tasks
  const summaryBlock = document.getElementById("summary-block");
  if (task.status === "completed") {
    loadSummary(task.id);
  } else {
    summaryBlock.style.display = "none";
  }

  // Stop polling once terminal
  if (task.status === "completed" || task.status === "failed") {
    if (pollTimer) {
      clearInterval(pollTimer);
      pollTimer = null;
    }
  }
}

function renderMarkdown(text) {
  // Simple markdown to HTML: headings, bold, italic, lists, paragraphs
  return text
    .replace(/^### (.+)$/gm, "<h4>$1</h4>")
    .replace(/^## (.+)$/gm, "<h3>$1</h3>")
    .replace(/^# (.+)$/gm, "<h2>$1</h2>")
    .replace(/\*\*(.+?)\*\*/g, "<strong>$1</strong>")
    .replace(/\*(.+?)\*/g, "<em>$1</em>")
    .replace(/^- (.+)$/gm, "<li>$1</li>")
    .replace(/(<li>.*<\/li>\n?)+/g, (m) => `<ul>${m}</ul>`)
    .replace(/\n{2,}/g, "</p><p>")
    .replace(/^(?!<[hul])(.+)$/gm, "<p>$1</p>")
    .replace(/<p><\/p>/g, "");
}

let summaryLoaded = false;

async function loadSummary(id) {
  if (summaryLoaded) return;
  try {
    const res = await fetch(`/api/tasks/${id}/summary`);
    const block = document.getElementById("summary-block");
    if (!res.ok) {
      block.style.display = "none";
      return;
    }
    const md = await res.text();
    document.getElementById("task-summary").innerHTML = renderMarkdown(md);
    block.style.display = "";
    summaryLoaded = true;
  } catch {
    // ignore
  }
}

async function loadTask() {
  try {
    const res = await fetch(`/api/tasks/${taskId}`);
    if (!res.ok) {
      document.getElementById("task-detail").innerHTML =
        '<p class="empty-state">Task not found.</p>';
      if (pollTimer) clearInterval(pollTimer);
      return;
    }
    render(await res.json());
  } catch {
    // ignore polling errors
  }
}

document.getElementById("delete-btn").addEventListener("click", async () => {
  if (!confirm("Delete this task?")) return;
  try {
    const res = await fetch(`/api/tasks/${taskId}`, { method: "DELETE" });
    if (res.ok || res.status === 204) {
      window.location.href = "/";
    } else {
      alert("Failed to delete task");
    }
  } catch {
    alert("Failed to delete task");
  }
});

// Initial load + polling for active tasks
loadTask();
pollTimer = setInterval(loadTask, 5000);
