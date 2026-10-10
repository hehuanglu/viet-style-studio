const $ = (selector) => document.querySelector(selector);
const terminal = new Set(["complete", "cards_only", "needs_evidence", "needs_resolution", "failed", "cancelled"]);
const statusLabels = {
  cleaning: "Gemini đang đọc yêu cầu của bạn", designing_checklist: "Gemini đang tìm tham khảo và chuẩn bị lựa chọn",
  checking_selection_conflicts: "Gemini đang kiểm tra xung đột nghiêm trọng trong lựa chọn",
  awaiting_choices: "Xác nhận lựa chọn thiết kế", resolving_choices: "Gemini đang tổng hợp nhu cầu đã chốt",
  generating_prompt_pool: "Đang viết các gợi ý thiết kế", specialist_auditing: "Đang kiểm tra thiết kế từ ba góc nhìn",
  harmony_scoring: "Đang đánh giá hài hòa và tính điểm", selecting: "Đang chọn ba điểm cao nhất",
  writing_design_stories: "Gemini đang viết câu chuyện cho từng thiết kế",
  prompt_writing: "Gemini đang viết prompt tạo ảnh qua API",
  brief_checking: "Gemini đang kiểm tra các thông tin đã nhận diện",
  normalizing: "Đang hiểu yêu cầu", retrieving: "Đang chọn căn cứ",
  rendering: "Đang tạo ảnh qua API", image_repairing: "Đang sửa ảnh qua API", image_checking: "Đang đánh giá ảnh",
  awaiting_image: "Đang chờ bạn gửi ảnh tạo", awaiting_image_repair: "Đang chờ bạn gửi ảnh sửa",
  awaiting_manual_audit: "Chờ kết quả kiểm tra", awaiting_audit_choice: "Chọn cách kiểm tra ảnh",
  concept_repairing: "Đang sửa phương án", repair_auditing: "Đang kiểm tra phương án sửa",
  queued: "Đang xếp hàng", understanding: "Đang hiểu yêu cầu", planning: "Đang tạo phương án",
  auditing: "Đang kiểm tra phương án", cards_ready: "Đã có gợi ý", awaiting_user: "Cần bạn bổ sung thông tin",
  complete: "Hoàn tất", cards_only: "Đã hoàn tất gợi ý bằng chữ", needs_evidence: "Chưa đủ nguồn để tiếp tục",
  needs_resolution: "Chưa đủ gợi ý hợp lệ", failed: "Không thể hoàn thành", cancelled: "Đã hủy",
};
const waiting = new Set(["awaiting_choices", "awaiting_user", "awaiting_image", "awaiting_image_repair", "awaiting_manual_audit", "awaiting_audit_choice"]);
let textApiReady = false;
let simulationEnabled = false;
function updateSubmitState() {
  const ready = textApiReady || (simulationEnabled && $("#simulation-mode").checked);
  $("#submit-request").disabled = !ready || submittingRequest || (!!activeJob && !terminal.has(activeJob.status));
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
let pendingSubmission = null;
let submittingRequest = false;
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

let cloudApiKey = "";

async function stageCloudImages(value) {
  if (Array.isArray(value)) {
    const result = [];
    for (const item of value) result.push(await stageCloudImages(item));
    return result;
  }
  if (!value || typeof value !== "object") return value;
  if (typeof value.data === "string" && typeof value.mime_type === "string" && value.mime_type.startsWith("image/")) {
    const chunks = [];
    for (let offset = 0; offset < value.data.length; offset += 1048576) {
      const chunk = await api("/uploads", {method: "POST", body: JSON.stringify({data: value.data.slice(offset, offset + 1048576)})});
      chunks.push(chunk.asset_id);
    }
    const asset = await api("/uploads/assemble", {method: "POST", body: JSON.stringify({chunks})});
    return {mime_type: value.mime_type, asset_id: asset.asset_id};
  }
  const result = {};
  for (const [key, item] of Object.entries(value)) result[key] = await stageCloudImages(item);
  return result;
}

const cloudAssetUrls = new Map();
async function cloudArtifactUrl(url) {
  const path = url.split("?")[0];
  if (!cloudAssetUrls.has(path)) {
    const pending = (async () => {
      const manifest = await api(path + "/manifest");
      const parts = [];
      for (let part = 0; part < manifest.parts; part++) {
        const controller = new AbortController();
        const timer = setTimeout(() => controller.abort(), 15000);
        try {
          const response = await fetch(path + "/parts/" + part, {headers: {"X-Arena-Session": sessionId}, signal: controller.signal});
          if (!response.ok) throw new Error("Không tải được ảnh đã lưu.");
          parts.push(await response.arrayBuffer());
        } finally { clearTimeout(timer); }
      }
      return URL.createObjectURL(new Blob(parts, {type: manifest.mime_type}));
    })();
    cloudAssetUrls.set(path, pending);
    pending.catch(() => cloudAssetUrls.delete(path));
  }
  return cloudAssetUrls.get(path);
}
async function resolveCloudAssetUrls(value) {
  if (Array.isArray(value)) {
    for (let i = 0; i < value.length; i++) value[i] = await resolveCloudAssetUrls(value[i]);
  } else if (value && typeof value === "object") {
    for (const [key, item] of Object.entries(value)) {
      value[key] = typeof item === "string" && (key === "url" || key.endsWith("_url")) && item.startsWith("/artifacts/")
        ? await cloudArtifactUrl(item) : await resolveCloudAssetUrls(item);
    }
  }
  return value;
}

async function api(path, options = {}) {
  const cloud = typeof window !== "undefined" && window.ARENA_CLOUD === true;
  if (cloud && options.body && !path.startsWith("/uploads")) {
    options = {...options, body: JSON.stringify(await stageCloudImages(JSON.parse(options.body)))};
  }
  const controller = new AbortController();
  const timeoutMs = options.timeoutMs ?? (cloud && options.method === "POST" ? 295000 : 15000);
  let timer;
  const deadline = new Promise((resolve, reject) => {
    timer = setTimeout(() => {
      const error = new Error("Máy chủ chưa phản hồi trong thời gian cho phép. Vui lòng thử lại; thao tác gửi yêu cầu giữ cùng khóa để tránh tạo trùng.");
      error.code = "request_timeout";
      reject(error);
      controller.abort();
    }, timeoutMs);
  });
  const {timeoutMs: ignoredTimeout, ...requestOptions} = options;
  try {
    const response = await Promise.race([fetch(path, {
      ...requestOptions,
      signal: controller.signal,
      headers: { "Content-Type": "application/json", ...(cloud ? {"X-Arena-Session": sessionId, ...(cloudApiKey ? {"X-Gemini-Key": cloudApiKey} : {})} : {}), ...(options.headers || {}) },
    }), deadline]);
    const contentType = response.headers.get("content-type") || "";
    const body = contentType.includes("application/json") ? await Promise.race([response.json(), deadline]) : null;
    if (!response.ok) {
      const error = new Error(body?.error?.message || `Lỗi HTTP ${response.status}`);
      error.code = body?.error?.code;
      error.status = response.status;
      throw error;
    }
    return cloud ? await resolveCloudAssetUrls(body) : body;
  } catch (error) {
    if (error.name === "AbortError") {
      const timeout = new Error("Máy chủ chưa phản hồi trong thời gian cho phép. Vui lòng gửi lại; hệ thống giữ khóa yêu cầu để tránh tạo trùng.");
      timeout.code = "request_timeout";
      throw timeout;
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

function setKeyMessage(message, error = false) {
  const element = $("#key-message");
  element.textContent = message;
  element.classList.toggle("error", error);
}

async function loadHealth() {
  try {
    const health = await api("/health");
    textApiReady = health.text_api_ready ?? (health.provider === "gemini" && health.api_key_configured === true);
    simulationEnabled = health.simulation_enabled === true;
    $("#simulation-option").hidden = !simulationEnabled;
    $("#provider-badge").textContent = textApiReady ? "Đã nhập key" : health.provider === "gemini" ? "Cần kết nối" : "Chỉ mô phỏng";
    $("#provider-badge").className = `badge ${textApiReady ? "connected" : "mock"}`;
    $("#connection-settings").open = !textApiReady;
    $("#text-api-note").textContent = textApiReady ? "Bạn có thể nhập nhu cầu bên dưới. Google sẽ kiểm tra key và quyền sử dụng khi xử lý yêu cầu." : "Kết nối API key ở trên để bắt đầu. Đăng nhập Gemini chưa thay thế bước này.";
    updateSubmitState();
    imagesEnabled = health.images_enabled;
    updateImageMode();
    $("#pack-label").textContent = "Gemini tìm và đọc nguồn theo từng nhu cầu. Tham khảo và đánh giá AI cần được xem xét theo đúng phạm vi.";
  } catch (error) {
    textApiReady = false;
    simulationEnabled = false;
    updateSubmitState();
    $("#provider-badge").textContent = "Chưa kết nối";
    $("#provider-badge").className = "badge";
    $("#pack-label").textContent = "Mở lại ứng dụng để tiếp tục.";
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
  setKeyMessage("Đang kết nối API key…");
  try {
    await api("/session/api-key", { method: "POST", body: JSON.stringify({ api_key: key }) });
    if (window.ARENA_CLOUD === true) cloudApiKey = key;
    keyInput.value = "";
    setKeyMessage("Đã nhập key. Google sẽ kiểm tra quyền sử dụng ở lần xử lý tiếp theo.");
    await loadHealth();
  } catch (error) {
    setKeyMessage(error.message, true);
  } finally {
    button.disabled = false;
  }
});

$("#request-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  if (submittingRequest) return;
  const input = $("#request-input").value;
  if (!input.trim()) return $("#request-input").focus();
  if (!textApiReady && !(simulationEnabled && $("#simulation-mode").checked)) return setKeyMessage("Kết nối Gemini API key để hệ thống nhận diện yêu cầu.", true);
  if (activeJob && !terminal.has(activeJob.status)) return;
  submittingRequest = true;
  $("#submit-request").disabled = true;
  activeJob = null;
  activeId = null;
  stopPolling();
  $("#result-section").hidden = false;
  $("#result-title").textContent = "Đang gửi yêu cầu…";
  $("#result-summary").textContent = "Đang kết nối máy chủ. Hệ thống sẽ thông báo nếu không nhận được phản hồi trong 15 giây.";
  $("#request-error").hidden = true;
  $("#next-action").hidden = true;
  $("#revision-control").hidden = true;
  $("#cards").replaceChildren();
  $("#warnings").replaceChildren();
  $("#question-card").hidden = true;
  $("#image-result").replaceChildren();
  $("#manual-step").hidden = true;
  $("#mock-request-notice").hidden = true;
  renderedManualKey = null;
  uploadDrafts.clear();
  $("#progress").classList.remove("done", "stopped");
  window.scrollTo({ top: $("#result-section").offsetTop - 20, behavior: "smooth" });
  try {
    const submission = {raw_prompt: input, workflow_version: 2, reference_mode: "text_only", creative_level: creativityLevels[Number($("#creative-level").value)].value, session_id: sessionId, render_image: true, image_mode: imageMode(), audit_mode: "none"};
    const fingerprint = JSON.stringify(submission);
    if (!pendingSubmission || pendingSubmission.fingerprint !== fingerprint) pendingSubmission = {fingerprint, key: crypto.randomUUID()};
    const created = await api("/requests", { method: "POST", body: JSON.stringify({...submission, idempotency_key: pendingSubmission.key}) });
    pendingSubmission = null;
    activeId = created.request_id;
    localStorage.setItem("arena-active-request", activeId);
    history.replaceState(null, "", `?request=${encodeURIComponent(activeId)}`);
    $("#cancel-request").hidden = false;
    syncPolling();
    await refreshJob();
  } catch (error) {
    showRequestError(error);
    renderNextAction({status: "failed", error});
    $("#result-title").textContent = "Không gửi được yêu cầu";
  } finally {
    submittingRequest = false;
    updateSubmitState();
  }
});

$("#retry-real-request").addEventListener("click", async () => {
  if (!activeJob || activeJob.provider !== "mock") return;
  const button = $("#retry-real-request");
  button.disabled = true;
  try {
    const original = activeJob.raw_prompt || activeJob.turns[0]?.text || "";
    if (!terminal.has(activeJob.status)) await api(`/requests/${activeId}/cancel`, { method: "POST", body: "{}" });
    $("#request-input").value = original;
    $("#simulation-mode").checked = false;
    await refreshJob();
    setKeyMessage("Đã giữ yêu cầu gốc trong ô nhập. Kết nối API key, rồi bấm Tạo gợi ý để Gemini phân tích lại từ đầu.");
    $("#api-key").focus();
    updateSubmitState();
  } catch (error) {
    showRequestError(error);
  } finally {
    button.disabled = false;
  }
});

$("#cancel-request").addEventListener("click", () => {
  if (!activeId || !activeJob) return;
  const modal = $("#cancel-confirm-modal");
  const summaryBox = $("#modal-summary-content");
  if (modal && summaryBox) {
    const snapshot = activeJob.previous_selection_snapshot || (activeJob.choices ? {checklist: activeJob.checklist, choices: activeJob.choices} : null);
    let summaryHtml = '<p class="modal-eyebrow">YÊU CẦU ĐANG XỬ LÝ</p>';
    if (snapshot) {
      summaryHtml += selectionSummary(snapshot);
    } else if (activeJob.raw_prompt) {
      summaryHtml += `<p style="font-size: 14px; margin-top: 10px;">${escapeHtml(activeJob.raw_prompt)}</p>`;
    } else {
      summaryHtml += `<p style="font-size: 14px; margin-top: 10px;">Yêu cầu chưa rõ</p>`;
    }
    summaryBox.innerHTML = summaryHtml;
    modal.showModal();
  }
});

$("#resume-request")?.addEventListener("click", () => {
  $("#cancel-confirm-modal")?.close();
});

$("#confirm-cancel-request")?.addEventListener("click", async (e) => {
  if (!activeId) return;
  const btn = e.target;
  btn.disabled = true;
  try {
    await api(`/requests/${activeId}/cancel`, { method: "POST", body: "{}" });
    $("#cancel-confirm-modal")?.close();
    await refreshJob();
  } catch (error) {
    showRequestError(error);
  } finally {
    btn.disabled = false;
  }
});

function errorGuidance(error) {
  const code = error?.code || "";
  if (code === "google_http_429") return {message: "Gemini đang giới hạn sử dụng hoặc chưa cấp quyền cho bước này. Kết quả đã nhận và nhu cầu của bạn vẫn được giữ.", next: "Kiểm tra hạn mức API của API key, hoặc đổi key có quyền sử dụng. Sau khi xử lý xong, bấm Thử lại yêu cầu.", quota: true};
  if (["google_http_401", "google_http_403", "missing_api_key"].includes(code)) return {message: "Gemini chưa chấp nhận API key hoặc quyền sử dụng của key.", next: "Nhập lại key trong phần Kết nối Gemini, rồi thử lại yêu cầu.", key: true};
  if (code === "google_http_400") return {message: "Gemini từ chối cấu hình ứng dụng gửi đi. Đây chưa phải lỗi trong cách bạn mô tả bộ đồ.", next: "Nhờ người thiết lập ứng dụng kiểm tra cấu hình Gemini. Sau khi sửa, bấm Thử lại yêu cầu."};
  if (code === "google_http_404") return {message: "Model Gemini đang cấu hình chưa dùng được với key này.", next: "Nhờ người thiết lập ứng dụng chọn model được Google cho phép, rồi thử lại."};
  if (["budget_exhausted", "deadline_exceeded", "session_budget_exhausted", "task_retry_exhausted"].includes(code)) return {message: "Phiên này đã chạm giới hạn xử lý. Kết quả đã nhận vẫn được giữ.", next: "Bạn có thể xem kết quả hiện có hoặc bấm Thử lại yêu cầu để bắt đầu phiên mới."};
  if (["semantic_invalid", "schema_invalid", "provider_invalid_json", "provider_incomplete_output"].includes(code)) return {message: "Gemini đã trả kết quả, nhưng ứng dụng chưa xác nhận được nội dung đầy đủ và đúng với lựa chọn của bạn.", next: "Các lựa chọn đã lưu vẫn được giữ. Nếu có nút Tiếp tục từ lựa chọn đã chốt, hãy dùng nút đó; nếu lỗi lặp lại, xem Chi tiết kỹ thuật."};
  return {message: typeof error === "string" ? error : "Chưa hoàn thành bước này. Nội dung đã nhập vẫn được giữ.", next: "Kiểm tra kết nối và thử lại. Nếu lỗi lặp lại, mở Chi tiết kỹ thuật để người hỗ trợ kiểm tra."};
}

function showRequestError(error) {
  const box = $("#request-error");
  const guidance = errorGuidance(error);
  const technical = typeof error === "string" ? "" : `${error?.message || ""}${error?.code ? ` (${error.code})` : ""}`;
  box.innerHTML = `<p>${escapeHtml(guidance.message)}</p>${technical ? `<details><summary>Chi tiết kỹ thuật</summary><p>${escapeHtml(technical)}</p></details>` : ""}`;
  box.hidden = false;
}

function renderNextAction(job) {
  const box = $("#next-action");
  box.hidden = true;
  if (job.status === "failed" || job.error || job.status === "needs_resolution" && job.workflow_version === 2) {
    const guidance = job.status === "needs_resolution" && !job.error ? {message: "Chưa đủ gợi ý hợp lệ", next: `Hiện có ${job.cards?.length || 0}/3 gợi ý đạt điều kiện từ ${job.prompt_pool?.length || 0} prompt hợp lệ. Các bản lỗi chưa được chọn. Bạn có thể tiếp tục nếu còn ngân sách hoặc sửa lựa chọn.`} : errorGuidance(job.error);
    const task = job.trace?.at(-1)?.task;
    const stoppedAt = ({checking_selection_conflicts: "Kiểm tra xung đột lựa chọn", cleaning: "Hiểu nhu cầu", designing_checklist: "Chuẩn bị bảng lựa chọn", resolving_choices: "Tổng hợp lựa chọn", generating_prompt_pool: "Viết gợi ý thiết kế", specialist_auditing: "Đánh giá thiết kế", harmony_scoring: "Đánh giá hài hòa thiết kế", writing_design_stories: "Viết câu chuyện thiết kế"}[job.failed_stage]) || ({VP02C: "Kiểm tra xung đột lựa chọn", VP01: "Hiểu nhu cầu", VP02: "Chuẩn bị bảng lựa chọn", VP02R: "Tìm nguồn tham khảo"}[task]) || "Xử lý yêu cầu";

    const design = job.user_report?.api?.budgets?.design;
    const canContinue = !["budget_exhausted", "deadline_exceeded", "session_budget_exhausted"].includes(job.error?.code) && (!design || ((job.metrics?.design?.attempts || 0) < design.total_provider_calls_max && (job.metrics?.design?.active_seconds || 0) < design.active_processing_deadline_seconds));
    box.innerHTML = `<div><strong>Đã dừng ở: ${escapeHtml(stoppedAt)}</strong><p>${escapeHtml(guidance.next)}</p>${guidance.quota ? '<p><a href="https://ai.dev/rate-limit" target="_blank" rel="noopener noreferrer">Kiểm tra hạn mức tại Google ↗</a></p>' : ""}</div><div class="manual-actions"><button type="button" class="button button-quiet" data-key-settings>Nhập / đổi API key</button><button type="button" class="button button-accent" data-retry-request>Thử lại yêu cầu</button></div>`;
    box.hidden = false;
    if (canContinue && job.workflow_version === 2 && job.resolved_brief?.status === "ready" && job.prompt_pool?.length && !job.cards?.length) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "button button-accent"; button.textContent = "Tiếp tục phần đánh giá còn thiếu";
      button.addEventListener("click", async () => { button.disabled = true; try { await api(`/requests/${job.request_id}/retry-audits`, {method: "POST", body: JSON.stringify({revision: job.revision})}); await refreshJob(); syncPolling(); } catch (error) { showRequestError(error); button.disabled = false; } });
      box.append(button);
    }
    if (canContinue && job.workflow_version === 2 && job.choices && ((["checking_selection_conflicts", "resolving_choices"].includes(job.failed_stage) && !job.resolved_brief) || (job.resolved_brief?.status === "ready" && !job.prompt_pool?.length && !job.cards?.length))) {
      const button = document.createElement("button");
      button.type = "button"; button.className = "button button-accent"; button.textContent = "Tiếp tục từ lựa chọn đã chốt";
      button.addEventListener("click", async () => { button.disabled = true; try { await api(`/requests/${job.request_id}/retry-resolution`, {method: "POST", body: JSON.stringify({revision: job.revision})}); await refreshJob(); syncPolling(); } catch (error) { showRequestError(error); button.disabled = false; } });
      box.append(button);
    }
    box.querySelector("[data-key-settings]").addEventListener("click", () => { $("#connection-settings").open = true; $("#api-key").focus(); });
    box.querySelector("[data-retry-request]").addEventListener("click", () => { if (job.turns?.[0]) $("#request-input").value = job.raw_prompt || job.turns[0].text;  $("#request-form").requestSubmit(); });
  } else if (job.status === "awaiting_manual_audit") {
    box.hidden = false;
    box.innerHTML = '<strong>Ảnh đã nhận</strong><a class="button button-quiet small-button" href="#manual-step">Kiểm tra ảnh ↓</a>';
  } else if (job.status === "awaiting_image" && job.workflow_version === 2) {
    box.hidden = false;
    const selected = (job.cards || []).find(card => job.image_target_ids?.includes(card.candidate_id));
    box.innerHTML = `<div><strong>${selected ? `Đang nhận ảnh cho: ${escapeHtml(selected.title)}` : "Bước tiếp: chọn một gợi ý để xem ảnh"}</strong><p>Bấm Copy prompt ở thẻ bạn thích. Hướng dẫn này dùng để tạo ảnh; nút sẽ sao chép sẵn để bạn dán vào Gemini. Sau đó tải ảnh về và gửi vào đây.</p><p class="tiny-note">Đánh giá áp dụng cho bản mô tả thiết kế; ảnh thực tế chưa được tạo.</p></div>`;
  }
}

function v2Summary(job) {
  if (job.status === "awaiting_choices") return "Xem những phần đã hiểu và chọn các chi tiết còn thiếu bên dưới.";
  if (job.status === "awaiting_image") return `Có ${job.cards?.length || 0} gợi ý bằng chữ. Chọn gợi ý bạn thích để tạo ảnh trên Gemini.`;
  if (job.status === "failed") return "Phiên đang dừng. Nhu cầu và các kết quả đã nhận vẫn được giữ; xem bước xử lý bên dưới.";
  if (job.status === "cancelled") return "Đã dừng theo yêu cầu. Bạn có thể nhập lại nhu cầu để bắt đầu phiên mới.";
  if (job.status === "complete" && job.output_artifact_ids?.length) return "Ảnh đã được lưu. Xem ảnh bên dưới, tải về hoặc mở ảnh để khoanh phần muốn sửa. Nhận xét kiểm tra bằng AI có thể sai.";
  if (terminal.has(job.status)) return job.user_report?.final || "Xem kết quả hiện có bên dưới.";
  return "Bạn chưa cần thao tác. Gemini đang xử lý; việc chuẩn bị gợi ý có thể mất vài phút.";
}

async function copyPrompt(text, textarea = null) {
  try {
    if (navigator.clipboard?.writeText) {
      await navigator.clipboard.writeText(text);
      return;
    }
  } catch (_) { /* Select the exact text below for the legacy/manual fallback. */ }
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
    if (!document.execCommand("copy")) throw new Error("Clipboard không khả dụng");
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

function shouldChooseCopiedCandidate(job, card) {
  const ids = new Set((job.cards || []).map(item => item.candidate_id));
  const hasImages = (job.artifacts || []).some(item => job.workflow_version !== 2 || ids.has(item.candidate_id));
  return job.status === "awaiting_image" && !!job.pending_manual && !hasImages
    && !job.image_target_ids?.includes(card.candidate_id);
}

async function chooseImageCandidate(job, card) {
  await api(`/requests/${job.request_id}/image-candidate`, {method: "POST", body: JSON.stringify({
    revision: job.revision, step_id: job.pending_manual.step_id, candidate_id: card.candidate_id,
  })});
  renderedManualKey = null;
  uploadDrafts.clear();
  await refreshJob();
}

function renderCards(job) {
  const cards = job.cards || [];
  $("#cards").innerHTML = cards.map((card, index) => {
    const design = card.design || {}, prompt = candidatePrompt(job, card, index);
    const story = card.design_story;
    const tags = [...(design.palette || []), ...(design.accessories || [])];
    const sources = (card.source_caption || []).map(source => source.source_url
      ? `<a href="${escapeHtml(source.source_url)}" target="_blank" rel="noreferrer">${escapeHtml(source.text || source.source_id || "Nguồn tham khảo")}</a>`
      : escapeHtml(source.text || ""));
    const reviews = [
      ["Thời trang / cấu trúc", card.fashion_summary, card.specialist_reviews?.fashion],
      ["Văn hóa / lịch sử", card.culture_summary, card.specialist_reviews?.culture],
      ["Hội họa / mỹ thuật", card.art_summary, card.specialist_reviews?.art],
    ].map(([label, text, review]) => `<section class="specialist-section"><div class="specialist-heading"><h4>${label}</h4></div><p>${escapeHtml(text || "")}</p>${review ? `<details class="ai-review"><summary>Nhận xét AI</summary><div class="ai-review-body"><p>${escapeHtml(review.summary || "")}</p>${review.concerns?.length ? `<ul>${review.concerns.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul>` : ""}</div></details>` : ""}</section>`).join("");
    return `<article class="idea-card ${index === 0 ? "idea-card-recommended" : ""}">
      <header class="idea-card-header"><div class="idea-top"><span class="idea-index">PHƯƠNG ÁN ${String(index + 1).padStart(2, "0")}</span>${index === 0 ? '<span class="chosen-label">Đề xuất</span>' : ""}</div><h3>${escapeHtml(card.title || "Gợi ý phối đồ")}</h3></header>
      <div class="idea-card-body">${job.workflow_version === 2 ? `<section class="design-story"><h4>Câu chuyện thiết kế</h4>${story ? `<p>${escapeHtml(story.origin_and_meaning)}</p>${story.cultural_combination_warnings?.length ? `<div class="story-notes"><h5>Lưu ý kết hợp văn hóa</h5><ul>${story.cultural_combination_warnings.map(item => `<li>${escapeHtml(item)}</li>`).join("")}</ul></div>` : ""}` : `<p class="muted">${job.status === "writing_design_stories" ? "Gemini đang viết câu chuyện từ prompt của phương án này…" : "Chưa có câu chuyện thiết kế cho phương án này."}</p>`}</section><div class="design-perspectives">${reviews}</div>` : `<p>${escapeHtml(card.target_need || "")}</p><p>${escapeHtml(design.subject_description || "")} ${escapeHtml(design.scene || "")}</p>`}
      ${tags.length ? `<div class="tag-list">${tags.map(tag => `<span class="tag">${escapeHtml(tag)}</span>`).join("")}</div>` : ""}
      ${sources.length ? `<p class="source-line">Nguồn: ${sources.join(" · ")}</p>` : ""}</div>
      <footer class="idea-card-footer"><button type="button" class="button-primary copy-prompt-button" data-copy-option="${index}" aria-label="Copy prompt phương án ${index + 1}" ${prompt ? "" : "disabled"}><svg aria-hidden="true" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="8" y="8" width="12" height="12" rx="2"/><path d="M16 8V4a2 2 0 0 0-2-2H4a2 2 0 0 0-2 2v10a2 2 0 0 0 2 2h4"/></svg>Copy prompt</button><span role="status" aria-live="polite" class="option-prompt-status">${prompt ? "" : "Đang chuẩn bị prompt…"}</span>
      <div id="option-prompt-${index}" hidden class="option-prompt-textarea"><label for="option-prompt-text-${index}">Prompt phương án ${index + 1}</label><textarea id="option-prompt-text-${index}" rows="8" readonly>${escapeHtml(prompt)}</textarea></div></footer>
    </article>`;
  }).join("");
  $("#cards").querySelectorAll("[data-copy-option]").forEach(button => button.addEventListener("click", async () => {
    const index = Number(button.dataset.copyOption), candidate = cards[index];
    const panel = button.closest(".idea-card").querySelector(".option-prompt-textarea");
    const textarea = panel.querySelector("textarea");
    const message = button.closest(".idea-card").querySelector(".option-prompt-status");
    button.disabled = true;
    try {
      await copyPrompt(candidatePrompt(job, candidate, index), textarea);
      message.textContent = "Đã copy · dán vào Gemini";
      if (shouldChooseCopiedCandidate(job, candidate)) {
        try {
          await chooseImageCandidate(job, candidate);
          const current = $("#cards").querySelector(`[data-copy-option="${index}"]`);
          if (current) current.closest(".idea-card").querySelector(".option-prompt-status").textContent = "Đã copy · đang nhận ảnh cho phương án này";
        } catch (error) { message.textContent = "Đã copy. Chưa chọn được phương án nhận ảnh; bấm Copy prompt để thử lại."; showRequestError(error); }
      }
    } catch (_) {
      panel.hidden = false; textarea.focus(); textarea.select();
      message.textContent = "Dùng Ctrl+C / ⌘C để copy đoạn đã chọn, rồi bấm Copy prompt để chốt phương án.";
    } finally { button.disabled = false; }
  }));
}

function renderQuestion(job) {
  if (job.workflow_version === 2) return renderChecklist(job);
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
    showRequestError(error);
    $("#question-card").querySelectorAll("button,input").forEach((element) => { element.disabled = false; });
  }
}

function renderWarnings(job) {
  const messages = [...(job.warnings || [])];
  if (job.status === "needs_evidence") messages.unshift("Chưa đủ nguồn cho phần bắt buộc. Giữ nguyên mức lịch sử đã yêu cầu; có thể điều chỉnh yêu cầu.");
  if (job.status === "cards_only" && job.render_image && !job.artifacts?.length) messages.unshift("Không có ảnh đã kiểm tra; các gợi ý bằng chữ vẫn được giữ lại.");
  if (job.workflow_version === 2) {
    const basic = job.reference_mode === "text_only" ? '<p class="warning">Ứng dụng hỗ trợ ý tưởng hiện đại, không có nguồn web đã tìm/đọc và không xác nhận lịch sử.</p>' : "";
    const usageWarnings = [...new Set(job.api_call_warnings || [])];
    const usageNotice = usageWarnings.map(message => `<p class="warning" role="status">${escapeHtml(message)}</p>`).join("");
    $("#warnings").innerHTML = basic + usageNotice + (job.status === "needs_evidence" ? '<p class="warning">Chưa đủ nguồn cho yêu cầu đã chốt. Bạn có thể sửa lựa chọn hoặc điều chỉnh yêu cầu.</p>' : "");
    return;
  }
  $("#warnings").innerHTML = messages.map((message) => `<div class="warning">${escapeHtml(message)}</div>`).join("");
}

function renderImage(job) {
  const currentIds = job.output_artifact_ids || (job.artifacts || []).filter(a => !(job.artifacts || []).some(child => child.parent_artifact_id === a.artifact_id)).map(a => a.artifact_id);
  const editable = waiting.has(job.status) || ["complete", "cards_only"].includes(job.status);
  const imageReview = (artifact) => {
    if (job.workflow_version !== 2) return "";
    const audit = (job.image_audits || []).flatMap(batch => batch.audits || []).reverse().find(row => row.artifact_id === artifact.artifact_id);
    return audit ? `<details><summary>Nhận xét kiểm tra ảnh bằng AI</summary><p>AI có thể nhìn nhầm chi tiết. Hãy đối chiếu với ảnh trước khi quyết định sửa tiếp.</p><p>${escapeHtml(audit.quality_reason)}</p>${audit.findings.map(f => `<p>${escapeHtml(f.evidence)} · ${escapeHtml(f.reason)}</p>`).join("")}</details>` : "";
  };
  const imageMarkup = (artifact) => `<div class="image-result">
    <button type="button" class="image-open" data-edit-image="${escapeHtml(artifact.artifact_id)}" ${editable ? "" : "disabled"} aria-label="Mở ảnh để phác thảo"><img src="${escapeHtml(artifact.url)}" alt="${artifact.parent_artifact_id ? "Ảnh sửa" : "Ảnh tạo"}" /></button>
    <div class="image-info" style="flex: 1;">
      <p style="margin: 0 0 8px 0; font-size: 14px;"><strong>${escapeHtml((job.cards || []).find(c => c.candidate_id === artifact.candidate_id)?.title || artifact.candidate_id || "")}</strong></p>
      <div style="display: flex; gap: 10px; margin-top: 15px; margin-bottom: 10px; flex-wrap: wrap;">
        <a class="button-secondary" href="${escapeHtml(artifact.url)}" download style="text-decoration: none;">Tải ảnh</a>
        <button type="button" class="button-primary" data-edit-image="${escapeHtml(artifact.artifact_id)}" ${editable ? "" : "disabled"}>Mở ảnh / Phác thảo chỉnh sửa</button>
      </div>
      ${imageReview(artifact)}
    </div>
  </div>`;
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
        await api(`/requests/${job.request_id}/image-edits`, {method: "POST", body: JSON.stringify({revision: activeJob.revision, parent_artifact_id: artifact.artifact_id, audit_mode: "none", image: result.image, filename: result.filename, ...context})});
        renderedManualKey = null; await refreshJob(); syncPolling();
      }});
    } catch (error) { showRequestError(error); }
    finally { button.disabled = false; }
  }));
}

