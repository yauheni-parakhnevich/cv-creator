const I18N = {
  en: {
    // Common
    appTitle: "CV Creator",
    // Login page
    loginSubtitle: "Select a profile or create a new one to get started",
    noProfiles: "No profiles yet. Create one below.",
    newProfile: "+ New Profile",
    newProfileTitle: "New Profile",
    editProfileTitle: "Edit Profile",
    labelName: "Name",
    labelDefaultStyle: "Default Style",
    labelCvFile: "CV File",
    createProfile: "Create Profile",
    saveChanges: "Save Changes",
    cancel: "Cancel",
    namePlaceholder: "e.g. John Doe",
    currentFile: "Current:",
    styleExecutive: "Executive",
    styleNormal: "General",
    editProfileHint: "Edit profile",
    deleteProfileHint: "Delete profile",
    confirmDeleteProfile: "Delete this profile?",
    failedDeleteProfile: "Failed to delete profile",
    creatingProfile: "Creating...",
    savingProfile: "Saving...",
    failedCreateProfile: "Failed to create profile",
    failedUpdateProfile: "Failed to update profile",
    // App page
    profileLabel: "Profile:",
    noCvUploaded: "(No CV uploaded)",
    switchProfile: "Switch Profile",
    newTask: "New Task",
    labelVacancy: "Vacancy Description",
    vacancyPlaceholder: "Paste the job description here...",
    labelBackground: "Background Info (optional)",
    backgroundPlaceholder: "Additional context about your experience...",
    labelCvFileOverride: "CV File (optional override)",
    labelOutputFormat: "Output Format",
    labelCvStyle: "CV Style",
    createTask: "Create Task",
    creatingTask: "Creating...",
    tasksTitle: "Tasks",
    noTasks: "No tasks yet. Create one above.",
    unknownCompany: "Unknown company",
    downloadCvHint: "Download CV",
    downloadClHint: "Download Cover Letter",
    deleteTaskHint: "Delete task",
    confirmDeleteTask: "Delete this task?",
    failedDeleteTask: "Failed to delete task",
    failedCreateTask: "Failed to create task",
    cvHintUsingProfile: "Using profile CV: {0}. Upload here to override for this task.",
    cvHintNoProfile: "No CV in profile. Please upload one here.",
    // Detail page
    backToTasks: "Back to tasks",
    taskTitle: "Task #",
    labelCompany: "Company",
    labelCvFileDetail: "CV File",
    labelOutputFormatDetail: "Output Format",
    labelCvStyleDetail: "CV Style",
    labelCreated: "Created",
    labelUpdated: "Updated",
    labelVacancyDesc: "Vacancy Description",
    labelBackgroundInfo: "Background Info",
    labelChangesSummary: "Changes Summary",
    labelError: "Error",
    downloadCv: "Download CV",
    downloadCoverLetter: "Download Cover Letter",
    deleteTask: "Delete Task",
    taskNotFound: "Task not found.",
    failedDeleteTaskDetail: "Failed to delete task",
    // Statuses
    statusPending: "pending",
    statusProcessing: "processing",
    statusCompleted: "completed",
    statusFailed: "failed",
    networkError: "Network error: ",
  },
  de: {
    // Common
    appTitle: "Lebenslauf-Ersteller",
    // Login page
    loginSubtitle: "Profil auswaehlen oder ein neues erstellen",
    noProfiles: "Noch keine Profile. Erstellen Sie eines unten.",
    newProfile: "+ Neues Profil",
    newProfileTitle: "Neues Profil",
    editProfileTitle: "Profil bearbeiten",
    labelName: "Name",
    labelDefaultStyle: "Standardstil",
    labelCvFile: "CV-Datei",
    createProfile: "Profil erstellen",
    saveChanges: "Speichern",
    cancel: "Abbrechen",
    namePlaceholder: "z.B. Max Mustermann",
    currentFile: "Aktuell:",
    styleExecutive: "Executive",
    styleNormal: "Allgemein",
    editProfileHint: "Profil bearbeiten",
    deleteProfileHint: "Profil loeschen",
    confirmDeleteProfile: "Dieses Profil loeschen?",
    failedDeleteProfile: "Profil konnte nicht geloescht werden",
    creatingProfile: "Erstellen...",
    savingProfile: "Speichern...",
    failedCreateProfile: "Profil konnte nicht erstellt werden",
    failedUpdateProfile: "Profil konnte nicht aktualisiert werden",
    // App page
    profileLabel: "Profil:",
    noCvUploaded: "(Kein CV hochgeladen)",
    switchProfile: "Profil wechseln",
    newTask: "Neue Aufgabe",
    labelVacancy: "Stellenbeschreibung",
    vacancyPlaceholder: "Stellenbeschreibung hier einfuegen...",
    labelBackground: "Hintergrundinformationen (optional)",
    backgroundPlaceholder: "Zusaetzlicher Kontext zu Ihrer Erfahrung...",
    labelCvFileOverride: "CV-Datei (optionale Ueberschreibung)",
    labelOutputFormat: "Ausgabeformat",
    labelCvStyle: "CV-Stil",
    createTask: "Aufgabe erstellen",
    creatingTask: "Erstellen...",
    tasksTitle: "Aufgaben",
    noTasks: "Noch keine Aufgaben. Erstellen Sie eine oben.",
    unknownCompany: "Unbekanntes Unternehmen",
    downloadCvHint: "CV herunterladen",
    downloadClHint: "Anschreiben herunterladen",
    deleteTaskHint: "Aufgabe loeschen",
    confirmDeleteTask: "Diese Aufgabe loeschen?",
    failedDeleteTask: "Aufgabe konnte nicht geloescht werden",
    failedCreateTask: "Aufgabe konnte nicht erstellt werden",
    cvHintUsingProfile: "Profil-CV: {0}. Hier hochladen, um fuer diese Aufgabe zu ueberschreiben.",
    cvHintNoProfile: "Kein CV im Profil. Bitte hier hochladen.",
    // Detail page
    backToTasks: "Zurueck zu Aufgaben",
    taskTitle: "Aufgabe #",
    labelCompany: "Unternehmen",
    labelCvFileDetail: "CV-Datei",
    labelOutputFormatDetail: "Ausgabeformat",
    labelCvStyleDetail: "CV-Stil",
    labelCreated: "Erstellt",
    labelUpdated: "Aktualisiert",
    labelVacancyDesc: "Stellenbeschreibung",
    labelBackgroundInfo: "Hintergrundinformationen",
    labelChangesSummary: "Zusammenfassung der Aenderungen",
    labelError: "Fehler",
    downloadCv: "CV herunterladen",
    downloadCoverLetter: "Anschreiben herunterladen",
    deleteTask: "Aufgabe loeschen",
    taskNotFound: "Aufgabe nicht gefunden.",
    failedDeleteTaskDetail: "Aufgabe konnte nicht geloescht werden",
    // Statuses
    statusPending: "Ausstehend",
    statusProcessing: "In Bearbeitung",
    statusCompleted: "Abgeschlossen",
    statusFailed: "Fehlgeschlagen",
    networkError: "Netzwerkfehler: ",
  },
};

function getLang() {
  return localStorage.getItem("lang") || "en";
}

function setLang(lang) {
  localStorage.setItem("lang", lang);
  window.location.reload();
}

function t(key) {
  const lang = getLang();
  return (I18N[lang] && I18N[lang][key]) || I18N.en[key] || key;
}

function initLangSelector() {
  const sel = document.getElementById("lang-select");
  if (!sel) return;
  sel.value = getLang();
  sel.addEventListener("change", (e) => setLang(e.target.value));
  const title = document.getElementById("app-title");
  if (title) title.textContent = t("appTitle");
  document.title = t("appTitle");
}
