const $ = (id) => document.getElementById(id);

const statusCard = $("status-card");
const statusLine = $("status-line");
const summary = $("summary");
const messages = $("messages");
const validateBtn = $("validate-btn");
const sendBtn = $("send-btn");
const form = $("mail-form");

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
    messages.innerHTML = "";
    summary.innerHTML = "";
    return null;
  }

  const response = await fetch("/api/validate", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ value: recipient, kind: "email", mx: includeMx, lang: "en" }),
  });
  return response.json();
}

function renderValidation(data) {
  summary.innerHTML = "";
  messages.innerHTML = "";

  showStatus(!!data.ok, data.ok ? "Recipient is valid." : "Recipient is invalid.");
  addItem("Input", `<code>${escapeHtml(data.input || "")}</code>`);
  addItem("Normalized", data.normalized ? `<code>${escapeHtml(data.normalized)}</code>` : "");
  addItem("Local part", data.local ? `<code>${escapeHtml(data.local)}</code>` : "");
  addItem("Domain Unicode", data.domain_unicode ? `<code>${escapeHtml(data.domain_unicode)}</code>` : "");
  addItem("Domain ASCII", data.domain_ascii ? `<code>${escapeHtml(data.domain_ascii)}</code>` : "");
  addItem("SMTPUTF8 required", data.smtputf8_required ? "yes" : "no");
  addItem("IDNA used", data.idn_required ? "yes" : "no");
  addItem("Scripts", Array.isArray(data.scripts) ? `<code>${escapeHtml(data.scripts.join(", "))}</code>` : "");

  messages.innerHTML = [
    renderMessages(data.errors, "error"),
    renderMessages(data.warnings, "warn"),
  ].join("");
}

async function validateOnly() {
  setBusy(true);
  try {
    const data = await validateRecipient(true);
    if (data) renderValidation(data);
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
    const validation = await validateRecipient(false);
    if (!validation || !validation.ok) {
      renderValidation(validation || { ok: false, errors: ["Recipient validation failed."] });
      return;
    }

    const payload = {
      recipient: $("recipient").value.trim(),
      sender_name: $("sender-name").value.trim(),
      subject: $("subject").value.trim(),
      body: $("body").value,
    };

    const response = await fetch("/api/send", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    const data = await response.json();

    if (!response.ok || !data.ok) {
      showStatus(false, data.error || "Sending failed.");
      messages.innerHTML = renderMessages(data.details || [data.error || "Unknown error"], "error");
      return;
    }

    showStatus(true, `Email sent to ${data.recipient}.`);
    summary.innerHTML = "";
    addItem("Recipient", `<code>${escapeHtml(data.recipient)}</code>`);
    addItem("Sender", `<code>${escapeHtml(data.sender)}</code>`);
    addItem("SMTPUTF8 required", data.smtp_utf8_required ? "yes" : "no");
    messages.innerHTML = "";
  } catch (error) {
    showStatus(false, `Sending failed: ${error.message}`);
  } finally {
    setBusy(false);
  }
}

validateBtn.addEventListener("click", validateOnly);
form.addEventListener("submit", sendEmail);
