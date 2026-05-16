const $ = (id) => document.getElementById(id);

const statusCard = $("status-card");
const statusLine = $("status-line");
const summary = $("summary");
const messages = $("messages");
const validateBtn = $("validate-btn");
const sendBtn = $("send-btn");
const form = $("mail-form");

function clearOutput() {
  summary.innerHTML = "";
  messages.innerHTML = "";
}

function setBusy(isBusy) {
  validateBtn.disabled = isBusy;
  sendBtn.disabled = isBusy;
}

function showStatus(ok, text) {
  statusCard.hidden = false;
  statusLine.textContent = text;
  statusLine.className = `status-line ${ok ? "ok" : "bad"}`;
}

function addItem(label, value) {
  if (value === undefined || value === null || value === "") return;
  const dt = document.createElement("dt");
  dt.textContent = label;
  const dd = document.createElement("dd");
  dd.innerHTML = value;
  summary.append(dt, dd);
}

function renderMessages(items, kind) {
  if (!items || !items.length) return "";
  return `
    <ul class="list">
      ${items.map((item) => `<li class="${kind}">${escapeHtml(item)}</li>`).join("")}
    </ul>
  `;
}

function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (ch) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[ch]);
}

async function validateRecipient(includeMx = false) {
  const recipient = $("recipient").value.trim();
  if (!recipient) {
    showStatus(false, "Enter a recipient email address first.");
    clearOutput();
    return null;
  }

  const response = await fetch("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value: recipient, kind: "email", mx: includeMx, lang: "en" }),
  });
  return response.json();
}

function collectPayload() {
  return {
    recipient: $("recipient").value.trim(),
    sender_name: $("sender-name").value.trim(),
    subject: $("subject").value.trim(),
    body: $("body").value,
    lang: "en",
  };
}

async function validateCompose() {
  const response = await fetch("/api/compose/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(collectPayload()),
  });

  return { response, data: await response.json() };
}

function renderComposeValidation(data) {
  clearOutput();

  const recipient = data.recipient || {};
  const linkMarkup = Array.isArray(data.links) && data.links.length
    ? data.links.map((item) => `<code>${escapeHtml(item)}</code>`).join("<br>")
    : "";

  showStatus(!!data.ok, data.ok ? "Message is ready to send." : "Related issues found. Fix them before sending.");
  addItem("Recipient", recipient.input ? `<code>${escapeHtml(recipient.input)}</code>` : "");
  addItem("Normalized", recipient.normalized ? `<code>${escapeHtml(recipient.normalized)}</code>` : "");
  addItem("Local part", recipient.local ? `<code>${escapeHtml(recipient.local)}</code>` : "");
  addItem("Domain Unicode", recipient.domain_unicode ? `<code>${escapeHtml(recipient.domain_unicode)}</code>` : "");
  addItem("Domain ASCII", recipient.domain_ascii ? `<code>${escapeHtml(recipient.domain_ascii)}</code>` : "");
  addItem("SMTPUTF8 required", "smtputf8_required" in recipient ? (recipient.smtputf8_required ? "yes" : "no") : "");
  addItem("Links checked", Array.isArray(data.links) ? String(data.links.length) : "0");
  addItem("Link targets", linkMarkup);

  messages.innerHTML = [
    renderMessages(data.errors, "error"),
    renderMessages(data.warnings, "warn"),
  ].join("");
}

async function validateOnly() {
  setBusy(true);
  try {
    const { data } = await validateCompose();
    renderComposeValidation(data);
  } catch (error) {
    showStatus(false, `Validation failed: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

async function sendEmail(event) {
  event.preventDefault();
  setBusy(true);
  try {
    const { data: validation } = await validateCompose();
    renderComposeValidation(validation);
    if (!validation.ok) {
      return;
    }

    const response = await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(collectPayload()),
    });
    const data = await response.json();

    if (!response.ok || !data.ok) {
      showStatus(false, "Related issues found. Email was not sent.");
      messages.innerHTML = [
        renderMessages(data.errors || data.details || [data.error || "Unknown error"], "error"),
        renderMessages(data.warnings, "warn"),
      ].join("");
      return;
    }

    showStatus(true, `Email sent to ${data.recipient}.`);
    clearOutput();
    addItem("Recipient", `<code>${escapeHtml(data.recipient)}</code>`);
    addItem("Links checked", String(data.links_checked || 0));
    addItem("SMTPUTF8 used", data.smtputf8_used ? "yes" : "no");
    addItem("SMTPUTF8 advertised", data.smtputf8_advertised ? "yes" : "no");
    addItem("Message ID", data.message_id ? `<code>${escapeHtml(data.message_id)}</code>` : "");
  } catch (error) {
    showStatus(false, `Related issues found. ${error.message}`);
  } finally {
    setBusy(false);
  }
}

validateBtn.addEventListener("click", validateOnly);
form.addEventListener("submit", sendEmail);