const creativityLevels = [
  {value: "moderate", label: "Vừa phải", description: "Điều chỉnh tiết chế, dùng cách đánh giá cân bằng."},
  {value: "balanced", label: "Cân bằng", description: "Cân bằng tính ứng dụng và ý tưởng sáng tạo."},
  {value: "explore", label: "Khám phá", description: "Ưu tiên ý tưởng mới và sáng tạo, vẫn giữ các chi tiết bạn đã chốt."},
];
function updateCreativity() {
  const input = $("#creative-level"), level = creativityLevels[Number(input.value)] || creativityLevels[2];
  $("#creative-level-label").textContent = level.label;
  $("#creative-level-description").textContent = level.description;
  input.setAttribute("aria-valuetext", level.label);
  input.style.setProperty("--creativity-fill", `${Number(input.value) * 50}%`);
}
$("#creative-level").addEventListener("input", updateCreativity);

function imageMode() { return $("#image-mode").getAttribute("aria-pressed") === "true" ? "api" : "gemini_manual"; }
function updateImageMode() {
  $("#image-mode").querySelector(".auto-image-state").textContent = imageMode() === "api" ? "Bật" : "Tắt";
  const manual = imageMode() === "gemini_manual";
  $("#image-note").textContent = manual ? "Sau khi có gợi ý, tạo ảnh trên Gemini rồi gửi về để xem và chỉnh sửa." : imagesEnabled ? "Tạo ảnh tự động qua API — cần bật billing, có tính phí" : "Tạo ảnh API cần bật billing và được người thiết lập ứng dụng bật tính năng";
}
$("#image-mode").addEventListener("click", () => {
  $("#image-mode").setAttribute("aria-pressed", String(imageMode() !== "api"));
  updateImageMode();
});

