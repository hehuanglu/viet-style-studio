const $ = (selector) => document.querySelector(selector);
const terminal = new Set(["complete", "cards_only", "needs_evidence", "needs_resolution", "failed", "cancelled"]);
const statusLabels = {
  prompt_writing: "Gemini đang viết prompt tạo ảnh qua API",
  brief_checking: "Gemini đang kiểm tra các thông tin đã nhận diện",
  normalizing: "Đang hiểu yêu cầu", retrieving: "Đang chọn căn cứ",
  rendering: "Đang tạo ảnh qua API", image_repairing: "Đang sửa ảnh qua API", image_checking: "Đang audit ảnh",
  awaiting_image: "Đang chờ bạn gửi ảnh tạo", awaiting_image_repair: "Đang chờ bạn gửi ảnh sửa",
  awaiting_manual_audit: "Chờ kết quả kiểm tra", awaiting_audit_choice: "Chọn cách kiểm tra ảnh",
  concept_repairing: "Đang sửa phương án", repair_auditing: "Đang kiểm tra phương án sửa",
  queued: "Đang xếp hàng", understanding: "Đang hiểu yêu cầu", planning: "Đang tạo phương án",
  auditing: "Đang kiểm tra phương án", cards_ready: "Đã có gợi ý", awaiting_user: "Cần bạn bổ sung thông tin",
  complete: "Hoàn tất", cards_only: "Đã hoàn tất gợi ý bằng chữ", needs_evidence: "Chưa đủ nguồn để tiếp tục",
  needs_resolution: "Cần làm rõ yêu cầu", failed: "Không thể hoàn thành", cancelled: "Đã hủy",
};
const waiting = new Set(["awaiting_user", "awaiting_image", "awaiting_image_repair", "awaiting_manual_audit", "awaiting_audit_choice"]);
let textApiReady = false;
let simulationEnabled = false;
function updateSubmitState() {
  const ready = textApiReady || (simulationEnabled && $("#simulation-mode").checked);
  $("#submit-request").disabled = !ready || (!!activeJob && !terminal.has(activeJob.status));
}
$("#simulation-mode").addEventListener("change", updateSubmitState);
let activeId = new URLSearchParams(location.search).get("request") || localStorage.getItem("arena-active-request");
if (activeId) localStorage.setItem("arena-active-request", activeId);
let imagesEnabled = false;
let renderedManualKey = null;
let manualPasteController = new AbortController();
const uploadDrafts = new Map();
let previewUrl = null;
let activeJob = null;
let pollTimer = null;
let imageEditor = null;
function editor() { return imageEditor ||= new ArenaImageEditor(); }
function stopPolling() {
  clearInterval(pollTimer);
  pollTimer = null;
}
function syncPolling() {
  if (!activeId || (activeJob && (terminal.has(activeJob.status) || waiting.has(activeJob.status)))) stopPolling();
  else if (!pollTimer) pollTimer = setInterval(refreshJob, 1100);
}
function isOlderJob(incoming, current) {
  if (!current || incoming.request_id !== current.request_id) return false;
  if (incoming.revision !== current.revision) return incoming.revision < current.revision;
  const sequence = (job) => job.events?.at(-1)?.sequence || 0;
  return sequence(incoming) < sequence(current);
}
let sessionId = localStorage.getItem("arena-session-id");
if (!sessionId) {
  sessionId = crypto.randomUUID();
  localStorage.setItem("arena-session-id", sessionId);
}

