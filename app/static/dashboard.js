(() => {
  "use strict";

  let state = null;
  let contentSaveTimer = null;
  const selectedInvitationIds = new Set();
  const $ = (selector, root = document) => root.querySelector(selector);
  const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

  const titles = {
    overview: "Overview",
    content: "Website Content",
    guests: "Guest Tracker",
    invitations: "Invitations",
    photos: "Photo Library",
    "run-sheet": "Run Sheet",
    checklist: "Checklist",
    budget: "Budget & Payments",
    vendors: "Vendors",
    access: "Client Access",
  };

  const simpleConfigs = {
    "run-sheet": {
      title: "Run-Sheet Item",
      endpoint: "/api/run-sheet/save",
      list: "run_sheet",
      fields: [
        ["start_time", "Time", "text"], ["title", "Item", "text", true], ["details", "Details", "textarea"],
        ["owner", "Owner", "text"], ["sort_order", "Sort order", "number"], ["done", "Complete", "checkbox"],
      ],
    },
    checklist: {
      title: "Checklist Task",
      endpoint: "/api/checklist/save",
      list: "checklist",
      fields: [
        ["title", "Task", "text", true], ["status", "Status", "select", false, ["not_started", "in_progress", "complete"]],
        ["due_date", "Due date", "date"], ["owner", "Owner", "text"], ["notes", "Notes", "textarea"],
      ],
    },
    budget: {
      title: "Budget Item",
      endpoint: "/api/budget/save",
      list: "budget",
      fields: [
        ["item", "Item", "text", true], ["category", "Category", "text"], ["vendor", "Vendor", "text"],
        ["estimated", "Estimated", "number"], ["actual", "Actual", "number"],
        ["payment_status", "Payment status", "select", false, ["not_due", "deposit_due", "part_paid", "paid", "overdue"]],
        ["due_date", "Due date", "date"], ["notes", "Notes", "textarea"],
      ],
    },
    vendors: {
      title: "Vendor",
      endpoint: "/api/vendors/save",
      list: "vendors",
      fields: [
        ["name", "Vendor name", "text", true], ["service", "Service", "text"], ["contact_name", "Contact name", "text"],
        ["email", "Email", "email"], ["phone", "Phone", "text"],
        ["status", "Status", "select", false, ["active", "quoted", "booked", "paid", "complete", "cancelled"]],
        ["notes", "Notes", "textarea"],
      ],
    },
  };

  function escapeHtml(value) {
    return String(value ?? "").replace(/[&<>'"]/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", "'": "&#39;", '"': "&quot;" }[char]));
  }

  function pretty(value) {
    return String(value ?? "").replaceAll("_", " ").replace(/\b\w/g, (character) => character.toUpperCase());
  }

  function dateTime(value) {
    if (!value) return "—";
    try { return new Intl.DateTimeFormat("en-NZ", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value)); }
    catch { return value; }
  }

  function currency(value) {
    return new Intl.NumberFormat("en-NZ", { style: "currency", currency: "NZD" }).format(Number(value || 0));
  }

  function fileSize(value) {
    const bytes = Number(value || 0);
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  }

  function toast(message, isError = false) {
    const node = $("#toast");
    node.textContent = message;
    node.style.background = isError ? "#8d3c3c" : "#132235";
    node.classList.add("show");
    clearTimeout(node._timer);
    node._timer = setTimeout(() => node.classList.remove("show"), 4200);
  }

  async function api(url, options = {}) {
    const config = { ...options, headers: { ...(options.headers || {}) } };
    if (config.body && !(config.body instanceof FormData) && typeof config.body !== "string") {
      config.headers["Content-Type"] = "application/json";
      config.body = JSON.stringify(config.body);
    }
    const response = await fetch(url, config);
    const contentType = response.headers.get("content-type") || "";
    const data = contentType.includes("application/json") ? await response.json().catch(() => ({})) : {};
    if (!response.ok || data.ok === false) throw new Error(data.error || `Request failed: ${response.status}`);
    return data;
  }

  async function loadState({ quiet = false } = {}) {
    try {
      state = await api("/api/dashboard/state");
      const validIds = new Set(state.parties.map((party) => party.id));
      for (const id of selectedInvitationIds) if (!validIds.has(id)) selectedInvitationIds.delete(id);
      renderAll();
      if (!quiet) $("#save-indicator").textContent = "Ready";
    } catch (error) {
      toast(error.message, true);
      $("#save-indicator").textContent = "Connection error";
    }
  }

  function showView(view) {
    $$(".nav-item").forEach((item) => item.classList.toggle("is-active", item.dataset.view === view));
    $$("[data-view-panel]").forEach((panel) => panel.classList.toggle("is-active", panel.dataset.viewPanel === view));
    $("#view-title").textContent = titles[view] || "Dashboard";
    $(".sidebar").classList.remove("open");
    history.replaceState(null, "", `#${view}`);
  }

  function renderAll() {
    if (!state) return;
    renderContentState();
    renderOverview();
    renderContent();
    renderGuests();
    renderInvitations();
    renderPhotos();
    renderRunSheet();
    renderChecklist();
    renderBudget();
    renderVendors();
    renderAccess();
  }

  function renderContentState() {
    const pending = state.content.has_pending_changes;
    const pill = $("#content-state");
    pill.textContent = pending ? "DRAFT CHANGES" : "LIVE CURRENT";
    pill.classList.toggle("pending", pending);
  }

  function metricCard(label, value, detail, view) {
    return `<article class="metric-card"><button type="button" data-metric-view="${view}"><small>${escapeHtml(label)}</small><strong>${escapeHtml(value)}</strong><span>${escapeHtml(detail)}</span></button></article>`;
  }

  function renderOverview() {
    const m = state.metrics;
    $("#metric-grid").innerHTML = [
      metricCard("Guest parties", m.parties, "active records", "guests"),
      metricCard("Confirmed attendees", m.confirmed_attendees, "currently attending", "guests"),
      metricCard("Needs follow-up", m.needs_follow_up, "host action needed", "guests"),
      metricCard("Invitation prepared", m.invitations_prepared, "ready in Gmail", "invitations"),
      metricCard("Invitations sent", m.invitations_sent, "manually confirmed", "invitations"),
      metricCard("Gallery photos", m.gallery_photos, "published photographs", "photos"),
      metricCard("Pending plus-ones", m.pending_plus_ones, "awaiting decision", "guests"),
      metricCard("Severe allergies", m.severe_allergies, "prominent safety flags", "guests"),
      metricCard("New submissions", m.new_submissions, "not yet reviewed", "guests"),
      metricCard("Budget actual", currency(m.budget_actual), `of ${currency(m.budget_estimated)} forecast`, "budget"),
    ].join("");

    const warnings = [];
    if (m.needs_follow_up) warnings.push(["Needs Follow-up", `${m.needs_follow_up} guest parties need host action.`, "guests"]);
    if (m.pending_plus_ones) warnings.push(["Pending Plus-Ones", `${m.pending_plus_ones} requests are awaiting a decision.`, "guests"]);
    if (m.severe_allergies) warnings.push(["Severe Allergies", `${m.severe_allergies} attendee records carry severe allergy flags.`, "guests"]);
    if (m.possible_duplicates) warnings.push(["Possible Duplicates", `${m.possible_duplicates} duplicate markers require review.`, "guests"]);
    if (state.content.has_pending_changes) warnings.push(["Unpublished Draft", "Website edits are saved but not yet live.", "content"]);
    if (!warnings.length) warnings.push(["No urgent warnings", "The dashboard has no active warning flags.", "overview"]);
    $("#warning-list").innerHTML = warnings.map(([title, text, view]) => `<button class="stack-item warning" data-jump="${view}"><h4>${escapeHtml(title)}</h4><p>${escapeHtml(text)}</p></button>`).join("");
    $("#activity-list").innerHTML = state.activity.length ? state.activity.map((item) => `<div class="activity-item"><p><strong>${escapeHtml(item.summary)}</strong></p><small>${escapeHtml(pretty(item.event_type))} · ${escapeHtml(dateTime(item.occurred_at))}</small></div>`).join("") : `<div class="empty">No activity recorded yet.</div>`;
  }

  function renderContent() {
    const form = $("#content-form");
    if (!form.dataset.loaded) {
      Object.entries(state.content.draft).forEach(([key, value]) => { if (form.elements[key]) form.elements[key].value = value; });
      form.dataset.loaded = "true";
    }
    $("#publication-history").innerHTML = state.publication_history.length ? state.publication_history.map((item) => `<article class="stack-item"><h4>Version ${item.id}</h4><p>${escapeHtml(dateTime(item.published_at))}</p><p>${escapeHtml(item.change_note || "No change note")}</p>${item.restored_from ? `<p>Restored from version ${item.restored_from}</p>` : ""}<button class="text-button" data-restore-publication="${item.id}">Restore this version</button></article>`).join("") : `<div class="empty">No publication history.</div>`;
  }

  async function saveDraft() {
    const fields = Object.fromEntries(new FormData($("#content-form")).entries());
    $("#save-indicator").textContent = "Saving draft…";
    try {
      await api("/api/content/draft", { method: "POST", body: { fields } });
      $("#save-indicator").textContent = "Draft saved";
      state.content.draft = fields;
      state.content.has_pending_changes = JSON.stringify(fields) !== JSON.stringify(state.content.live);
      renderContentState();
    } catch (error) {
      $("#save-indicator").textContent = "Save failed";
      toast(error.message, true);
    }
  }

  async function publishContent() {
    await saveDraft();
    try {
      await api("/api/content/publish", { method: "POST", body: { change_note: $("#publish-note").value.trim() } });
      $("#publish-note").value = "";
      $("#content-form").dataset.loaded = "";
      await loadState({ quiet: true });
      toast("Website changes published.");
    } catch (error) { toast(error.message, true); }
  }

  async function discardDraft() {
    if (!confirm("Discard all draft edits and return to the current live content?")) return;
    try {
      await api("/api/content/discard", { method: "POST", body: {} });
      $("#content-form").dataset.loaded = "";
      await loadState({ quiet: true });
      toast("Draft discarded.");
    } catch (error) { toast(error.message, true); }
  }

  async function restorePublication(id) {
    if (!confirm(`Restore publication ${id}?`)) return;
    try {
      await api(`/api/content/restore/${id}`, { method: "POST", body: {} });
      $("#content-form").dataset.loaded = "";
      await loadState({ quiet: true });
      toast(`Publication ${id} restored.`);
    } catch (error) { toast(error.message, true); }
  }

  function attendeeTags(attendee) {
    const tags = [];
    if (attendee.dietary_requirement) tags.push(`<span class="tag gold">Dietary</span>`);
    if (attendee.allergy_severity === "severe") tags.push(`<span class="tag red">Severe allergy</span>`);
    else if (attendee.allergy_information) tags.push(`<span class="tag gold">Allergy</span>`);
    if (attendee.accessibility_note) tags.push(`<span class="tag">Accessibility</span>`);
    return tags.join("");
  }

  function renderGuests() {
    const search = $("#guest-search").value.trim().toLowerCase();
    const response = $("#guest-response-filter").value;
    const workflow = $("#guest-workflow-filter").value;
    const showDeleted = $("#show-deleted").checked;
    const parties = state.parties.filter((party) => {
      if (showDeleted !== Boolean(party.deleted_at)) return false;
      if (response && party.guest_response !== response) return false;
      if (workflow && party.workflow_state !== workflow) return false;
      if (search) {
        const haystack = [party.party_name, party.contact_name, party.email, party.phone, ...party.attendees.map((attendee) => attendee.attendee_name)].join(" ").toLowerCase();
        if (!haystack.includes(search)) return false;
      }
      return true;
    });
    $("#guest-list").innerHTML = parties.length ? parties.map((party) => {
      const attendeeHtml = party.attendees.length ? party.attendees.map((attendee) => `<div class="attendee"><strong>${escapeHtml(attendee.attendee_name)}</strong><div class="tag-row"><span class="tag ${attendee.attendance_status === "attending" ? "green" : ""}">${escapeHtml(pretty(attendee.attendance_status))}</span>${attendeeTags(attendee)}</div>${attendee.dietary_requirement ? `<small>Dietary: ${escapeHtml(attendee.dietary_requirement)}</small>` : ""}${attendee.allergy_information ? `<small>Allergy: ${escapeHtml(attendee.allergy_information)}</small>` : ""}</div>`).join("") : `<div class="empty">No attendee records.</div>`;
      return `<article class="guest-card ${party.deleted_at ? "is-deleted" : ""}">
        <div class="guest-head"><div><h4>${escapeHtml(party.party_name)}</h4><div class="guest-meta"><span>${escapeHtml(party.contact_name || "No contact name")}</span><span>${escapeHtml(party.email || "No email")}</span><span>${escapeHtml(party.phone || "No phone")}</span></div></div><div class="tag-row"><span class="tag ${party.guest_response === "attending" ? "green" : party.guest_response === "not_attending" ? "red" : "gold"}">${escapeHtml(pretty(party.guest_response))}</span><span class="tag">${escapeHtml(pretty(party.workflow_state))}</span><span class="tag ${party.invitation_status === "sent" ? "green" : party.invitation_status === "prepared" ? "gold" : ""}">${escapeHtml(pretty(party.invitation_status))}</span>${party.plus_one_status === "pending" ? `<span class="tag gold">Pending plus-one</span>` : ""}${party.deleted_at ? `<span class="tag red">Deleted</span>` : ""}</div></div>
        <div class="guest-details"><div><p><strong>Party notes</strong></p><p>${escapeHtml(party.party_note || "—")}</p><p><strong>Private host notes</strong></p><p>${escapeHtml(party.host_notes || "—")}</p></div><div class="attendee-list">${attendeeHtml}</div></div>
        <div class="guest-actions">${party.deleted_at ? `<button class="button button-secondary" data-restore-party="${party.id}">Restore</button>` : `<button class="button button-secondary" data-edit-party="${party.id}">Edit</button><button class="button button-danger" data-delete-party="${party.id}">Delete</button>`}</div>
      </article>`;
    }).join("") : `<div class="empty">No guest parties match this view.</div>`;
  }

  function attendeeRow(attendee = {}) {
    const wrapper = document.createElement("div");
    wrapper.className = "attendee-edit-row";
    wrapper.innerHTML = `<div class="form-grid"><label>Attendee name<input data-attendee="attendee_name" value="${escapeHtml(attendee.attendee_name || "")}"></label><label>Attendance<select data-attendee="attendance_status"><option>attending</option><option>unsure</option><option>not_attending</option></select></label><label>Dietary requirement<input data-attendee="dietary_requirement" value="${escapeHtml(attendee.dietary_requirement || "")}"></label><label>Allergy information<input data-attendee="allergy_information" value="${escapeHtml(attendee.allergy_information || "")}"></label><label>Allergy severity<select data-attendee="allergy_severity"><option>none</option><option>mild</option><option>moderate</option><option>severe</option></select></label><label>Accessibility note<input data-attendee="accessibility_note" value="${escapeHtml(attendee.accessibility_note || "")}"></label></div><label>Private attendee note<textarea data-attendee="private_note" rows="2">${escapeHtml(attendee.private_note || "")}</textarea></label><button type="button" class="text-button danger remove-attendee">Remove attendee</button>`;
    $("[data-attendee='attendance_status']", wrapper).value = attendee.attendance_status || "attending";
    $("[data-attendee='allergy_severity']", wrapper).value = attendee.allergy_severity || "none";
    $(".remove-attendee", wrapper).addEventListener("click", () => wrapper.remove());
    $("#attendee-editor").append(wrapper);
  }

  function openPartyDialog(party = null) {
    const form = $("#party-form");
    form.reset();
    form.elements.id.value = party?.id || "";
    for (const field of ["party_name", "contact_name", "email", "phone", "guest_response", "workflow_state", "plus_one_status", "plus_one_name", "party_note", "host_notes"]) {
      if (form.elements[field]) form.elements[field].value = party?.[field] || (field === "guest_response" ? "unsure" : field === "workflow_state" ? "new" : field === "plus_one_status" ? "not_applicable" : "");
    }
    $("#attendee-editor").innerHTML = "";
    (party?.attendees?.length ? party.attendees : [{}]).forEach(attendeeRow);
    $("#party-dialog-title").textContent = party ? `Edit ${party.party_name}` : "Add Party";
    $("#party-dialog").showModal();
  }

  async function submitParty(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = Object.fromEntries(new FormData(form).entries());
    data.id = data.id ? Number(data.id) : null;
    data.plus_one_requested = data.plus_one_status !== "not_applicable";
    data.attendees = $$(".attendee-edit-row", $("#attendee-editor")).map((row) => Object.fromEntries($$("[data-attendee]", row).map((field) => [field.dataset.attendee, field.value]))).filter((attendee) => attendee.attendee_name.trim());
    try {
      await api("/api/parties/save", { method: "POST", body: data });
      $("#party-dialog").close();
      await loadState({ quiet: true });
      toast("Guest party saved.");
    } catch (error) { toast(error.message, true); }
  }

  async function deleteParty(id) {
    const reason = prompt("Reason for moving this party to Deleted Records:", "Duplicate or no longer required") ?? "";
    if (!reason && !confirm("Delete without a reason?")) return;
    try { await api(`/api/parties/${id}/delete`, { method: "POST", body: { reason } }); await loadState({ quiet: true }); toast("Party moved to Deleted Records."); }
    catch (error) { toast(error.message, true); }
  }

  async function restoreParty(id) {
    try { await api(`/api/parties/${id}/restore`, { method: "POST", body: {} }); await loadState({ quiet: true }); toast("Party restored."); }
    catch (error) { toast(error.message, true); }
  }

  async function importGuestCsv(file) {
    const formData = new FormData();
    formData.append("csv_file", file);
    $("#save-indicator").textContent = "Importing guests…";
    try {
      const result = await api("/api/parties/import-csv", { method: "POST", body: formData });
      await loadState({ quiet: true });
      const suffix = result.errors?.length ? ` ${result.errors.slice(0, 3).join(" ")}` : "";
      toast(`Imported ${result.created} parties; ${result.skipped} skipped.${suffix}`, Boolean(result.errors?.length));
    } catch (error) { toast(error.message, true); }
    finally { $("#save-indicator").textContent = "Ready"; $("#guest-csv-file").value = ""; }
  }

  function activeInvitationParties() {
    return state.parties.filter((party) => !party.deleted_at && /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(party.email || ""));
  }

  function invitationTag(status) {
    const className = status === "sent" ? "green" : status === "prepared" ? "gold" : "";
    return `<span class="tag ${className}">${escapeHtml(pretty(status))}</span>`;
  }

  function renderInvitations() {
    const settings = state.invitations.settings;
    const form = $("#invitation-form");
    if (!form.dataset.loaded) {
      form.elements.invitation_subject.value = settings.invitation_subject || "";
      form.elements.invitation_message.value = settings.invitation_message || "";
      form.elements.event_site_link.value = settings.event_site_link || "";
      form.dataset.loaded = "true";
    }
    const parties = activeInvitationParties();
    $("#invitation-list").innerHTML = parties.length ? parties.map((party) => `<label class="invitation-row"><input type="checkbox" data-invitation-party="${party.id}" ${selectedInvitationIds.has(party.id) ? "checked" : ""}><span><strong>${escapeHtml(party.party_name)}</strong><small>${escapeHtml(party.email)} · ${escapeHtml(pretty(party.guest_response))} · ${escapeHtml(pretty(party.workflow_state))}</small></span>${invitationTag(party.invitation_status)}</label>`).join("") : `<div class="empty">No active guest records contain email addresses.</div>`;
    updateInvitationCount();
  }

  function updateInvitationCount() {
    $("#invitation-selection-count").textContent = `${selectedInvitationIds.size} selected`;
  }

  function selectInvitations(mode) {
    selectedInvitationIds.clear();
    for (const party of activeInvitationParties()) {
      if (mode === "all" || (mode === "attending" && party.guest_response === "attending") || (mode === "unsure" && party.guest_response === "unsure") || (mode === "follow-up" && party.workflow_state === "needs_follow_up")) selectedInvitationIds.add(party.id);
    }
    renderInvitations();
  }

  function selectedParties() {
    return activeInvitationParties().filter((party) => selectedInvitationIds.has(party.id));
  }

  async function saveInvitationSettings({ quiet = false } = {}) {
    const data = Object.fromEntries(new FormData($("#invitation-form")).entries());
    await api("/api/invitations/settings", { method: "POST", body: data });
    state.invitations.settings = data;
    if (!quiet) toast("Invitation text saved.");
    return data;
  }

  function copyText(text) {
    if (navigator.clipboard?.writeText) return navigator.clipboard.writeText(text);
    const area = document.createElement("textarea");
    area.value = text;
    document.body.append(area);
    area.select();
    document.execCommand("copy");
    area.remove();
    return Promise.resolve();
  }

  async function copyBcc() {
    const emails = selectedParties().map((party) => party.email).filter(Boolean);
    if (!emails.length) return toast("Select at least one guest with an email address.", true);
    await copyText(emails.join(", "));
    toast(`Copied ${emails.length} BCC recipients.`);
  }

  function exportRecipientCsv() {
    const parties = selectedParties();
    if (!parties.length) return toast("Select at least one guest with an email address.", true);
    const quote = (value) => `"${String(value ?? "").replaceAll('"', '""')}"`;
    const rows = [["party_name", "contact_name", "email", "guest_response", "workflow_state", "invitation_status"], ...parties.map((party) => [party.party_name, party.contact_name, party.email, party.guest_response, party.workflow_state, party.invitation_status])];
    const csv = rows.map((row) => row.map(quote).join(",")).join("\r\n");
    const link = document.createElement("a");
    link.href = URL.createObjectURL(new Blob([csv], { type: "text/csv;charset=utf-8" }));
    link.download = "event-command-center-invitation-recipients.csv";
    link.click();
    URL.revokeObjectURL(link.href);
  }

  async function prepareInvitationEmail() {
    const ids = [...selectedInvitationIds];
    if (!ids.length) return toast("Select at least one guest with an email address.", true);
    const composeWindow = window.open("about:blank", "_blank");
    try {
      const settings = await saveInvitationSettings({ quiet: true });
      const result = await api("/api/invitations/prepare", { method: "POST", body: { party_ids: ids } });
      const emails = result.recipients.map((recipient) => recipient.email).filter(Boolean);
      if (!emails.length) throw new Error("No valid email addresses were selected.");
      const body = [settings.invitation_message, settings.event_site_link].filter(Boolean).join("\n\n");
      const query = new URLSearchParams({ view: "cm", fs: "1", bcc: emails.join(","), su: settings.invitation_subject || "", body });
      const gmailUrl = `https://mail.google.com/mail/?${query.toString()}`;
      if (composeWindow) composeWindow.location.href = gmailUrl;
      else window.location.href = gmailUrl;
      await loadState({ quiet: true });
      toast(`Prepared an invitation email for ${emails.length} parties.`);
    } catch (error) {
      if (composeWindow) composeWindow.close();
      toast(error.message, true);
    }
  }

  async function setInvitationStatus(status) {
    const ids = [...selectedInvitationIds];
    if (!ids.length) return toast("Select at least one guest party.", true);
    try {
      await api("/api/invitations/status", { method: "POST", body: { party_ids: ids, status } });
      await loadState({ quiet: true });
      toast(`Selected invitations marked ${pretty(status)}.`);
    } catch (error) { toast(error.message, true); }
  }

  function renderPhotos() {
    const publicCount = state.photos.filter((photo) => photo.show_in_gallery).length;
    $("#photo-summary").innerHTML = `<span class="tag green">Gallery: ${publicCount}</span><span class="tag">Private: ${state.photos.length - publicCount}</span><span class="tag">Total: ${state.photos.length}</span>`;
    $("#photo-grid").innerHTML = state.photos.length ? state.photos.map((photo) => `<article class="photo-card ${photo.show_in_gallery ? "is-public" : ""}" data-photo-id="${escapeHtml(photo.photo_id)}">
      <img loading="lazy" src="${escapeHtml(photo.thumbnail_url)}" alt="${escapeHtml(photo.alt_text || "")}">
      <div class="photo-body">
        <strong class="photo-name">${escapeHtml(photo.original_filename)}</strong>
        <div class="photo-meta"><span>${escapeHtml(`${photo.width} × ${photo.height}`)}</span><span>${escapeHtml(fileSize(photo.file_size))}</span></div>
        <label class="photo-toggle"><span>Show in Gallery</span><input class="photo-gallery-toggle" type="checkbox" ${photo.show_in_gallery ? "checked" : ""}></label>
        <label>Caption<textarea class="photo-caption" rows="2">${escapeHtml(photo.comment || "")}</textarea></label>
        <label>Alt text<input class="photo-alt" value="${escapeHtml(photo.alt_text || "")}" placeholder="Describe the photograph"></label>
        <label>Display order<input class="photo-order" type="number" value="${Number(photo.display_order || 0)}"></label>
        <div class="photo-actions"><button class="button button-secondary save-photo" type="button">Save Photo</button><button class="button button-danger delete-photo" type="button">Delete Permanently</button></div>
      </div>
    </article>`).join("") : `<div class="empty">No client photographs uploaded yet.</div>`;
  }

  async function uploadPhotos(files) {
    const list = [...files].filter((file) => file.size > 0);
    if (!list.length) return;
    const formData = new FormData();
    list.forEach((file) => formData.append("photos", file));
    $("#photo-upload-progress").textContent = `Uploading and processing ${list.length} photograph${list.length === 1 ? "" : "s"}…`;
    try {
      const result = await api("/api/photos/upload", { method: "POST", body: formData });
      await loadState({ quiet: true });
      const errorText = result.errors?.length ? ` ${result.errors.join(" ")}` : "";
      $("#photo-upload-progress").textContent = `${result.saved} photograph${result.saved === 1 ? "" : "s"} uploaded.${errorText}`;
      toast(`${result.saved} photograph${result.saved === 1 ? "" : "s"} uploaded.`, Boolean(result.errors?.length));
    } catch (error) {
      $("#photo-upload-progress").textContent = error.message;
      toast(error.message, true);
    } finally {
      $("#photo-upload-input").value = "";
    }
  }

  async function savePhoto(card) {
    try {
      await api("/api/photos/save", {
        method: "POST",
        body: {
          photo_id: card.dataset.photoId,
          show_in_gallery: $(".photo-gallery-toggle", card).checked,
          caption: $(".photo-caption", card).value,
          alt_text: $(".photo-alt", card).value,
          display_order: $(".photo-order", card).value,
        },
      });
      await loadState({ quiet: true });
      toast("Photo settings saved.");
    } catch (error) { toast(error.message, true); }
  }

  async function deletePhoto(card) {
    const name = $(".photo-name", card)?.textContent || "this photo";
    if (!confirm(`Permanently delete ${name}? This removes the original, display image and thumbnail.`)) return;
    try {
      await api(`/api/photos/${encodeURIComponent(card.dataset.photoId)}/delete`, { method: "POST", body: {} });
      await loadState({ quiet: true });
      toast("Photo permanently deleted.");
    } catch (error) { toast(error.message, true); }
  }

  function renderRunSheet() {
    $("#run-sheet-table").innerHTML = state.run_sheet.length ? state.run_sheet.map((item) => `<tr><td>${escapeHtml(item.start_time || "—")}</td><td><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.details || "")}</small></td><td>${escapeHtml(item.owner || "—")}</td><td><span class="tag ${item.done ? "green" : "gold"}">${item.done ? "Complete" : "Open"}</span></td><td><div class="table-actions"><button class="text-button" data-edit-simple="run-sheet" data-id="${item.id}">Edit</button><button class="text-button danger" data-delete-simple="run-sheet" data-id="${item.id}">Delete</button></div></td></tr>`).join("") : `<tr><td colspan="5"><div class="empty">No run-sheet items yet.</div></td></tr>`;
  }

  function renderChecklist() {
    $("#checklist-table").innerHTML = state.checklist.length ? state.checklist.map((item) => `<tr><td><strong>${escapeHtml(item.title)}</strong><br><small>${escapeHtml(item.notes || "")}</small></td><td>${escapeHtml(item.owner || "—")}</td><td>${escapeHtml(item.due_date || "—")}</td><td><span class="tag ${item.status === "complete" ? "green" : item.status === "in_progress" ? "gold" : ""}">${escapeHtml(pretty(item.status))}</span></td><td><div class="table-actions"><button class="text-button" data-edit-simple="checklist" data-id="${item.id}">Edit</button><button class="text-button danger" data-delete-simple="checklist" data-id="${item.id}">Delete</button></div></td></tr>`).join("") : `<tr><td colspan="5"><div class="empty">No checklist tasks yet.</div></td></tr>`;
  }

  function renderBudget() {
    const estimated = state.budget.reduce((sum, item) => sum + Number(item.estimated || 0), 0);
    const actual = state.budget.reduce((sum, item) => sum + Number(item.actual || 0), 0);
    $("#budget-totals").innerHTML = `<article class="total-card"><small>Estimated</small><strong>${currency(estimated)}</strong></article><article class="total-card"><small>Actual</small><strong>${currency(actual)}</strong></article><article class="total-card"><small>Difference</small><strong>${currency(estimated - actual)}</strong></article>`;
    $("#budget-table").innerHTML = state.budget.length ? state.budget.map((item) => `<tr><td><strong>${escapeHtml(item.item)}</strong><br><small>${escapeHtml(item.category || "")}</small></td><td>${escapeHtml(item.vendor || "—")}</td><td>${currency(item.estimated)}</td><td>${currency(item.actual)}</td><td><span class="tag ${item.payment_status === "paid" ? "green" : item.payment_status === "overdue" ? "red" : "gold"}">${escapeHtml(pretty(item.payment_status))}</span></td><td><div class="table-actions"><button class="text-button" data-edit-simple="budget" data-id="${item.id}">Edit</button><button class="text-button danger" data-delete-simple="budget" data-id="${item.id}">Delete</button></div></td></tr>`).join("") : `<tr><td colspan="6"><div class="empty">No budget items yet.</div></td></tr>`;
  }

  function renderVendors() {
    $("#vendor-grid").innerHTML = state.vendors.length ? state.vendors.map((item) => `<article class="vendor-card"><div class="guest-head"><div><h4>${escapeHtml(item.name)}</h4><p>${escapeHtml(item.service || "Service not entered")}</p></div><span class="tag ${item.status === "booked" || item.status === "paid" ? "green" : ""}">${escapeHtml(pretty(item.status))}</span></div><p><strong>${escapeHtml(item.contact_name || "No contact name")}</strong></p><p>${escapeHtml(item.email || "No email")}</p><p>${escapeHtml(item.phone || "No phone")}</p><p>${escapeHtml(item.notes || "")}</p><div class="guest-actions"><button class="button button-secondary" data-edit-simple="vendors" data-id="${item.id}">Edit</button><button class="button button-danger" data-delete-simple="vendors" data-id="${item.id}">Delete</button></div></article>`).join("") : `<div class="empty">No vendor records yet.</div>`;
  }

  function renderAccess() {
    const access = state.client_access || {};
    const value = access.value || "not_configured";
    $("#access-state-label").textContent = pretty(value);
    $("#access-explanation").textContent = access.configured ? `Last recorded client-access state: ${pretty(value)}.` : "No external tunnel command is configured. The guest site and dashboard still work on the LAN.";
    $("#access-callout").textContent = access.configured ? "These buttons run only fixed operator-configured commands on this instance." : "Disabled by default. Configure independently reviewed absolute-path commands to activate these controls.";
    $("#open-client-access").disabled = !access.configured;
    $("#close-client-access").disabled = !access.configured;
    $("#check-client-access").disabled = !access.configured;
    $("#access-dot").className = `status-dot ${value === "open" ? "is-open" : value === "close" || value === "closed" ? "is-closed" : ""}`;
  }

  async function clientAccessAction(action) {
    try {
      const result = await api(`/api/client-access/${action}`, { method: "POST", body: {} });
      await loadState({ quiet: true });
      toast(result.output || `Client access ${action} complete.`);
    } catch (error) { toast(error.message, true); }
  }

  function fieldHtml(field) {
    const [name, label, type, required, options] = field;
    if (type === "textarea") return `<label>${label}<textarea name="${name}" rows="4" ${required ? "required" : ""}></textarea></label>`;
    if (type === "select") return `<label>${label}<select name="${name}">${options.map((option) => `<option value="${option}">${pretty(option)}</option>`).join("")}</select></label>`;
    if (type === "checkbox") return `<label class="check-label"><input type="checkbox" name="${name}"> ${label}</label>`;
    return `<label>${label}<input type="${type}" name="${name}" ${type === "number" ? 'step="0.01"' : ""} ${required ? "required" : ""}></label>`;
  }

  function openSimpleDialog(module, item = null) {
    const config = simpleConfigs[module];
    const form = $("#simple-form");
    form.reset();
    form.elements.module.value = module;
    form.elements.id.value = item?.id || "";
    $("#simple-dialog-title").textContent = `${item ? "Edit" : "Add"} ${config.title}`;
    $("#simple-fields").innerHTML = config.fields.map(fieldHtml).join("");
    if (item) config.fields.forEach(([name, , type]) => { if (form.elements[name]) { if (type === "checkbox") form.elements[name].checked = Boolean(item[name]); else form.elements[name].value = item[name] ?? ""; } });
    $("#simple-dialog").showModal();
  }

  async function submitSimple(event) {
    event.preventDefault();
    const form = event.currentTarget;
    const module = form.elements.module.value;
    const config = simpleConfigs[module];
    const data = Object.fromEntries(new FormData(form).entries());
    config.fields.filter((field) => field[2] === "checkbox").forEach(([name]) => data[name] = form.elements[name].checked);
    data.id = data.id ? Number(data.id) : null;
    delete data.module;
    try {
      await api(config.endpoint, { method: "POST", body: data });
      $("#simple-dialog").close();
      await loadState({ quiet: true });
      toast(`${config.title} saved.`);
    } catch (error) { toast(error.message, true); }
  }

  async function deleteSimple(module, id) {
    if (!confirm("Delete this item?")) return;
    const route = { "run-sheet": "run-sheet", checklist: "checklist", budget: "budget", vendors: "vendors" }[module];
    try { await api(`/api/${route}/${id}/delete`, { method: "POST", body: {} }); await loadState({ quiet: true }); toast("Item deleted."); }
    catch (error) { toast(error.message, true); }
  }

  document.addEventListener("click", (event) => {
    const nav = event.target.closest("[data-view]"); if (nav) showView(nav.dataset.view);
    const jump = event.target.closest("[data-jump]"); if (jump) showView(jump.dataset.jump);
    const metric = event.target.closest("[data-metric-view]"); if (metric) showView(metric.dataset.metricView);
    const editParty = event.target.closest("[data-edit-party]"); if (editParty) openPartyDialog(state.parties.find((party) => party.id === Number(editParty.dataset.editParty)));
    const deleteButton = event.target.closest("[data-delete-party]"); if (deleteButton) deleteParty(deleteButton.dataset.deleteParty);
    const restoreButton = event.target.closest("[data-restore-party]"); if (restoreButton) restoreParty(restoreButton.dataset.restoreParty);
    const savePhotoButton = event.target.closest(".save-photo"); if (savePhotoButton) savePhoto(savePhotoButton.closest(".photo-card"));
    const deletePhotoButton = event.target.closest(".delete-photo"); if (deletePhotoButton) deletePhoto(deletePhotoButton.closest(".photo-card"));
    const restorePublicationButton = event.target.closest("[data-restore-publication]"); if (restorePublicationButton) restorePublication(restorePublicationButton.dataset.restorePublication);
    const addSimple = event.target.closest("[data-add-simple]"); if (addSimple) openSimpleDialog(addSimple.dataset.addSimple);
    const editSimple = event.target.closest("[data-edit-simple]"); if (editSimple) { const module = editSimple.dataset.editSimple; const config = simpleConfigs[module]; openSimpleDialog(module, state[config.list].find((item) => item.id === Number(editSimple.dataset.id))); }
    const deleteSimpleButton = event.target.closest("[data-delete-simple]"); if (deleteSimpleButton) deleteSimple(deleteSimpleButton.dataset.deleteSimple, deleteSimpleButton.dataset.id);
    const quickSelect = event.target.closest("[data-select-invitations]"); if (quickSelect) selectInvitations(quickSelect.dataset.selectInvitations);
  });

  document.addEventListener("change", (event) => {
    const invitationCheckbox = event.target.closest("[data-invitation-party]");
    if (invitationCheckbox) {
      const id = Number(invitationCheckbox.dataset.invitationParty);
      if (invitationCheckbox.checked) selectedInvitationIds.add(id); else selectedInvitationIds.delete(id);
      updateInvitationCount();
    }
  });

  $(".menu-toggle").addEventListener("click", () => $(".sidebar").classList.toggle("open"));
  $("#content-form").addEventListener("input", () => { $("#save-indicator").textContent = "Draft changed"; clearTimeout(contentSaveTimer); contentSaveTimer = setTimeout(saveDraft, 750); });
  $("#publish-content").addEventListener("click", publishContent);
  $("#discard-draft").addEventListener("click", discardDraft);
  $("#add-party").addEventListener("click", () => openPartyDialog());
  $("#add-attendee").addEventListener("click", () => attendeeRow());
  $("#party-form").addEventListener("submit", submitParty);
  $("#simple-form").addEventListener("submit", submitSimple);
  ["#guest-search", "#guest-response-filter", "#guest-workflow-filter", "#show-deleted"].forEach((selector) => $(selector).addEventListener("input", renderGuests));

  $("#import-guests").addEventListener("click", () => $("#guest-csv-file").click());
  $("#guest-csv-file").addEventListener("change", (event) => { if (event.target.files[0]) importGuestCsv(event.target.files[0]); });

  $("#save-invitation-settings").addEventListener("click", () => saveInvitationSettings().catch((error) => toast(error.message, true)));
  $("#copy-bcc").addEventListener("click", () => copyBcc().catch((error) => toast(error.message, true)));
  $("#export-recipient-csv").addEventListener("click", exportRecipientCsv);
  $("#prepare-invitation-email").addEventListener("click", prepareInvitationEmail);
  $("#mark-invitations-sent").addEventListener("click", () => setInvitationStatus("sent"));
  $("#reset-invitation-status").addEventListener("click", () => setInvitationStatus("not_prepared"));

  const dropzone = $("#photo-dropzone");
  const uploadInput = $("#photo-upload-input");
  dropzone.addEventListener("click", () => uploadInput.click());
  dropzone.addEventListener("keydown", (event) => { if (event.key === "Enter" || event.key === " ") { event.preventDefault(); uploadInput.click(); } });
  uploadInput.addEventListener("change", (event) => uploadPhotos(event.target.files));
  for (const eventName of ["dragenter", "dragover"]) dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.add("is-dragging"); });
  for (const eventName of ["dragleave", "drop"]) dropzone.addEventListener(eventName, (event) => { event.preventDefault(); dropzone.classList.remove("is-dragging"); });
  dropzone.addEventListener("drop", (event) => uploadPhotos(event.dataTransfer.files));

  $("#open-client-access").addEventListener("click", () => clientAccessAction("open"));
  $("#close-client-access").addEventListener("click", () => clientAccessAction("close"));
  $("#check-client-access").addEventListener("click", () => clientAccessAction("status"));

  const initial = location.hash.slice(1);
  if (titles[initial]) showView(initial);
  loadState();
})();