async function resumeStep(job, endpoint, data = {}) {
  const box = $("#manual-step");
  box.querySelectorAll("button,input,textarea").forEach((element) => { element.disabled = true; });
  $("#request-error").hidden = true;
  $("#progress")?.scrollIntoView({ behavior: "smooth", block: "center" });
  try {
    await api(`/requests/${job.request_id}/${endpoint}`, {method: "POST", body: JSON.stringify({revision: job.revision, step_id: job.pending_manual.step_id, ...data})});
    renderedManualKey = null;
    stopPolling();
    await refreshJob();
    if (activeJob && !terminal.has(activeJob.status) && !waiting.has(activeJob.status)) syncPolling();
  } catch (error) {
    showRequestError(error);
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
  if (["audit_choice", "audit"].includes(pending.kind)) {
    box.innerHTML = `${heading("Kiểm tra ảnh")}<p>Bạn có thể bỏ qua kiểm tra ảnh và tiếp tục chỉnh sửa trực tiếp.</p><button class="button-primary" id="choose-background-audit" style="margin-top: 10px;">Bỏ qua kiểm tra ảnh và tiếp tục</button>`;
    box.querySelector("#choose-background-audit").addEventListener("click", () => resumeStep(job, "background-audit-mode", {audit_mode: "none"}));
    return;
  }
  const repair = pending.kind === "repair";
  const instructions = repair
      ? "Copy yêu cầu sửa và tiếp tục cuộc trò chuyện Gemini đã tạo ảnh. Đính kèm ảnh gốc, tải ảnh sửa về rồi gửi tại đây."
      : "Bấm Copy prompt ở thẻ bạn thích để sao chép và chọn phương án. Mở Gemini, dán đoạn vừa sao chép và gửi. Nếu Gemini chỉ trả lời bằng chữ, chọn Công cụ → Tạo ảnh rồi gửi lại. Tải ảnh Gemini trả về, quay lại đây bấm Chọn ảnh (hoặc copy ảnh rồi bấm Dán ảnh), kiểm tra tên phương án và bấm Gửi ảnh. Sau đó bấm vào ảnh để chỉnh sửa.";
  const relevant = (job.artifacts || []).filter((a) => a.artifact_id === pending.artifact_id || a.artifact_id === pending.parent_artifact_id);
  relevant.sort((a, b) => Number(b.artifact_id === pending.artifact_id) - Number(a.artifact_id === pending.artifact_id));
  box.innerHTML = `${heading(repair ? "Sửa ảnh" : "Tạo ảnh với Gemini")}
    ${!repair ? '<div class="manual-path" aria-label="Các bước tạo ảnh"><span>01 · Copy prompt</span><span>02 · Tạo trên Gemini</span><span>03 · Gửi ảnh</span></div>' : ""}
    <div class="manual-actions" style="display: flex; gap: 10px; margin-top: 15px; flex-wrap: wrap;">
      ${repair ? `<button type="button" class="button-primary" id="copy-prompt">Copy prompt</button>` : ""}
      <a class="button-secondary gemini-button" href="https://gemini.google.com/" target="_blank" rel="noreferrer" style="text-decoration: none;">Mở Gemini ↗</a>
      <span id="copy-message" role="status" style="width: 100%; color: var(--muted); font-size: 13px;"></span>
    </div>
    ${relevant.length ? `<div class="manual-references">${relevant.map((a) => `<div class="audit-reference"><img src="${escapeHtml(a.url)}" alt="${a.artifact_id === pending.artifact_id ? "Ảnh cần kiểm tra" : "Ảnh gốc"}" /><a class="button-secondary small-button" href="${escapeHtml(a.url)}" download style="text-decoration: none;">${a.artifact_id === pending.artifact_id ? "Tải ảnh cần kiểm tra" : "Tải ảnh gốc"}</a></div>`).join("")}</div>` : ""}
    <div class="manual-upload" tabindex="0" aria-label="Dán ảnh Gemini" style="margin-top: 20px;"><div class="upload-control" style="display: flex; gap: 10px; align-items: center;"><button type="button" class="button-secondary" id="paste-image">Dán ảnh</button><label for="manual-image" class="button-secondary upload-button" style="margin: 0;">Chọn ảnh</label><input id="manual-image" class="visually-hidden" type="file" accept="image/png,image/jpeg,image/webp" /><span id="upload-name" style="font-size: 13px; color: var(--muted);">Chưa chọn ảnh</span></div><span class="upload-hint" style="display: block; margin-top: 8px;">Ctrl+V / ⌘V hoặc chọn ảnh · PNG, JPG, WebP · tối đa 10 MB</span><div id="upload-preview" style="margin-top: 15px;"></div><div class="manual-actions" style="display: flex; gap: 10px; margin-top: 15px;"><button id="edit-upload" type="button" class="button-secondary" hidden>Mở ảnh / Phác thảo chỉnh sửa</button><button id="confirm-image" type="button" class="button-primary" disabled>Gửi ảnh</button></div></div>
    ${!["background", "none"].includes(job.audit_mode) ? '<button type="button" class="button-secondary" id="switch-direct-edit" style="margin-top: 15px;">Dùng quy trình chỉnh sửa trực tiếp</button>' : ""}
    <details class="manual-help" style="margin-top: 20px;" ${!repair ? "open" : ""}><summary>Hướng dẫn từng bước</summary><p style="margin-top: 10px;">${instructions}</p></details>`;
  box.querySelector("#copy-prompt")?.addEventListener("click", async () => {
    try {
      await copyPrompt(pending.prompt);
      box.querySelector("#copy-message").textContent = "Đã sao chép hướng dẫn";
    } catch (_) {
      box.querySelector("#copy-message").textContent = "Trình duyệt chưa cho phép copy. Hãy cấp quyền clipboard rồi thử lại.";
    }
  });
  box.querySelector("#switch-direct-edit")?.addEventListener("click", () => resumeStep(job, "background-audit-mode", {audit_mode: "none"}));
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
    } catch (error) { if (version === selectionVersion && renderedManualKey === key) showRequestError(error); }
  }
  async function openSelected() {
    if (!selectedImage) return;
    try {
      await editor().open({image: selectedImage, filename: selectedName, job, candidateId, onComplete: async (result, packet) => {
        if (renderedManualKey !== key) throw new Error("Bước nhận ảnh đã thay đổi. Hãy mở lại bước hiện tại.");
        ++selectionVersion; showPreview(result, packet);
      }});
    } catch (error) { showRequestError(error); }
  }
  editButton.addEventListener("click", openSelected);
  box.querySelector("#manual-image").addEventListener("change", event => selectFile(event.target.files[0]));
  box.querySelector("#paste-image").addEventListener("click", async () => {
    try { const file = await arenaImageFromClipboard(); if (renderedManualKey === key) await selectFile(file); }
    catch (error) { showRequestError(error); box.querySelector(".manual-upload").focus(); }
  });
  document.addEventListener("paste", event => {
    const file = [...(event.clipboardData?.items || [])].find(item => item.kind === "file" && item.type.startsWith("image/"))?.getAsFile();
    if (file && !imageEditor?.dialog.open && renderedManualKey === key) { event.preventDefault(); selectFile(file); }
  }, {signal: manualPasteController.signal});
  confirm.addEventListener("click", async () => {
    if (!selectedImage) return;
    await resumeStep(job, "images", {audit_mode: "none", image: selectedImage, filename: selectedName, ...(selectedEdit ? {edit_context: selectedEdit} : {})});
    if (activeJob?.pending_manual?.step_id !== pending.step_id) uploadDrafts.delete(draftKey);
  });
  const draft = uploadDrafts.get(draftKey);
  if (draft) showPreview(draft.result, draft.context);
}

