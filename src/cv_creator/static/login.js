initLangSelector();

// Apply translations to static elements
document.getElementById("login-subtitle").textContent = t("loginSubtitle");
document.getElementById("profiles-empty").textContent = t("noProfiles");
document.getElementById("toggle-form-btn").textContent = t("newProfile");
document.getElementById("form-title").textContent = t("newProfileTitle");
document.getElementById("label-name").textContent = t("labelName");
document.getElementById("label-default-style").textContent = t("labelDefaultStyle");
document.getElementById("label-cv-file").textContent = t("labelCvFile");
document.getElementById("create-btn").textContent = t("createProfile");
document.getElementById("cancel-btn").textContent = t("cancel");
document.getElementById("profile_name").placeholder = t("namePlaceholder");
document.getElementById("opt-executive").textContent = t("styleExecutive");
document.getElementById("opt-normal").textContent = t("styleNormal");

const profilesList = document.getElementById("profiles-list");
const profilesEmpty = document.getElementById("profiles-empty");
const form = document.getElementById("profile-form");
const submitBtn = document.getElementById("create-btn");
const toggleBtn = document.getElementById("toggle-form-btn");
const cancelBtn = document.getElementById("cancel-btn");
const formTitle = document.getElementById("form-title");

let editingProfileId = null;

function openForm(profile) {
  if (profile) {
    editingProfileId = profile.id;
    formTitle.textContent = t("editProfileTitle");
    submitBtn.textContent = t("saveChanges");
    document.getElementById("profile_name").value = profile.name;
    document.getElementById("profile_cv_style").value = profile.cv_style;
    const cvHint = document.getElementById("cv-current");
    if (profile.cv_filename) {
      cvHint.textContent = `${t("currentFile")} ${profile.cv_filename}`;
      cvHint.classList.remove("hidden");
    } else {
      cvHint.classList.add("hidden");
    }
  } else {
    editingProfileId = null;
    formTitle.textContent = t("newProfileTitle");
    submitBtn.textContent = t("createProfile");
    document.getElementById("cv-current").classList.add("hidden");
    form.reset();
  }
  form.classList.remove("hidden");
  toggleBtn.classList.add("hidden");
  document.getElementById("profile_name").focus();
}

function closeForm() {
  form.classList.add("hidden");
  toggleBtn.classList.remove("hidden");
  editingProfileId = null;
  form.reset();
  document.getElementById("cv-current").classList.add("hidden");
}

toggleBtn.addEventListener("click", () => openForm(null));
cancelBtn.addEventListener("click", closeForm);

function getInitials(name) {
  return name
    .split(/\s+/)
    .map((w) => w[0])
    .join("")
    .toUpperCase()
    .slice(0, 2);
}

const AVATAR_COLORS = [
  "#4f46e5", "#0891b2", "#059669", "#d97706", "#dc2626",
  "#7c3aed", "#db2777", "#2563eb", "#0d9488", "#ca8a04",
];

function avatarColor(id) {
  return AVATAR_COLORS[id % AVATAR_COLORS.length];
}

function selectProfile(profile) {
  localStorage.setItem("profileId", profile.id);
  localStorage.setItem("profileName", profile.name);
  localStorage.setItem("profileCvStyle", profile.cv_style);
  localStorage.setItem("profileCvFilename", profile.cv_filename || "");
  window.location.href = "/app";
}

function renderProfiles(profiles) {
  if (profiles.length === 0) {
    profilesList.classList.add("hidden");
    profilesEmpty.classList.remove("hidden");
    return;
  }
  profilesList.classList.remove("hidden");
  profilesEmpty.classList.add("hidden");

  profilesList.innerHTML = profiles
    .map(
      (p) => `
    <div class="profile-card" onclick="selectProfileById(${p.id})">
      <div class="profile-card-body">
        <div class="profile-avatar" style="background:${avatarColor(p.id)}">${getInitials(p.name)}</div>
        <div class="profile-info">
          <div class="profile-name">${p.name}</div>
          <div class="profile-meta">${p.cv_style.charAt(0).toUpperCase() + p.cv_style.slice(1)} style${p.cv_filename ? " &middot; " + p.cv_filename : ""}</div>
        </div>
      </div>
      <div class="profile-card-actions">
        <button class="profile-edit-btn" onclick="editProfile(event, ${p.id})" title="${t("editProfileHint")}">&#9998;</button>
        <button class="profile-delete-btn" onclick="deleteProfile(event, ${p.id})" title="${t("deleteProfileHint")}">&times;</button>
      </div>
    </div>`
    )
    .join("");
}

let allProfiles = [];

window.selectProfileById = function (id) {
  const p = allProfiles.find((x) => x.id === id);
  if (p) selectProfile(p);
};

window.editProfile = function (event, id) {
  event.stopPropagation();
  const p = allProfiles.find((x) => x.id === id);
  if (p) openForm(p);
};

window.deleteProfile = async function (event, id) {
  event.stopPropagation();
  if (!confirm(t("confirmDeleteProfile"))) return;
  try {
    const res = await fetch(`/api/profiles/${id}`, { method: "DELETE" });
    if (res.ok || res.status === 204) {
      if (localStorage.getItem("profileId") === String(id)) {
        localStorage.removeItem("profileId");
        localStorage.removeItem("profileName");
        localStorage.removeItem("profileCvStyle");
        localStorage.removeItem("profileCvFilename");
      }
      closeForm();
      await loadProfiles();
    }
  } catch {
    alert(t("failedDeleteProfile"));
  }
};

async function loadProfiles() {
  try {
    const res = await fetch("/api/profiles");
    if (!res.ok) return;
    const data = await res.json();
    allProfiles = data.profiles;
    renderProfiles(allProfiles);
  } catch {
    // ignore
  }
}

form.addEventListener("submit", async (e) => {
  e.preventDefault();
  submitBtn.disabled = true;
  const isEdit = editingProfileId !== null;
  submitBtn.textContent = isEdit ? t("savingProfile") : t("creatingProfile");

  const formData = new FormData();
  formData.append("name", document.getElementById("profile_name").value);
  formData.append("cv_style", document.getElementById("profile_cv_style").value);
  const cvFile = document.getElementById("profile_cv_file").files[0];
  if (cvFile) formData.append("cv_file", cvFile);

  try {
    const url = isEdit ? `/api/profiles/${editingProfileId}` : "/api/profiles";
    const method = isEdit ? "PUT" : "POST";
    const res = await fetch(url, { method, body: formData });
    if (!res.ok) {
      const err = await res.json();
      alert(err.detail || t(isEdit ? "failedUpdateProfile" : "failedCreateProfile"));
      return;
    }
    const profile = await res.json();
    if (isEdit) {
      if (localStorage.getItem("profileId") === String(profile.id)) {
        localStorage.setItem("profileName", profile.name);
        localStorage.setItem("profileCvStyle", profile.cv_style);
        localStorage.setItem("profileCvFilename", profile.cv_filename || "");
      }
      closeForm();
      await loadProfiles();
    } else {
      selectProfile(profile);
    }
  } catch (err) {
    alert(t("networkError") + err.message);
  } finally {
    submitBtn.disabled = false;
    submitBtn.textContent = isEdit ? t("saveChanges") : t("createProfile");
  }
});

loadProfiles();
