"use strict";

const $ = (id) => document.getElementById(id);
const token = document.querySelector('meta[name="pennovia-token"]').content;
const state = {
  sources: [], profile: null, draft: "", busy: false, review: null,
  sourceRevision: 0, profileRevision: 0, draftRevision: 0,
};
const buttons = ["analyze", "generate", "review", "download", "wordpress", "drive", "profile-save"];
const editableFields = [
  "url-input", "paste-input", "file-input", "author", "language", "profile-import",
  "topic", "content-type", "backend", "model", "draft", "export-title-input",
  "export-format", "add-urls", "add-text",
];
const remoteAttempts = new Map(); // Browser-session only; remote exactly-once is not guaranteed.
let noticeTimeout;

function notify(message, kind = "info") {
  const box = $("notice");
  box.textContent = message;
  box.className = "notice " + kind;
  box.hidden = false;
  clearTimeout(noticeTimeout);
  noticeTimeout = setTimeout(() => { box.hidden = true; }, 6500);
}

function setBusy(busy) {
  state.busy = busy;
  document.body.classList.toggle("is-busy", busy);
  updateControls();
}

function updateControls() {
  const hasProfile = Boolean(state.profile);
  const hasDraft = Boolean($("draft").value.trim());
  const enabled = {
    analyze: state.sources.length > 0,
    generate: hasProfile && Boolean($("topic").value.trim()),
    review: hasProfile && hasDraft,
    download: hasProfile && hasDraft,
    wordpress: hasProfile && hasDraft,
    drive: hasProfile && hasDraft,
    "profile-save": hasProfile,
  };
  for (const id of buttons) $(id).disabled = state.busy || !enabled[id];
  for (const id of editableFields) $(id).disabled = state.busy || (id === "model" && $("backend").value === "codex");
  for (const button of document.querySelectorAll("[data-source-tab], .source-remove")) {
    button.disabled = state.busy;
  }
}

function clearProfile() {
  state.sourceRevision++;
  if (!state.profile) return;
  state.profile = null;
  state.profileRevision++;
  $("profile-empty").hidden = false;
  $("profile-results").hidden = true;
  $("profile-state").textContent = "Reanalysis needed";
  $("profile-state").classList.remove("ready");
  clearReview();
  // Preserve the author's draft; losing a profile must never delete writing.
  notify("Sources or analysis settings changed. Analyze again before drafting or exporting.");
  updateControls();
}