async function refreshJob() {
  if (!activeId) return;
  const requestId = activeId;
  try {
    const job = await api(`/requests/${requestId}`);
    if (requestId !== activeId) return;
    if (isOlderJob(job, activeJob)) return;
    if (!activeJob || activeJob.request_id !== job.request_id) {
      $("#image-mode").setAttribute("aria-pressed", String(job.image_mode === "api" && !terminal.has(job.status)));
      $("#request-input").value = job.raw_prompt || job.turns[0]?.text || "";
      if (job.creative_level) { $("#creative-level").value = Math.max(0, creativityLevels.findIndex(level => level.value === job.creative_level)); updateCreativity(); }
    }
    const previousStatus = activeJob ? activeJob.status : null;
    activeJob = job;
    $("#image-mode").disabled = !terminal.has(job.status);
    updateImageMode();
    $("#result-section").hidden = false;
    $("#request-error").hidden = true;
    updateSubmitState();
    $("#mock-request-notice").hidden = job.provider !== "mock";
    $("#result-title").textContent = statusLabels[job.status] || job.status;
    const subjectLabel = {au_phuc: "âu phục", ao_dai: "áo dài", ao_tu_than: "áo tứ thân", ao_ngu_than: "áo ngũ thân", ao_va_chan_vay: "áo phối chân váy", vay_lien: "váy liền thân"}[job.brief?.subject?.value] || job.brief?.subject?.value;
    $("#result-summary").textContent = job.workflow_version === 2 ? v2Summary(job) : subjectLabel ? `Đối tượng: ${subjectLabel}${job.brief.mode ? ` · ${job.brief.mode === "historical" ? "theo hướng lịch sử" : "lấy cảm hứng"}` : ""}` : "";

    const progressMap = { queued: 5, cleaning: 10, understanding: 15, designing_checklist: 20, checking_selection_conflicts: 25, awaiting_choices: 30, resolving_choices: 40, generating_prompt_pool: 50, specialist_auditing: 60, harmony_scoring: 70, selecting: 80, writing_design_stories: 85, prompt_writing: 85, cards_ready: 90, awaiting_image: 95, rendering: 96, image_repairing: 97, image_checking: 98, complete: 100, cards_only: 100 };
    let progressPercent = progressMap[job.status] || 50;
    const progressSpan = $("#progress span");
    if (terminal.has(job.status)) {
        if (job.status === "cancelled" || job.status === "failed") {
            $("#progress").className = "progress-track stopped";
            progressSpan.style.width = "100%";
        } else {
            $("#progress").className = "progress-track done";
            progressSpan.style.width = "100%";
        }
    } else if (waiting.has(job.status)) {
        $("#progress").className = "progress-track paused";
        progressSpan.style.width = progressPercent + "%";
    } else {
        $("#progress").className = "progress-track loading";
        progressSpan.style.width = progressPercent + "%";
    }

    $("#cancel-request").hidden = terminal.has(job.status);
    renderQuestion(job);
    renderCards(job);
    renderWarnings(job);
    renderImage(job);
    renderManual(job);
    renderNextAction(job);
    renderRevisionControl(job);
    if (previousStatus !== job.status) {
      setTimeout(() => {
        if (waiting.has(job.status)) {
          if (job.status === "awaiting_choices") $("#question-card")?.scrollIntoView({ behavior: "smooth", block: "start" });
          else if (job.status === "awaiting_image") $("#cards")?.scrollIntoView({ behavior: "smooth", block: "start" });
          else if (job.status === "awaiting_manual_audit" || job.status === "awaiting_image_repair") $("#manual-step")?.scrollIntoView({ behavior: "smooth", block: "start" });
        } else if (terminal.has(job.status)) {
          if (job.status === "complete") $("#image-result")?.scrollIntoView({ behavior: "smooth", block: "start" });
          else if (job.status === "cards_only") $("#cards")?.scrollIntoView({ behavior: "smooth", block: "start" });
        }
      }, 100);
    }
    if (job.error) showRequestError(job.error);
    syncPolling();
  } catch (error) {
    if (requestId !== activeId) return;
    stopPolling();
    showRequestError(error);
    const action = $("#next-action");
    action.hidden = false;
    action.innerHTML = '<div><strong>Chưa tải được tiến độ</strong><p>Không cần nhập lại nhu cầu. Kiểm tra kết nối rồi tải lại tiến độ của phiên đang mở.</p></div><button type="button" class="button button-accent" data-refresh-job>Tải lại tiến độ</button>';
    action.querySelector("[data-refresh-job]").addEventListener("click", refreshJob);
  }
}