function escapeHtml(value) {
  return String(value ?? "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[char]);
}

async function api(path, options = {}) {
  const response = await fetch(path, {
    ...options,
    headers: { "Content-Type": "application/json", ...(options.headers || {}) },
  });
  const contentType = response.headers.get("content-type") || "";
  const body = contentType.includes("application/json") ? await response.json() : null;
  if (!response.ok) throw new Error(body?.error?.message || `Lỗi HTTP ${response.status}`);
  return body;
}

function setKeyMessage(message, error = false) {
  const element = $("#key-message");
  element.textContent = message;
  element.classList.toggle("error", error);
}

async function loadHealth() {
  try {
    const health = await api("/health");
    $(".status-dot").classList.add("online");
    $("#server-label").textContent = "Backend đang hoạt động";
    textApiReady = health.text_api_ready ?? (health.provider === "gemini" && health.api_key_configured === true);
    simulationEnabled = health.simulation_enabled === true;
    $("#simulation-option").hidden = !simulationEnabled;
    $("#provider-badge").textContent = textApiReady ? "Gemini · đã cấu hình key" : health.provider === "gemini" ? "Gemini · cần API key" : "Mock · chỉ mô phỏng";
    $("#provider-badge").className = `badge ${textApiReady ? "connected" : "mock"}`;
    $("#text-api-note").textContent = textApiReady ? "Hiểu yêu cầu, tạo và audit phương án dùng API Gemini. Google xác thực key ở lần gọi đầu; lỗi API sẽ được báo, không chuyển sang mock." : "Chưa có API văn bản hoạt động. Kết nối Gemini API key để phân tích yêu cầu thật; lựa chọn ảnh thủ công không thay bước này.";
    updateSubmitState();
    imagesEnabled = health.images_enabled;
    updateImageMode();
    $("#pack-label").textContent = `Phạm vi hiện tại: ${health.pack_id} · v${health.pack_version}. ${health.cultural_caption_ready ? "Có dữ liệu nguồn đã xác minh trong pack." : "Chưa có nguồn văn hóa đã xác minh trong pack."}`;
  } catch (error) {
    textApiReady = false;
    simulationEnabled = false;
    updateSubmitState();
    $("#server-label").textContent = "Không kết nối được backend";
    $("#provider-badge").textContent = "Backend ngoại tuyến";
    $("#provider-badge").className = "badge";
    $("#pack-label").textContent = "Khởi động backend để xem phạm vi dữ liệu.";
    setKeyMessage(error.message, true);
  }
}

$("#key-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const keyInput = $("#api-key");
  const button = $("#key-submit");
  const key = keyInput.value.trim();
  if (!key) return setKeyMessage("Vui lòng nhập Gemini API key.", true);
  button.disabled = true;
  setKeyMessage("Đang cấu hình key trong bộ nhớ backend…");
  try {
    await api("/session/api-key", { method: "POST", body: JSON.stringify({ api_key: key }) });
    keyInput.value = "";
    setKeyMessage("Đã cập nhật key. Các request đang chờ vẫn giữ nguyên tiến độ. Key chỉ tồn tại trong tiến trình backend; Gemini xác thực ở lần gọi API tiếp theo.");
    await loadHealth();
  } catch (error) {
    setKeyMessage(error.message, true);
  } finally {
    button.disabled = false;
  }
});

document.querySelectorAll("[data-example]").forEach((button) => {
  button.addEventListener("click", () => {
    $("#request-input").value = button.dataset.example;
    $("#request-input").focus();
  });
});

$("#request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  const input = $("#request-input").value.trim();
  if (!input) return $("#request-input").focus();
  if (!textApiReady && !(simulationEnabled && $("#simulation-mode").checked)) return setKeyMessage("Kết nối Gemini API key để hệ thống nhận diện yêu cầu.", true);
  if (activeJob && !terminal.has(activeJob.status)) return;
  $("#submit-request").disabled = true;
  activeJob = null;
  activeId = null;
  stopPolling();
  $("#result-section").hidden = false;
  $("#result-title").textContent = "Đang gửi yêu cầu…";
  $("#result-summary").textContent = "";
  $("#request-error").hidden = true;
  $("#cards").replaceChildren();
  $("#warnings").replaceChildren();
  $("#question-card").hidden = true;
  $("#image-result").replaceChildren();
  $("#details").hidden = true;
  $("#report").hidden = true;
  $("#manual-step").hidden = true;
  $("#mock-request-notice").hidden = true;
  renderedManualKey = null;
  uploadDrafts.clear();
  $("#progress").classList.remove("done");
  window.scrollTo({ top: $("#result-section").offsetTop - 20, behavior: "smooth" });
  try {
    const created = await api("/requests", { method: "POST", body: JSON.stringify({ input, session_id: sessionId, render_image: $("#render-image").checked, image_mode: $("#image-mode").value, audit_mode: $("#audit-mode").value }) });
    activeId = created.request_id;
    localStorage.setItem("arena-active-request", activeId);
    history.replaceState(null, "", `?request=${encodeURIComponent(activeId)}`);
    $("#cancel-request").hidden = false;
    syncPolling();
    await refreshJob();
  } catch (error) {
    showRequestError(error.message);
    $("#result-title").textContent = "Không gửi được yêu cầu";
  } finally {
    updateSubmitState();
  }
});

$("#retry-real-request").addEventListener("click", async () => {
  if (!activeJob || activeJob.provider !== "mock") return;
  const button = $("#retry-real-request");
  button.disabled = true;
  try {
    const original = activeJob.turns.map((turn) => turn.text).join("\n\n");
    if (!terminal.has(activeJob.status)) await api(`/requests/${activeId}/cancel`, { method: "POST", body: "{}" });
    $("#request-input").value = original;
    $("#simulation-mode").checked = false;
    await refreshJob();
    setKeyMessage("Đã giữ yêu cầu gốc trong ô nhập. Kết nối API key, rồi bấm Tạo gợi ý để Gemini phân tích lại từ đầu.");
    $("#api-key").focus();
    updateSubmitState();
  } catch (error) {
    showRequestError(error.message);
  } finally {
    button.disabled = false;
  }
});

$("#cancel-request").addEventListener("click", async () => {
  if (!activeId) return;
  try {
    await api(`/requests/${activeId}/cancel`, { method: "POST", body: "{}" });
    await refreshJob();
  } catch (error) {
    showRequestError(error.message);
  }
});

function showRequestError(message) {
  const box = $("#request-error");
  box.textContent = message;
  box.hidden = false;
}