async function api(path, payload, binary = false) {
  const response = await fetch(path, {
    method: "POST",
    headers: { "Content-Type": "application/json", "X-Pennovia-Token": token },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    let message = "Studio could not complete this action.";
    let outcome = response.status >= 500 ? "unknown" : "failed";
    try {
      const error = await response.json();
      message = error.error || message;
      outcome = error.outcome || outcome;
    } catch (_) { /* No readable error body. */ }
    const failure = new Error(message);
    failure.outcome = outcome;
    throw failure;
  }
  return binary ? response.blob() : response.json();
}

async function perform(action) {
  if (state.busy) return;
  setBusy(true);
  try { await action(); }
  catch (error) { notify(error.message || "Something went wrong.", "error"); }
  finally { setBusy(false); }
}

function addSource(entry) {
  if (state.sources.length >= 20) {
    notify("Studio accepts up to 20 writing samples per profile.", "error");
    return false;
  }
  state.sources.push(entry);
  clearProfile();
  renderSources();
  return true;
}

function renderSources() {
  const list = $("source-list");
  list.replaceChildren();
  $("source-counter").textContent = state.sources.length + " / 20";
  if (!state.sources.length) {
    const empty = document.createElement("p");
    empty.className = "list-empty";
    empty.textContent = "No writing samples yet.";
    list.append(empty);
  }
  for (const [index, item] of state.sources.entries()) {
    const row = document.createElement("div");
    row.className = "source-item";
    const icon = document.createElement("span");
    icon.className = "source-icon";
    icon.textContent = item.type === "url" ? "URL" : item.type === "file" ? "DOC" : "TXT";
    const label = document.createElement("span");
    label.className = "source-name";
    label.title = item.label;
    label.textContent = item.label;
    const remove = document.createElement("button");
    remove.type = "button";
    remove.className = "source-remove";
    remove.textContent = "×";
    remove.setAttribute("aria-label", "Remove " + item.label);
    remove.addEventListener("click", () => {
      if (state.busy) return;
      state.sources.splice(index, 1);
      clearProfile();
      renderSources();
    });
    row.append(icon, label, remove);
    list.append(row);
  }
  updateControls();
}

function selectTab(name) {
  if (state.busy) return;
  for (const button of document.querySelectorAll("[data-source-tab]")) {
    const active = button.dataset.sourceTab === name;
    button.classList.toggle("is-active", active);
    button.setAttribute("aria-selected", String(active));
    $("source-" + button.dataset.sourceTab).hidden = !active;
  }
}

for (const button of document.querySelectorAll("[data-source-tab]")) {
  button.addEventListener("click", () => selectTab(button.dataset.sourceTab));
}
$("add-urls").addEventListener("click", () => {
  if (state.busy) return;
  const links = $("url-input").value.split(/\r?\n/).map((s) => s.trim()).filter(Boolean);
  if (!links.length) return notify("Paste one or more article links.", "error");
  let added = 0;
  for (const link of links) {
    if (!/^https:\/\/[^ ]+/i.test(link)) {
      notify("Only public HTTPS article URLs are accepted.", "error");
      continue;
    }
    if (addSource({ type: "url", value: link, label: link })) added++;
  }
  if (added) {
    $("url-input").value = "";
    notify(added + " article link" + (added === 1 ? "" : "s") + " added.", "success");
  }
});

$("add-text").addEventListener("click", () => {
  if (state.busy) return;
  const value = $("paste-input").value.trim();
  if (value.split(/\s+/).length < 51) return notify("Add at least 51 words to each sample.", "error");
  const summary = value.replace(/\s+/g, " ").slice(0, 62);
  if (addSource({ type: "text", value, label: summary + (value.length > 62 ? "…" : "") })) {
    $("paste-input").value = "";
    notify("Writing sample added.", "success");
  }
});

function fileBase64(file) {
  return file.arrayBuffer().then((buffer) => {
    const bytes = new Uint8Array(buffer);
    const parts = [];
    for (let i = 0; i < bytes.length; i += 32768) {
      parts.push(String.fromCharCode(...bytes.subarray(i, i + 32768)));
    }
    return btoa(parts.join(""));
  });
}

$("file-input").addEventListener("change", (event) => perform(async () => {
  let added = 0;
  for (const file of event.target.files) {
    if (!/\.(txt|html|htm|pdf)$/i.test(file.name)) {
      notify("Use TXT, HTML or PDF files.", "error");
      continue;
    }
    if (file.size > 4 * 1024 * 1024) {
      notify(file.name + " exceeds the 4 MB limit.", "error");
      continue;
    }
    if (state.sources.length >= 20) {
      notify("Studio accepts up to 20 writing samples.", "error");
      break;
    }
    if (addSource({ type: "file", name: file.name, data: await fileBase64(file), label: file.name })) added++;
  }
  $("file-input").value = "";
  if (added) notify(added + " file" + (added === 1 ? "" : "s") + " added.", "success");
}));

for (const event of ["input"]) {
  $("author").addEventListener(event, () => { if (!state.busy) { clearProfile(); updateControls(); } });
}
$("language").addEventListener("change", () => {
  if (!state.busy) { clearProfile(); updateControls(); }
});

function renderProfile(data) {
  state.profile = data.profile;
  state.profileRevision++;
  clearReview();
  $("profile-empty").hidden = true;
  $("profile-results").hidden = false;
  $("profile-state").textContent = "Profile ready";
  $("profile-state").classList.add("ready");
  $("metric-words").textContent = data.profile.total_words.toLocaleString();
  $("metric-texts").textContent = data.profile.text_count + " writing samples";
  $("metric-sentence").textContent = String(data.profile.avg_sentence_words);
  $("metric-person").textContent = Math.round(data.profile.first_person_rate * 100) + "%";
  $("metric-vocab").textContent = Number(data.profile.vocabulary_richness).toFixed(2);
  const chips = $("transitions");
  chips.replaceChildren();
  const names = data.profile.top_transitions.slice(0, 8);
  if (!names.length) names.push("No recurring transitions detected");
  for (const name of names) {
    const chip = document.createElement("span");
    chip.className = "chip";
    chip.textContent = name;
    chips.append(chip);
  }
  const warning = $("profile-warnings");
  const messages = data.warnings || [];
  warning.textContent = messages.join("\n");
  warning.hidden = !messages.length;
  updateControls();
}

function clearReview() {
  state.review = null;
  $("review-empty").hidden = false;
  $("review-results").hidden = true;
}

function renderReview(review) {
  state.review = review;
  $("review-empty").hidden = true;
  $("review-results").hidden = false;
  $("review-score").textContent = String(review.score);
  $("score-fill").style.width = Math.max(0, Math.min(100, review.score)) + "%";
  $("review-verdict").textContent = review.passed
    ? "Above the heuristic threshold. Editorial review is still needed."
    : "Needs review. This score is a style indicator, not a judgment of quality.";
  const details = $("review-components");
  details.replaceChildren();
  const max = { Voice: 40, Transitions: 20, Structure: 20, "No clichés": 20 };
  for (const [name, value] of Object.entries(review.components)) {
    const item = document.createElement("div");
    item.className = "review-component";
    const caption = document.createElement("span");
    caption.textContent = name;
    const number = document.createElement("strong");
    number.textContent = value + " / " + max[name];
    item.append(caption, number);
    details.append(item);
  }
  $("review-issues").textContent = review.issues.length
    ? "Review notes: " + review.issues.join(" · ")
    : "No automated issues flagged.";
}

$("draft").addEventListener("input", () => {
  if (state.busy) return;
  const text = $("draft").value.trim();
  state.draftRevision++;
  state.draft = text;
  $("draft-words").textContent = (text ? text.split(/\s+/).length : 0) + " words";
  clearReview();
  updateControls();
});
$("topic").addEventListener("input", updateControls);
$("backend").addEventListener("change", () => {
  const codex = $("backend").value === "codex";
  if (codex) $("model").value = "";
  updateControls();
});

$("analyze").addEventListener("click", () => perform(async () => {
  const revision = state.sourceRevision;
  const data = await api("/api/analyze", {
    sources: state.sources.map(({ type, value, name, data }) => ({ type, value, name, data })),
    author: $("author").value.trim() || "My writing",
    language: $("language").value,
  });
  if (revision !== state.sourceRevision) throw new Error("Sources changed during analysis; analyze again.");
  renderProfile(data);
  $("profile-title").scrollIntoView({ behavior: "smooth", block: "start" });
  notify("Voice profile ready from " + data.accepted + " sample(s).", "success");
}));
$("profile-save").addEventListener("click", () => {
  if (!state.profile) return;
  downloadBlob(new Blob([JSON.stringify(state.profile, null, 2)], { type: "application/json" }), "pennovia-voice.json");
});
$("profile-import").addEventListener("change", (event) => perform(async () => {
  const file = event.target.files[0];
  if (!file) return;
  try {
    if (file.size > 2 * 1024 * 1024) throw new Error("Profile exceeds 2 MB.");
    const json = JSON.parse(await file.text());
    const data = await api("/api/profile", { profile: json });
    // Imported profiles are independent of any unsubmitted source collection.
    state.sources = [];
    clearProfile();
    renderSources();
    $("author").value = data.profile.author_name;
    $("language").value = data.profile.language;
    renderProfile(data);
    notify("Voice profile loaded. Existing draft preserved; review it again.", "success");
  } finally {
    $("profile-import").value = ""; // Re-selecting the same file must work after a failure.
  }
}));
$("generate").addEventListener("click", () => {
  if (state.busy) return;
  if ($("draft").value.trim() && !window.confirm(
    "Replace the current draft with a new model response? Download it first if needed."
  )) return;
  perform(async () => {
  const profileRevision = state.profileRevision;
  const draftRevision = state.draftRevision;
  const result = await api("/api/generate", {
    profile: state.profile,
    topic: $("topic").value.trim(),
    content_type: $("content-type").value,
    backend: $("backend").value,
    model: $("model").value.trim(),
  });
  if (profileRevision !== state.profileRevision || draftRevision !== state.draftRevision) {
    throw new Error("Profile or draft changed during generation; response discarded.");
  }
  $("draft").value = result.draft;
  state.draftRevision++;
  $("draft-words").textContent = result.draft.trim().split(/\s+/).length + " words";
  state.draft = result.draft;
  if (!$("export-title-input").value) $("export-title-input").value = $("topic").value.trim();
  renderReview(result.review);
  updateControls();
  $("draft").scrollIntoView({ behavior: "smooth", block: "center" });
  notify("Draft ready for your editorial review.", "success");
  });
});
$("review").addEventListener("click", () => perform(async () => {
  const profileRevision = state.profileRevision;
  const draftRevision = state.draftRevision;
  const reviewed = await api("/api/review", { profile: state.profile, draft: $("draft").value });
  if (profileRevision !== state.profileRevision || draftRevision !== state.draftRevision) {
    throw new Error("Text changed during review; old score discarded.");
  }
  renderReview(reviewed);
  notify("Style review updated.", "success");
}));

function downloadBlob(blob, filename) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.append(link);
  link.click();
  link.remove();
  setTimeout(() => URL.revokeObjectURL(url), 3000);
}
function exportPayload(destination) {
  return {
    profile: state.profile,
    draft: $("draft").value,
    title: $("export-title-input").value.trim() || $("topic").value.trim() || "Untitled draft",
    format: $("export-format").value,
    destination,
  };
}
$("download").addEventListener("click", () => perform(async () => {
  const format = $("export-format").value;
  const blob = await api("/api/export", exportPayload("download"), true);
  downloadBlob(blob, "pennovia-draft." + format);
  notify("Downloaded " + format.toUpperCase() + " draft.", "success");
}));
function sendRemote(destination) {
  if (state.busy) return;
  const payload = exportPayload(destination);
  const key = JSON.stringify(payload);
  const previous = remoteAttempts.get(key);
  if (previous && !window.confirm(
    previous === "unknown"
      ? "The previous request may have succeeded. Check your " + destination +
        " account before retrying; another submission may create a duplicate. Retry?"
      : "This exact draft was already sent to " + destination + ". Send another copy?"
  )) return;
  if (destination === "wordpress" && !window.confirm(
    "Create a WordPress DRAFT? This does not publish the post."
  )) return;
  perform(async () => {
    remoteAttempts.set(key, "unknown"); // Network loss can hide a successful remote write.
    try {
      const result = await api("/api/export", payload);
      remoteAttempts.set(key, "confirmed");
      notify(result.message + ": " + result.url, "success");
    } catch (error) {
      if (error.outcome === "failed") remoteAttempts.delete(key);
      if (!error.outcome || error.outcome === "unknown") {
        error.message += " Check the remote destination before trying again.";
      }
      throw error;
    }
  });
}
$("wordpress").addEventListener("click", () => sendRemote("wordpress"));
$("drive").addEventListener("click", () => sendRemote("google_drive"));
updateControls();