let renderedChecklistKey = null;
function referenceMarkup(reference) {
  const safe = (url) => /^https?:\/\//i.test(url || "") ? escapeHtml(url) : "";
  const url = safe(reference.url), preview = safe(reference.preview_url);
  const explanation = `<p>${escapeHtml(reference.description)}</p><p class="tiny-note">${escapeHtml(reference.scope)} · ${reference.discovery_status === "tool_grounded" ? "Có metadata công cụ Gemini; chưa xác nhận chuyên môn" : "Chưa tìm được / chưa có xuất xứ công cụ"}</p>${preview ? `<img src="${preview}" alt="${escapeHtml(reference.label)}" loading="lazy" referrerpolicy="no-referrer" onerror="this.hidden=true" />` : ""}`;
  const link = url ? `<a href="${url}" target="_blank" rel="noopener noreferrer">${escapeHtml(reference.label)} ↗</a>` : `<span>${escapeHtml(reference.label)} · chưa tìm được link</span>`;
  return `<div class="reference-preview">${link}<div class="reference-hover" role="tooltip">${explanation}</div><details><summary>Xem mẫu</summary><div class="reference-body">${explanation}${url ? `<a href="${url}" target="_blank" rel="noopener noreferrer">Mở trang chi tiết ↗</a>` : ""}</div></details></div>`;
}