async function copyPrompt(text, textarea = null) {
  const temporary = !textarea;
  const previousFocus = document.activeElement;
  if (temporary) {
    textarea = document.createElement("textarea");
    textarea.value = text;
    textarea.style.cssText = "position:fixed;left:-10000px;top:0";
    document.body.appendChild(textarea);
  }
  textarea.focus(); textarea.select();
  try {
    if (!document.execCommand("copy")) await navigator.clipboard.writeText(text);
  } finally {
    if (temporary) {
      textarea.remove();
      previousFocus?.focus();
    }
  }
}

function candidatePrompt(job, card, index) {
  return card.image_prompt
    || job.image_prompts?.find(entry => entry.candidate_id === card.candidate_id)?.prompt
    || (index === 0 ? job.compiled_image_prompt : "")
    || "";
}

function renderCards(job) {
  const cards = job.cards || [];
  $("#cards").innerHTML = cards.map((card, index) => {
    const design = card.design || {};
    const prompt = candidatePrompt(job, card, index);
    const tags = [...(design.palette || []), ...(design.accessories || [])];
    const sources = (card.source_caption || []).map((source) => {
      const title = `${source.text || ""}${source.source_id ? ` · ${source.source_id}` : ""}`;
      return source.source_url
        ? `<a href="${escapeHtml(source.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(title)}</a>`
        : escapeHtml(title);
    });
    return `<article class="idea-card">
      <div class="idea-top"><span class="idea-index">PHƯƠNG ÁN 0${index + 1}</span><span class="score">${escapeHtml(card.score ?? "Gợi ý")}${card.score !== undefined ? " điểm" : ""}</span></div>
      <h3>${escapeHtml(card.title || "Gợi ý phối đồ")}</h3>
      ${index === 0 ? '<p class="chosen-label">Gợi ý nổi bật</p>' : ""}
      <p>${escapeHtml(card.target_need || "")}</p>
      <p class="design-detail">${escapeHtml(design.subject_description || "")} ${escapeHtml(design.scene || "")}</p>
      ${tags.length ? `<div class="tag-list">${tags.map((tag) => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      ${(card.caveats || []).map((item) => `<p>${escapeHtml(item)}</p>`).join("")}
      <div class="option-prompt">
        ${job.status === "awaiting_image" && !(job.artifacts || []).length ? `<button type="button" class="button button-accent small-button" data-select-option="${index}" ${job.image_target_ids?.includes(card.candidate_id) ? "disabled" : ""}>${job.image_target_ids?.includes(card.candidate_id) ? "Đã chọn tạo ảnh" : "Chọn phương án này"}</button>` : ""}
        <button type="button" class="button button-dark" data-copy-option="${index}" aria-label="Nhận prompt phương án ${index + 1}" aria-controls="option-prompt-${index}" aria-expanded="false" ${prompt ? "" : "disabled"}>Nhận prompt</button>
        <div id="option-prompt-${index}" hidden><label for="option-prompt-text-${index}">Prompt tạo ảnh · phương án ${index + 1}</label><textarea id="option-prompt-text-${index}" rows="8" readonly>${escapeHtml(prompt)}</textarea></div>
        <span role="status">${prompt ? "" : "Đang chuẩn bị prompt…"}</span>
      </div>
      ${sources.length ? `<p class="source-line">Nguồn: ${sources.join(" · ")}</p>` : ""}
    </article>`;
  }).join("");
  $("#cards").querySelectorAll("[data-select-option]").forEach((button) => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const candidate = cards[Number(button.dataset.selectOption)];
      await api(`/requests/${job.request_id}/image-candidate`, {method: "POST", body: JSON.stringify({
        revision: job.revision, step_id: job.pending_manual.step_id, candidate_id: candidate.candidate_id,
      })});
      renderedManualKey = null;
      uploadDrafts.clear();
      await refreshJob();
    } catch (error) { showRequestError(error.message); button.disabled = false; }
  }));
  $("#cards").querySelectorAll("[data-copy-option]").forEach((button) => button.addEventListener("click", async () => {
    const panel = button.parentElement.querySelector("div");
    panel.hidden = !panel.hidden;
    button.setAttribute("aria-expanded", String(!panel.hidden));
    button.textContent = panel.hidden ? "Nhận prompt" : "Ẩn prompt";
    if (panel.hidden) return;
    const textarea = panel.querySelector("textarea");
    const message = button.parentElement.querySelector('[role="status"]');
    try {
      await copyPrompt(candidatePrompt(job, cards[Number(button.dataset.copyOption)], Number(button.dataset.copyOption)), textarea);
      message.textContent = "Đã copy · dán vào Gemini";
    } catch (_) { message.textContent = "Dùng Ctrl+C / ⌘C để copy phần đã chọn"; }
  }));
}

function renderQuestion(job) {
  const questions = job.questions || [];
  const box = $("#question-card");
  if (job.status !== "awaiting_user" || !questions.length) { box.hidden = true; box.replaceChildren(); return; }
  const question = questions[0];
  const options = (question.options || []).map((option) => `<button type="button" class="button button-quiet small-button" data-answer="${escapeHtml(option)}">${escapeHtml(option)}</button>`).join("");
  box.innerHTML = `<h3>Cần bạn bổ sung một chút</h3><p>${escapeHtml(question.text)}</p>
    <form id="answer-form" class="answer-row"><input class="answer-input" name="answer" placeholder="Nhập câu trả lời…" maxlength="6000" /><button class="button button-dark small-button" type="submit">Gửi</button></form>
    <div class="question-actions">${options}<button type="button" class="button button-quiet small-button" data-skip>Để ứng dụng gợi ý</button></div>`;
  box.hidden = false;
  box.querySelector("#answer-form").addEventListener("submit", (event) => {
    event.preventDefault();
    const answer = new FormData(event.currentTarget).get("answer").trim();
    if (answer) sendAnswer(job, { answer });
  });
  box.querySelectorAll("[data-answer]").forEach((button) => button.addEventListener("click", () => sendAnswer(job, { answer: button.dataset.answer })));
  box.querySelector("[data-skip]").addEventListener("click", () => sendAnswer(job, { skip: true }));
}

async function sendAnswer(job, answer) {
  stopPolling();
  $("#question-card").querySelectorAll("button,input").forEach((element) => { element.disabled = true; });
  try {
    await api(`/requests/${job.request_id}/answers`, { method: "POST", body: JSON.stringify({ revision: job.revision, ...answer }) });
    await refreshJob();
    if (activeId && !terminal.has(activeJob?.status)) syncPolling();
  } catch (error) {
    showRequestError(error.message);
    $("#question-card").querySelectorAll("button,input").forEach((element) => { element.disabled = false; });
  }
}

function renderWarnings(job) {
  const messages = [...(job.warnings || [])];
  if (job.status === "needs_evidence") messages.unshift("Yêu cầu cần nguồn phù hợp hơn. Bạn có thể gửi một yêu cầu theo hướng lấy cảm hứng hiện đại.");
  if (job.status === "cards_only" && job.render_image && !job.artifacts?.length) messages.unshift("Không có ảnh đã kiểm tra; các gợi ý bằng chữ vẫn được giữ lại.");
  $("#warnings").innerHTML = messages.map((message) => `<div class="warning">${escapeHtml(message)}</div>`).join("");
}

function renderImage(job) {
  const labels = {passed: "Ảnh qua audit", mock_flow_checked: "Chỉ kiểm tra luồng bằng mock; chưa audit thị giác thật", failed_or_uncertain: "Chưa đạt / chưa xác định", unverified: "Chưa có audit hợp lệ"};
  const currentIds = job.output_artifact_ids || (job.artifacts || []).filter(a => !(job.artifacts || []).some(child => child.parent_artifact_id === a.artifact_id)).map(a => a.artifact_id);
  const editable = waiting.has(job.status) || ["complete", "cards_only"].includes(job.status);
  const imageMarkup = (artifact) => `<div class="image-result">
    <button type="button" class="image-open" data-edit-image="${escapeHtml(artifact.artifact_id)}" ${editable ? "" : "disabled"} aria-label="Mở ảnh để phác thảo"><img src="${escapeHtml(artifact.url)}" alt="${artifact.parent_artifact_id ? "Ảnh sửa" : "Ảnh tạo"}" /></button>
    <p>${escapeHtml((job.cards || []).find(c => c.candidate_id === artifact.candidate_id)?.title || artifact.candidate_id || "")}<br /><strong>${artifact.parent_artifact_id ? "Ảnh sửa từ ảnh gốc của request này" : "Ảnh tạo ban đầu"}</strong><br />
    ${escapeHtml(artifact.output_origin === "gemini" ? "API Gemini" : artifact.output_origin === "mock" ? "Ảnh mock" : artifact.output_origin)}<br />
    ${escapeHtml(labels[artifact.check_status] || "Chưa kiểm tra")}<br />
    ${(job.selected_artifact_ids || [job.selected_artifact_id]).includes(artifact.artifact_id) ? "Ảnh kết quả đã kiểm tra của phương án này.<br />" : ""}
    <a href="${escapeHtml(artifact.url)}" download>Tải ảnh</a><br /><button type="button" class="button button-accent small-button" data-edit-image="${escapeHtml(artifact.artifact_id)}" ${editable ? "" : "disabled"}>Mở ảnh / Phác thảo chỉnh sửa</button></p></div>`;
  const current = (job.artifacts || []).filter(a => currentIds.includes(a.artifact_id));
  const history = (job.artifacts || []).filter(a => !currentIds.includes(a.artifact_id));
  $("#image-result").innerHTML = current.map(imageMarkup).join("") + (history.length ? `<details class="details image-history"><summary>Lịch sử ảnh (${history.length})</summary>${history.map(a => `<p><a href="${escapeHtml(a.url)}" download>${escapeHtml(a.filename || "Ảnh trước chỉnh sửa")}</a></p>`).join("")}</details>` : "");
  $("#image-result").querySelectorAll("[data-edit-image]").forEach(button => button.addEventListener("click", async () => {
    button.disabled = true;
    try {
      const artifact = job.artifacts.find(a => a.artifact_id === button.dataset.editImage);
      const response = await fetch(artifact.url);
      if (!response.ok) throw new Error("Không tải được ảnh gốc.");
      const blob = await response.blob();
      const source = await readArenaImageFile(new File([blob], artifact.filename || "Ảnh gốc", {type: artifact.mime_type}));
      await editor().open({...source, job, candidateId: artifact.candidate_id, onComplete: async (result, packet) => {
        if (!activeJob || activeJob.request_id !== job.request_id) throw new Error("Yêu cầu hiện tại đã thay đổi. Mở lại đúng ảnh để sửa.");
        const {original, ...context} = packet;
        await api(`/requests/${job.request_id}/image-edits`, {method: "POST", body: JSON.stringify({revision: activeJob.revision, parent_artifact_id: artifact.artifact_id, image: result.image, filename: result.filename, ...context})});
        renderedManualKey = null; await refreshJob(); syncPolling();
      }});
    } catch (error) { showRequestError(error.message); }
    finally { button.disabled = false; }
  }));
}

function updateImageMode() {
  const manual = $("#image-mode").value === "gemini_manual";
  $("#render-image").disabled = (!manual && !imagesEnabled) || (!!activeJob && !terminal.has(activeJob.status));
  $("#image-note").textContent = manual ? "Copy prompt → gửi ảnh lại" : imagesEnabled ? "API ảnh đã bật" : "API ảnh cần --images";
  if (!manual && !imagesEnabled) $("#render-image").checked = false;
}
$("#image-mode").addEventListener("change", updateImageMode);

async function resumeStep(job, endpoint, data = {}) {
  const box = $("#manual-step");
  box.querySelectorAll("button,input,textarea").forEach((element) => { element.disabled = true; });
  $("#request-error").hidden = true;
  try {
    await api(`/requests/${job.request_id}/${endpoint}`, {method: "POST", body: JSON.stringify({revision: job.revision, step_id: job.pending_manual.step_id, ...data})});
    renderedManualKey = null;
    stopPolling();
    await refreshJob();
    if (activeJob && !terminal.has(activeJob.status) && !waiting.has(activeJob.status)) syncPolling();
  } catch (error) {
    showRequestError(error.message);
    box.querySelectorAll("button,input,textarea").forEach((element) => { element.disabled = false; });
  }
}

function renderManual(job) {
  const pending = job.pending_manual;
  const box = $("#manual-step");
  if (!pending || !waiting.has(job.status)) {
    box.hidden = true;
    manualPasteController.abort();
    renderedManualKey = null;
    if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
    box.replaceChildren();
    return;
  }
  const key = `${job.request_id}:${job.revision}:${pending.step_id}`;
  if (renderedManualKey === key) return;
  renderedManualKey = key;
  manualPasteController.abort();
  manualPasteController = new AbortController();
  if (previewUrl) { URL.revokeObjectURL(previewUrl); previewUrl = null; }
  box.hidden = false;
  const cards = job.cards || [];
  const candidateId = pending.candidate_id || job.image_workflow?.candidate_id || cards[0]?.candidate_id;
  const candidateIndex = Math.max(0, cards.findIndex(card => card.candidate_id === candidateId));
  const card = cards[candidateIndex];
  const heading = (title) => `<div class="manual-heading"><div><h3>${title}</h3><p class="manual-option">${escapeHtml(card?.title || `Phương án ${candidateIndex + 1}`)}</p></div><span class="manual-count">${job.image_target_ids ? "PHƯƠNG ÁN " : ""}${String(candidateIndex + 1).padStart(2, "0")}${job.image_target_ids ? "" : ` / ${String(cards.length || 1).padStart(2, "0")}`}</span></div>`;
  if (pending.kind === "audit_choice") {
    box.innerHTML = `${heading("Kiểm tra ảnh")}<p>Kiểm tra tự động chưa khả dụng. Bạn có thể tiếp tục chỉnh sửa trực tiếp trên ảnh.</p><button class="button button-accent" id="choose-background-audit">Tiếp tục chỉnh sửa trực tiếp</button><details class="manual-help"><summary>Audit JSON nâng cao</summary><button class="button button-dark" id="choose-manual-audit">Kiểm tra trên Gemini</button><p>${escapeHtml(job.audit_api_error?.message || "Hãy kiểm tra ảnh trên Gemini rồi gửi kết quả.")}</p></details>`;
    box.querySelector("#choose-background-audit").addEventListener("click", () => resumeStep(job, "background-audit-mode"));
    box.querySelector("#choose-manual-audit").addEventListener("click", () => resumeStep(job, "manual-audit-mode"));
    return;
  }
  const audit = pending.kind === "audit";
  const repair = pending.kind === "repair";
  const instructions = audit
    ? "Copy hướng dẫn, mở Gemini và đính kèm ảnh cần kiểm tra. Dán kết quả JSON Gemini trả về vào đây. Với ảnh sửa, đính kèm ảnh sửa trước, ảnh gốc sau."
    : repair
      ? "Copy yêu cầu sửa và tiếp tục cuộc trò chuyện Gemini đã tạo ảnh. Đính kèm ảnh gốc, tải ảnh sửa về rồi gửi tại đây."
      : "Chọn phương án bạn muốn, nhận prompt ở thẻ đó rồi dán vào Gemini. Gửi ảnh về đúng phương án đang hiển thị ở đây. Nếu không chọn riêng, ứng dụng sẽ lần lượt nhận ảnh cho cả ba phương án.";
  const relevant = (job.artifacts || []).filter((a) => a.artifact_id === pending.artifact_id || a.artifact_id === pending.parent_artifact_id);
  relevant.sort((a, b) => Number(b.artifact_id === pending.artifact_id) - Number(a.artifact_id === pending.artifact_id));
  box.innerHTML = `${heading(audit ? "Kiểm tra ảnh" : repair ? "Sửa ảnh" : "Tạo ảnh với Gemini")}
    ${!audit && !repair ? '<div class="manual-path" aria-label="Các bước tạo ảnh"><span>01 · Nhận prompt</span><span>02 · Tạo trên Gemini</span><span>03 · Gửi ảnh</span></div>' : ""}
    <div class="manual-actions">
      ${audit || repair ? `<button type="button" class="button button-dark" id="copy-prompt">${audit ? "Copy hướng dẫn" : "Copy yêu cầu sửa"}</button>` : ""}
      <a class="button button-quiet gemini-button" href="https://gemini.google.com/" target="_blank" rel="noreferrer">Mở Gemini ↗</a>
      <span id="copy-message" role="status"></span>
    </div>
    ${relevant.length ? `<div class="manual-references">${relevant.map((a) => `<div class="audit-reference"><img src="${escapeHtml(a.url)}" alt="${a.artifact_id === pending.artifact_id ? "Ảnh cần kiểm tra" : "Ảnh gốc"}" /><a class="button button-quiet small-button" href="${escapeHtml(a.url)}" download>${a.artifact_id === pending.artifact_id ? "Tải ảnh cần kiểm tra" : "Tải ảnh gốc"}</a></div>`).join("")}</div>` : ""}
    ${audit ? `<form id="audit-form" class="manual-audit-form"><label for="audit-result">Kết quả từ Gemini</label><textarea id="audit-result" rows="4" maxlength="80000" required placeholder="Dán kết quả JSON…"></textarea><div class="manual-actions"><button type="button" class="button button-quiet" id="paste-audit">Dán kết quả</button><button class="button button-accent" type="submit">Gửi kết quả</button><span id="paste-message" role="status"></span></div></form>`
      : `<div class="manual-upload" tabindex="0" aria-label="Dán ảnh Gemini"><div class="upload-control"><button type="button" class="button button-accent" id="paste-image">Dán ảnh</button><label for="manual-image" class="button button-quiet upload-button">Chọn ảnh</label><input id="manual-image" class="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" /><span id="upload-name">Chưa chọn ảnh</span></div><span class="upload-hint">Ctrl+V / ⌘V hoặc chọn ảnh · PNG, JPG, WebP · tối đa 10 MB</span><div id="upload-preview"></div><div class="manual-actions"><button id="edit-upload" type="button" class="button button-dark" hidden>Mở ảnh / Phác thảo chỉnh sửa</button><button id="confirm-image" type="button" class="button button-accent" disabled>Gửi ảnh</button></div></div>`}
    ${job.audit_mode !== "background" ? '<button type="button" class="button button-quiet" id="switch-direct-edit">Dùng quy trình chỉnh sửa trực tiếp</button>' : ""}
    <details class="manual-help"><summary>Hướng dẫn</summary><p>${instructions}</p></details>`;
  box.querySelector("#copy-prompt")?.addEventListener("click", async () => {
    try {
      await copyPrompt(pending.prompt);
      box.querySelector("#copy-message").textContent = "Đã copy prompt";
    } catch (_) {
      box.querySelector("#copy-message").textContent = "Trình duyệt chưa cho phép copy. Hãy cấp quyền clipboard rồi thử lại.";
    }
  });
  box.querySelector("#switch-direct-edit")?.addEventListener("click", () => resumeStep(job, "background-audit-mode"));
  if (audit) {
    box.querySelector("#paste-audit").addEventListener("click", async () => {
      try {
        const result = await navigator.clipboard.readText();
        if (renderedManualKey !== key) return;
        box.querySelector("#audit-result").value = result;
        box.querySelector("#paste-message").textContent = "Đã dán";
      } catch (_) {
        if (renderedManualKey !== key) return;
        box.querySelector("#audit-result").focus();
        box.querySelector("#paste-message").textContent = "Dán bằng Ctrl+V / ⌘V";
      }
    });
    box.querySelector("#audit-form").addEventListener("submit", (event) => { event.preventDefault(); resumeStep(job, "manual-audits", {result: box.querySelector("#audit-result").value}); });
    return;
  }
  let selectedImage = null;
  let selectedName = null;
  let selectedEdit = null;
  let selectionVersion = 0;
  const confirm = box.querySelector("#confirm-image");
  const editButton = box.querySelector("#edit-upload");
  const draftKey = `${job.request_id}:${pending.step_id}`;
  function showPreview(result, context = null) {
    uploadDrafts.set(draftKey, {result, context});
    selectedImage = result.image; selectedName = result.filename; selectedEdit = context;
    box.querySelector("#upload-name").textContent = result.filename;
    const img = new Image(); img.src = `data:${result.image.mime_type};base64,${result.image.data}`;
    img.alt = "Mở ảnh để phác thảo chỉnh sửa"; img.tabIndex = 0; img.className = "editable-preview";
    img.addEventListener("click", openSelected);
    img.addEventListener("keydown", event => { if (["Enter", " "].includes(event.key)) { event.preventDefault(); openSelected(); } });
    box.querySelector("#upload-preview").replaceChildren(img);
    confirm.disabled = false; editButton.hidden = false;
  }
  async function selectFile(file) {
    if (!file) return;
    const version = ++selectionVersion;
    selectedImage = null; selectedEdit = null; confirm.disabled = true; editButton.hidden = true;
    uploadDrafts.delete(draftKey);
    box.querySelector("#upload-preview").replaceChildren();
    $("#request-error").hidden = true;
    try {
      const result = await readArenaImageFile(file);
      if (version !== selectionVersion || renderedManualKey !== key) return;
      showPreview(result);
    } catch (error) { if (version === selectionVersion && renderedManualKey === key) showRequestError(error.message); }
  }
  async function openSelected() {
    if (!selectedImage) return;
    try {
      await editor().open({image: selectedImage, filename: selectedName, job, candidateId, onComplete: async (result, packet) => {
        if (renderedManualKey !== key) throw new Error("Bước nhận ảnh đã thay đổi. Hãy mở lại bước hiện tại.");
        ++selectionVersion; showPreview(result, packet);
      }});
    } catch (error) { showRequestError(error.message); }
  }
  editButton.addEventListener("click", openSelected);
  box.querySelector("#manual-image").addEventListener("change", event => selectFile(event.target.files[0]));
  box.querySelector("#paste-image").addEventListener("click", async () => {
    try { const file = await arenaImageFromClipboard(); if (renderedManualKey === key) await selectFile(file); }
    catch (error) { showRequestError(error.message); box.querySelector(".manual-upload").focus(); }
  });
  document.addEventListener("paste", event => {
    const file = [...(event.clipboardData?.items || [])].find(item => item.kind === "file" && item.type.startsWith("image/"))?.getAsFile();
    if (file && !imageEditor?.dialog.open && renderedManualKey === key) { event.preventDefault(); selectFile(file); }
  }, {signal: manualPasteController.signal});
  confirm.addEventListener("click", async () => {
    if (!selectedImage) return;
    await resumeStep(job, "images", {image: selectedImage, filename: selectedName, ...(selectedEdit ? {edit_context: selectedEdit} : {})});
    if (activeJob?.pending_manual?.step_id !== pending.step_id) uploadDrafts.delete(draftKey);
  });
  const draft = uploadDrafts.get(draftKey);
  if (draft) showPreview(draft.result, draft.context);
}

function renderReport(job) {
  const report = job.user_report;
  const box = $("#report");
  if (!report) { box.hidden = true; return; }
  const list = (items) => items.length ? `<ul>${items.map((item) => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : '<p class="muted">Chưa có.</p>';
  const totals = report.api.totals;
  box.hidden = false;
  box.innerHTML = `<details><summary>Thông tin xử lý và kiểm tra ảnh</summary><h3>Báo cáo yêu cầu</h3><p class="report-outcome">${escapeHtml(report.final)}</p>
    <h4>Input đã nhận</h4><p>${escapeHtml(report.inputs.initial)}</p>${list(report.inputs.answers)}
    ${list(report.inputs.images.map((image) => `${image.role}: ${image.name} · ${image.source}`))}
    ${report.inputs.manual_audits.map((text, index) => `<details><summary>Kết quả audit thủ công đã nhận · lượt ${index + 1}</summary><p>${escapeHtml(text)}</p></details>`).join("")}
    <h4>Yêu cầu đã chốt</h4>${list(report.agreed)}<h4>Giả định còn lại</h4>${list(report.assumptions)}
    <h4>Phương án và lựa chọn</h4>${report.candidates.map((candidate) => `<p><strong>${escapeHtml(candidate.title)}</strong> · ${escapeHtml(candidate.description)}<br />${escapeHtml(candidate.reason)}</p>`).join("")}
    <p><strong>${report.selected ? `Chọn: ${escapeHtml(report.selected)}` : "Chưa chọn phương án"}</strong><br />${escapeHtml(report.selection_reason)}</p>
    <details><summary>Xem phần đạt, chưa đạt và chưa xác định của audit phương án</summary>${(report.candidate_audits || []).map((audit) => `<p><strong>${escapeHtml(audit.title)}${audit.is_repair ? " · sau sửa" : ""}</strong></p>${list(audit.findings)}`).join("")}</details>
    <h4>Các bước đã thực hiện theo thứ tự</h4><ol>${report.steps.map((step) => `<li><strong>${escapeHtml(step.purpose)}</strong> · ${escapeHtml(step.via)}${step.detail ? `<br />${escapeHtml(step.detail)}` : ""}</li>`).join("")}</ol>
    <h4>API thật</h4><p>${totals.actual} lượt gọi thực tế: ${totals.success} thành công, ${totals.failed} thất bại / phản hồi không hợp lệ, ${totals.interrupted} bị ngắt chưa có kết quả. ${totals.cache} bước dùng kết quả đã lưu, không gọi lại API.</p>
    ${report.api.calls.length ? list(report.api.calls.map((call) => `${call.purpose} · ${call.provider} / ${call.model}: ${call.calls} lượt API thật · ${call.result}`)) : ""}
    ${totals.mock ? '<p class="muted">Các bước mock chỉ mô phỏng workflow, không tính là API thật.</p>' : ""}
    <h4>Thao tác Gemini thủ công</h4><p>${report.manual.image_prompts} prompt tạo/sửa ảnh đã giao · ${report.manual.images_received} ảnh đã nhận · ${report.manual.audit_prompts} prompt audit đã giao · ${report.manual.audits_received} kết quả audit hợp lệ đã nhận.</p>
    <h4>Audit ảnh và sửa</h4>${report.audits.length ? report.audits.map((audit) => `<p><strong>${escapeHtml(audit.image)}</strong> · ${escapeHtml(audit.via)}<br />${escapeHtml(audit.quality)}</p>${list(audit.findings)}${audit.fixes.length ? `<p>Cần sửa:</p>${list(audit.fixes)}` : ""}`).join("") : '<p>Chưa có kết quả audit ảnh hợp lệ.</p>'}
    ${report.repairs.map((repair) => `<p>Vòng sửa đã yêu cầu:</p>${list(repair.fixes)}<p>${escapeHtml(repair.quality)}</p>`).join("")}
    <h4>Kết quả cuối và giới hạn</h4><p>${escapeHtml(report.final)}</p>${list(report.limits)}</details>`;
  $("#details").hidden = true;
}

async function refreshJob() {
  if (!activeId) return;
  const requestId = activeId;
  try {
    const job = await api(`/requests/${requestId}`);
    if (requestId !== activeId) return;
    if (isOlderJob(job, activeJob)) return;
    if (!activeJob || activeJob.request_id !== job.request_id) {
      $("#image-mode").value = job.image_mode || "api";
      $("#audit-mode").value = job.audit_mode || "api";
      $("#render-image").checked = job.render_image;
      $("#request-input").value = job.turns.map((turn) => turn.text).join("\n\n");
    }
    activeJob = job;
    $("#image-mode").disabled = !terminal.has(job.status);
    $("#audit-mode").disabled = !terminal.has(job.status);
    updateImageMode();
    $("#result-section").hidden = false;
    $("#request-error").hidden = true;
    updateSubmitState();
    $("#mock-request-notice").hidden = job.provider !== "mock";
    $("#result-title").textContent = statusLabels[job.status] || job.status;
    const subjectLabel = {au_phuc: "âu phục", ao_dai: "áo dài", ao_tu_than: "áo tứ thân", ao_ngu_than: "áo ngũ thân", ao_va_chan_vay: "áo phối chân váy", vay_lien: "váy liền thân"}[job.brief?.subject?.value] || job.brief?.subject?.value;
    $("#result-summary").textContent = subjectLabel ? `Đối tượng: ${subjectLabel}${job.brief.mode ? ` · ${job.brief.mode === "historical" ? "theo hướng lịch sử" : "lấy cảm hứng"}` : ""}` : "";
    $("#progress").classList.toggle("done", terminal.has(job.status));
    $("#cancel-request").hidden = terminal.has(job.status);
    renderQuestion(job);
    renderCards(job);
    renderWarnings(job);
    renderImage(job);
    renderManual(job);
    const action = $("#next-action");
    action.hidden = job.status !== "awaiting_manual_audit";
    if (!action.hidden) action.innerHTML = '<strong>Ảnh đã nhận</strong><a class="button button-quiet small-button" href="#manual-step">Kiểm tra ảnh ↓</a>';
    renderReport(job);
    if (job.error) showRequestError(`${job.error.message}${job.error.code ? ` (${job.error.code})` : ""}`);
    syncPolling();
  } catch (error) {
    if (requestId !== activeId) return;
    stopPolling();
    showRequestError(error.message);
  }
}

loadHealth();
if (activeId) {
  $("#submit-request").disabled = true;
  refreshJob().then(() => {
    if (activeJob && !terminal.has(activeJob.status) && !waiting.has(activeJob.status)) syncPolling();
    updateSubmitState();
  });
}