function choiceProblem(groups, selections) {
  const selected = new Map(selections.map(item => [item.group_id, item]));
  for (const group of groups) {
    if (group.status === "locked" || !group.depends_on.every(dep => dep.option_ids.some(id => selected.get(dep.group_id)?.option_ids.includes(id)))) continue;
    const item = selected.get(group.group_id);
    const count = (item?.option_ids.length || 0) + Number(!!item?.custom_text.trim());
    if (group.status === "needs_choice" && count < group.min) return `Ở “${group.label}”, hãy chọn ít nhất ${group.min} ý, giao AI đề xuất hoặc nhập ý riêng.`;
    if (count > group.max) return `Ở “${group.label}”, chỉ chọn tối đa ${group.max} ý (tính cả ý riêng).`;
  }
  return "";
}

function selectionSummary(snapshot) {
  if (!snapshot?.checklist || !snapshot.choices) return "";
  const groups = new Map(snapshot.checklist.groups.map(g => [g.group_id, g]));
  const rows = (snapshot.choices.selections || []).map(item => {
    const group = groups.get(item.group_id);
    if (!group) return "";
    const labels = item.option_ids.map(id => group.options.find(o => o.option_id === id)).filter(Boolean).map(o => o.is_ai_delegate ? "Để AI đề xuất" : o.label);
    if (item.custom_text?.trim()) labels.push(`Yêu cầu riêng: ${item.custom_text}`);
    return labels.length ? `<div class="summary-bar"><span class="summary-label">${escapeHtml(group.label)}</span><span class="summary-value">${labels.map(escapeHtml).join(" · ")}</span></div>` : "";
  }).filter(Boolean);
  const changes = (snapshot.choices.explicit_changes || []).map(c => `<div class="summary-bar"><span class="summary-label">Đã sửa yêu cầu</span><span class="summary-value">${escapeHtml(c.replacement_text)}</span></div>`);
  const content = rows.concat(changes).join("") || `<div class="summary-bar"><span class="summary-value">Giữ các thông tin đã hiểu, không thêm lựa chọn.</span></div>`;
  return `<div class="summary-container">${content}</div>`;
}

function renderChecklist(job) {
  const box = $("#question-card"), checklist = job.checklist;
  if (job.status !== "awaiting_choices" || !checklist) {
    const snapshot = job.choices && checklist ? {checklist, choices: job.choices} : job.previous_selection_snapshot;
    const summary = selectionSummary(snapshot);
    box.hidden = !summary;
    if (summary) box.innerHTML = `<details open><summary>Lựa chọn đã chốt để đối chiếu</summary>${summary}<p class="tiny-note">Bạn có thể chọn lại từ bảng đã có bằng nút bên dưới.</p></details>`;
    else box.replaceChildren();
    renderedChecklistKey = null; return;
  }
  const conflictReview = job.selection_review?.status === "conflict" ? job.selection_review.conflicts : [];
  const conflictMarkup = conflictReview.length ? `<section role="alert"><h4>Cần sửa xung đột nghiêm trọng</h4>${conflictReview.map(c => `<div><strong>${escapeHtml(c.summary)}</strong><p>${escapeHtml(c.reason)}</p><p>Chi tiết đang xung đột: ${escapeHtml(c.same_feature)}</p><ul>${c.evidence.map(e => `<li>${escapeHtml(e.quote)}</li>`).join("")}</ul><p>Gợi ý sửa: ${escapeHtml(c.suggested_fix)}</p></div>`).join("")}<p>Lựa chọn đã được giữ bên dưới. Hãy sửa rồi chốt lại để Gemini kiểm tra; chỉ tiếp tục khi hết xung đột nghiêm trọng.</p></section>` : (job.resolved_brief?.status === "needs_resolution" ? `<section role="alert"><h4>Cần làm rõ yêu cầu</h4>${(job.resolved_brief.conflicts || []).map(c => `<p>${escapeHtml(typeof c === "string" ? c : JSON.stringify(c))}</p>`).join("")}</section>` : "");
  const key = `${job.request_id}:${job.revision}:${checklist.form_id}`;
  if (key === renderedChecklistKey) return;
  renderedChecklistKey = key;
  const references = new Map((checklist.references || []).map(r => [r.reference_id, r]));
  const groups = checklist.groups || [];
  box.hidden = false;
  box.innerHTML = `<h3>Chọn những chi tiết còn thiếu</h3><p>${escapeHtml(checklist.clean_prompt.clean_text)}</p><p class="muted">Ở mỗi phần cần chọn, bấm ý bạn thích, giao AI đề xuất hoặc nhập ý riêng. “Đã xác định” là phần được giữ từ lời bạn nói. ${job.choice_restore ? "Các lựa chọn bạn đã chốt được giữ lại; bạn có thể thay đổi trước khi chốt lần mới." : "Không có lựa chọn nào được chọn sẵn."}</p>${job.previous_selection_snapshot ? `<details><summary>Đối chiếu lựa chọn trước</summary>${selectionSummary(job.previous_selection_snapshot)}</details>` : ""}
    ${conflictMarkup}<form id="choice-form">${groups.map((g, index) => `<details class="choice-group" data-group="${escapeHtml(g.group_id)}" ${index < 6 ? "open" : ""}><summary>${escapeHtml(g.label)} · ${g.status === "locked" ? "Đã xác định" : g.selection_mode === "single" ? "Chọn một" : "Chọn nhiều"}</summary><fieldset ${g.status === "locked" ? "disabled" : ""}>
    <legend>${escapeHtml(g.question)}</legend><p class="muted">${escapeHtml(g.why_it_matters)}</p>${g.status !== "locked" ? `<p class="tiny-note">${g.status === "needs_choice" ? `Cần chọn ít nhất ${g.min}` : "Có thể bỏ qua"} · tối đa ${g.max} ý, tính cả ý riêng.</p>` : ""}
    ${g.status === "locked" ? g.related_atom_ids.map(aid => `<p>${escapeHtml(checklist.clean_prompt.atoms.find(a => a.atom_id === aid)?.meaning)}</p>`).join("") : g.options.map(o => `<div class="choice-option"><label><input type="${g.selection_mode === "single" ? "radio" : "checkbox"}" name="${escapeHtml(g.group_id)}" value="${escapeHtml(o.option_id)}" data-delegate="${o.is_ai_delegate}" /><strong>${o.is_ai_delegate ? "Để AI đề xuất" : escapeHtml(o.label)}</strong></label><p>${escapeHtml(o.description)}</p>${o.reference_ids.map(rid => references.has(rid) ? referenceMarkup(references.get(rid)) : "").join("")}</div>`).join("") + `<label>Nhập yêu cầu riêng<textarea data-custom rows="2" maxlength="6000" placeholder="Nhập để chọn ý riêng…"></textarea></label>`}
    </fieldset><p data-inactive class="tiny-note" hidden>Chọn nhóm nền phù hợp để mở phần này.</p></details>`).join("")}
    <details class="explicit-changes"><summary>Sửa ý đã hiểu (cần xác nhận)</summary>${checklist.clean_prompt.atoms.map(a => `<div data-change-atom="${escapeHtml(a.atom_id)}"><p>${escapeHtml(a.meaning)}</p><textarea rows="2" maxlength="6000" placeholder="Ý thay thế…"></textarea><label><input type="checkbox" /> Tôi xác nhận thay ý này</label></div>`).join("")}</details>
    <div class="reference-results">${(job.reference_metadata || []).map(m => m.groundingMetadata?.searchEntryPoint?.renderedContent).filter(Boolean).map(html => `<iframe title="Gợi ý tìm kiếm Google do Gemini trả" sandbox="allow-popups allow-popups-to-escape-sandbox" srcdoc="${escapeHtml(html)}"></iframe>`).join("")}</div>
    <p id="choice-error" class="error" role="alert"></p><button class="button button-accent" type="submit">Xác nhận lựa chọn và kiểm tra xung đột</button></form>`;
  const form = box.querySelector("#choice-form");
  const sections = new Map([...form.querySelectorAll("[data-group]")].map(el => [el.dataset.group, el]));
  function selections() {
    return groups.filter(g => g.status !== "locked").map(g => {
      const section = sections.get(g.group_id), field = section.querySelector("fieldset");
      return {group_id: g.group_id, option_ids: field.disabled ? [] : [...section.querySelectorAll("input:checked")].map(el => el.value), custom_text: field.disabled ? "" : section.querySelector("[data-custom]").value};
    });
  }
  function dependencies() {
    // Recompute to a fixed point so changing an ancestor clears every descendant.
    for (let pass = 0; pass <= groups.length; pass++) {
      const picked = new Map(selections().map(s => [s.group_id, s.option_ids]));
      for (const g of groups) {
        if (g.status === "locked") continue;
        const section = sections.get(g.group_id), field = section.querySelector("fieldset");
        const active = g.depends_on.every(d => d.option_ids.some(id => (picked.get(d.group_id) || []).includes(id)));
        field.disabled = !active; section.querySelector("[data-inactive]").hidden = active;
        if (!active) { section.querySelectorAll("input").forEach(el => { el.checked = false; }); section.querySelector("[data-custom]").value = ""; }
      }
    }
  }
  for (const g of groups) {
    if (g.status === "locked") continue;
    const section = sections.get(g.group_id), custom = section.querySelector("[data-custom]");
    section.querySelectorAll("input").forEach(input => input.addEventListener("change", () => {
      if (input.checked) {
        if (input.dataset.delegate === "true") section.querySelectorAll("input").forEach(other => { if (other !== input) other.checked = false; });
        else section.querySelectorAll('[data-delegate="true"]').forEach(other => { other.checked = false; });
        if (g.selection_mode === "single" || input.dataset.delegate === "true") custom.value = "";
      }
      dependencies();
    }));
    custom.addEventListener("input", () => {
      if (custom.value.trim()) section.querySelectorAll("input").forEach(el => { if (g.selection_mode === "single" || el.dataset.delegate === "true") el.checked = false; });
      dependencies();
    });
  }
  for (const saved of job.choice_restore?.selections || []) {
    const section = sections.get(saved.group_id);
    if (!section || !section.querySelector("[data-custom]")) continue;
    section.querySelectorAll("input").forEach(input => { input.checked = saved.option_ids.includes(input.value); });
    section.querySelector("[data-custom]").value = saved.custom_text || "";
  }
  for (const change of job.choice_restore?.explicit_changes || []) {
    const el = [...form.querySelectorAll("[data-change-atom]")].find(el => el.dataset.changeAtom === change.atom_id);
    if (el) { el.querySelector("textarea").value = change.replacement_text; el.querySelector("input").checked = true; }
  }
  dependencies();
  const idempotencyKey = crypto.randomUUID();
  form.addEventListener("submit", async event => {
    event.preventDefault();
    const picked = selections();
    const problem = choiceProblem(groups, picked);
    if (problem) { box.querySelector("#choice-error").textContent = problem; return; }
    const explicit_changes = [];
    for (const el of form.querySelectorAll("[data-change-atom]")) {
      if (el.querySelector("input").checked) {
        const replacement_text = el.querySelector("textarea").value;
        if (!replacement_text.trim()) { box.querySelector("#choice-error").textContent = "Cần nhập ý thay thế cho phần đã xác nhận."; return; }
        explicit_changes.push({atom_id: el.dataset.changeAtom, replacement_text, confirmed: "yes"});
      }
    }
    const payload = {revision: job.revision, form_id: checklist.form_id, idempotency_key: idempotencyKey, selections: picked, explicit_changes};
    const button = form.querySelector('button[type="submit"]'); button.disabled = true;
    try {
      await api(`/requests/${job.request_id}/selections`, {method: "POST", body: JSON.stringify(payload)});
      renderedChecklistKey = null; await refreshJob(); syncPolling();
    } catch (error) { box.querySelector("#choice-error").textContent = error.message; button.disabled = false; }
  });
}

function renderRevisionControl(job) {
  const box = $("#revision-control");
  if (!box) return;
  box.hidden = job.workflow_version !== 2 || !job.checklist || !["awaiting_image", "complete", "cards_only", "needs_evidence", "needs_resolution", "failed"].includes(job.status);
  if (box.hidden) return;
  box.innerHTML = '<button type="button" class="button button-quiet" data-reuse="true">Điều chỉnh lựa chọn</button><button type="button" class="button button-quiet" data-reuse="false">Gợi ý lựa chọn khác</button>';
  box.querySelectorAll("button").forEach(button => button.addEventListener("click", async event => {
    event.currentTarget.disabled = true;
    try { await api(`/requests/${job.request_id}/revise`, {method: "POST", body: JSON.stringify({revision: job.revision, reuse_checklist: button.dataset.reuse === "true"})}); renderedChecklistKey = null; await refreshJob(); syncPolling(); }
    catch (error) { showRequestError(error); event.currentTarget.disabled = false; }
  }));
}

loadHealth();
if (activeId) {
  $("#submit-request").disabled = true;
  refreshJob().then(() => {
    if (activeJob && !terminal.has(activeJob.status) && !waiting.has(activeJob.status)) syncPolling();
    updateSubmitState();
  });
}
