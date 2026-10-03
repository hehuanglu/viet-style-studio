/* Annotation layer stays separate from the clean image, at native coordinates. */
async function readArenaImageFile(file) {
  if (!file || !["image/png", "image/jpeg", "image/webp"].includes(file.type) || !file.size || file.size > 10 * 1024 * 1024) {
    throw new Error("Dùng ảnh PNG, JPG hoặc WebP, tối đa 10 MiB.");
  }
  const url = URL.createObjectURL(file);
  const img = new Image();
  try {
    img.src = url;
    await img.decode();
    if (img.naturalWidth * img.naturalHeight > 25000000) throw new Error("Ảnh vượt 25 triệu điểm ảnh.");
    const data = await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(reader.result.split(",")[1]);
      reader.onerror = () => reject(new Error("Không đọc được ảnh."));
      reader.readAsDataURL(file);
    });
    return {image: {mime_type: file.type, data}, filename: file.name || "Ảnh dán từ Gemini", width: img.naturalWidth, height: img.naturalHeight};
  } finally { URL.revokeObjectURL(url); }
}

async function arenaImageFromClipboard() {
  if (!navigator.clipboard?.read) throw new Error("Dán ảnh bằng Ctrl+V / ⌘V hoặc chọn tệp ảnh.");
  for (const item of await navigator.clipboard.read()) {
    const type = item.types.find(type => ["image/png", "image/jpeg", "image/webp"].includes(type));
    if (type) return new File([await item.getType(type)], "Ảnh dán từ Gemini", {type});
  }
  throw new Error("Clipboard chưa có ảnh. Hãy copy ảnh trên Gemini, rồi dán bằng Ctrl+V / ⌘V.");
}

function paintArenaStrokes(canvas, strokes, current = null) {
  const ctx = canvas.getContext("2d");
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  for (const stroke of [...strokes, ...(current ? [current] : [])]) {
    ctx.save();
    ctx.globalCompositeOperation = stroke.tool === "eraser" ? "destination-out" : "source-over";
    ctx.strokeStyle = stroke.tool === "region" ? "#e53935" : stroke.color;
    ctx.fillStyle = ctx.strokeStyle;
    ctx.lineWidth = stroke.width * Math.min(canvas.width, canvas.height);
    ctx.lineCap = ctx.lineJoin = "round";
    const points = stroke.points.map(([x, y]) => [x * canvas.width, y * canvas.height]);
    if (points.length === 1) {
      ctx.beginPath(); ctx.arc(points[0][0], points[0][1], ctx.lineWidth / 2, 0, Math.PI * 2); ctx.fill();
    } else {
      ctx.beginPath(); ctx.moveTo(...points[0]);
      points.slice(1).forEach(point => ctx.lineTo(...point)); ctx.stroke();
    }
    ctx.restore();
  }
}

class ArenaImageEditor {
  constructor() {
    this.dialog = document.createElement("dialog");
    this.dialog.className = "image-editor";
    this.dialog.setAttribute("aria-labelledby", "editor-title");
    this.dialog.innerHTML = `<div class="editor-heading"><div><h2 id="editor-title">Phác thảo chỉnh sửa</h2><p>Khoanh nơi cần sửa hoặc vẽ hình dạng mong muốn, rồi gửi hai ảnh và prompt cho Gemini.</p></div><button type="button" class="button button-quiet" data-close aria-label="Đóng trình chỉnh sửa">Đóng</button></div>
      <div class="editor-layout"><div class="editor-drawing"><div class="editor-tools" role="toolbar" aria-label="Công cụ vẽ">
        <button type="button" class="button button-quiet" data-tool="region" aria-pressed="true">Khoanh vùng</button>
        <button type="button" class="button button-quiet" data-tool="sketch" aria-pressed="false">Phác thảo</button>
        <button type="button" class="button button-quiet" data-tool="eraser" aria-pressed="false">Tẩy nét</button>
        <label>Màu phác <input type="color" data-color value="#2060df" /></label><label>Cỡ cọ <input type="range" data-width min="2" max="36" value="6" /></label>
        <button type="button" class="button button-quiet" data-undo>Hoàn tác</button><button type="button" class="button button-quiet" data-redo>Làm lại</button>
        <label>Zoom <select data-zoom><option value="fit">Vừa khung</option><option value="1">100%</option><option value="1.5">150%</option><option value="2">200%</option></select></label>
      </div><p class="muted editor-legend">Đỏ: chỉ vùng cần sửa · Màu phác: hình dạng/vị trí mong muốn · Tẩy chỉ xóa nét vẽ.</p>
      <div class="editor-viewport"><div class="editor-stage"><img alt="Ảnh gốc để phác thảo" draggable="false" /><canvas aria-label="Vẽ hướng dẫn sửa ảnh" tabindex="0"></canvas></div></div></div>
      <div class="editor-instructions"><label for="edit-instruction">Bạn muốn sửa gì?</label><textarea id="edit-instruction" rows="4" maxlength="6000" placeholder="Ví dụ: đổi cổ áo theo nét xanh; bỏ vòng cổ trong vùng đỏ…"></textarea>
        <label for="edit-keep">Chi tiết cần giữ thêm (tùy chọn)</label><textarea id="edit-keep" rows="2" maxlength="6000" placeholder="Ví dụ: giữ khuôn mặt, nền và màu áo."></textarea>
        <button type="button" class="button button-accent" data-prepare>Chuẩn bị ảnh và prompt</button>
        <div data-packet hidden><p class="muted">Đính kèm ảnh gốc trước, ảnh phác thảo sau, rồi dán prompt vào Gemini.</p><div class="editor-packet-actions">
          <button type="button" class="button button-quiet" data-original>Tải ảnh gốc</button><button type="button" class="button button-quiet" data-guide>Tải ảnh phác thảo</button>
          <button type="button" class="button button-dark" data-copy>Copy prompt sửa</button><a class="button button-quiet" href="https://gemini.google.com/" target="_blank" rel="noreferrer">Mở Gemini ↗</a>
        </div><details><summary>Xem / sửa prompt</summary><textarea data-prompt rows="9" maxlength="30000" aria-label="Prompt sửa ảnh"></textarea></details>
        <div class="editor-return"><strong>Nhận ảnh hoàn thiện</strong><p class="muted">Dán ảnh Gemini trả về. Ảnh mới được cập nhật ngay.</p><button type="button" class="button button-accent" data-paste-result>Dán ảnh hoàn thiện</button>
          <label class="button button-quiet upload-button" for="editor-result-file">Chọn ảnh hoàn thiện</label><input id="editor-result-file" type="file" class="visually-hidden" accept="image/png,image/jpeg,image/webp" />
          <button type="button" class="button button-quiet" data-retry hidden>Gửi lại ảnh hoàn thiện</button>
        </div></div><p data-message role="status" aria-live="polite"></p>
      </div></div>`;
    document.body.appendChild(this.dialog);
    const q = selector => this.dialog.querySelector(selector);
    this.q = q;
    this.canvas = q("canvas"); this.stage = q(".editor-stage");
    this.strokes = []; this.redo = []; this.current = null; this.busy = false;
    q("[data-close]").addEventListener("click", () => this.close());
    this.dialog.addEventListener("cancel", event => { if (this.busy) event.preventDefault(); else this.close(); });
    q("[data-zoom]").addEventListener("change", () => this.resize());
    this.observer = new ResizeObserver(() => { if (this.dialog.open) this.resize(); });
    this.observer.observe(q(".editor-viewport"));
    this.dialog.querySelectorAll("[data-tool]").forEach(button => button.addEventListener("click", () => {
      this.tool = button.dataset.tool;
      this.dialog.querySelectorAll("[data-tool]").forEach(el => el.setAttribute("aria-pressed", String(el === button)));
      q("[data-color]").disabled = this.tool !== "sketch";
    }));
    q("[data-undo]").addEventListener("click", () => { if (this.strokes.length) { this.redo.push(this.strokes.pop()); this.changed(); } });
    q("[data-redo]").addEventListener("click", () => { if (this.redo.length) { this.strokes.push(this.redo.pop()); this.changed(); } });
    this.canvas.addEventListener("pointerdown", event => this.startStroke(event));
    this.canvas.addEventListener("pointermove", event => this.moveStroke(event));
    this.canvas.addEventListener("pointerup", event => this.endStroke(event));
    this.canvas.addEventListener("pointercancel", event => this.endStroke(event));
    this.canvas.addEventListener("lostpointercapture", event => this.endStroke(event));
    [q("#edit-instruction"), q("#edit-keep")].forEach(el => el.addEventListener("input", () => this.invalidate()));
    q("[data-prepare]").addEventListener("click", () => this.prepare());
    q("[data-original]").addEventListener("click", () => this.download(this.source.image, "01-anh-goc", this.packet.original_url));
    q("[data-guide]").addEventListener("click", () => this.download(this.packet.guide, "02-anh-phac-thao", this.packet.guide_url));
    q("[data-copy]").addEventListener("click", async () => {
      try { await copyPrompt(q("[data-prompt]").value, q("[data-prompt]")); this.message("Đã copy prompt. Đính kèm hai ảnh theo đúng thứ tự."); }
      catch (_) { q("[data-packet] details").open = true; q("[data-prompt]").focus(); q("[data-prompt]").select(); this.message("Dùng Ctrl+C / ⌘C để copy prompt."); }
    });
    q("[data-paste-result]").addEventListener("click", async () => {
      try { await this.receive(await arenaImageFromClipboard()); } catch (error) { this.message(error.message, true); }
    });
    q("#editor-result-file").addEventListener("change", event => this.receive(event.target.files[0]));
    q("[data-retry]").addEventListener("click", () => this.commit());
    this.dialog.addEventListener("paste", event => {
      const file = [...(event.clipboardData?.items || [])].find(item => item.kind === "file" && item.type.startsWith("image/"))?.getAsFile();
      if (file && this.packet && !this.busy) { event.preventDefault(); this.receive(file); }
    });
  }

  async open(source) {
    if (this.busy) return;
    this.source = source; this.strokes = []; this.redo = []; this.current = null; this.packet = null; this.result = null;
    this.tool = "region";
    this.dialog.querySelectorAll("[data-tool]").forEach(el => el.setAttribute("aria-pressed", String(el.dataset.tool === "region")));
    this.q("[data-color]").disabled = true;
    this.q("[data-zoom]").value = "fit";
    this.q("#edit-instruction").value = ""; this.q("#edit-keep").value = "";
    this.q("[data-packet]").hidden = true; this.q("[data-retry]").hidden = true;
    this.q("#editor-result-file").value = "";
    this.message("Đang mở ảnh…");
    const img = this.q(".editor-stage img");
    img.src = `data:${source.image.mime_type};base64,${source.image.data}`;
    await img.decode();
    this.canvas.width = img.naturalWidth; this.canvas.height = img.naturalHeight;
    this.dialog.showModal(); this.resize(); this.changed(); this.message("");
    this.q("#edit-instruction").focus();
  }

  close() {
    if (this.busy) return;
    if (this.current) this.endStroke({pointerId: this.pointerId});
    this.dialog.close(); this.packet = null; this.result = null;
    this.strokes = []; this.redo = []; this.canvas.width = this.canvas.height = 1;
    this.q(".editor-stage img").removeAttribute("src");
    this.source = null;
  }

  message(text, error = false) {
    this.q("[data-message]").textContent = text;
    this.q("[data-message]").classList.toggle("error", error);
  }

  resize() {
    const zoom = this.q("[data-zoom]").value;
    const viewport = this.q(".editor-viewport");
    const width = zoom === "fit" ? Math.min(this.canvas.width, Math.max(1, viewport.clientWidth - 24), Math.max(1, viewport.clientHeight - 24) * this.canvas.width / this.canvas.height) : this.canvas.width * Number(zoom);
    this.stage.style.width = `${width}px`; this.stage.style.height = `${width * this.canvas.height / this.canvas.width}px`;
  }

  point(event) {
    const rect = this.canvas.getBoundingClientRect();
    return [Math.max(0, Math.min(1, (event.clientX - rect.left) / rect.width)), Math.max(0, Math.min(1, (event.clientY - rect.top) / rect.height))];
  }

  startStroke(event) {
    if (this.busy || this.current || event.button !== 0) return;
    if (this.strokes.length >= 500) return this.message("Tối đa 500 nét vẽ. Hoàn tác để giảm số nét.", true);
    if (this.strokes.reduce((n, s) => n + s.points.length, 0) >= 29999) return this.message("Nét vẽ quá dài. Hoàn tác để giảm số nét.", true);
    event.preventDefault(); this.pointerId = event.pointerId;
    this.canvas.setPointerCapture(event.pointerId);
    const rect = this.canvas.getBoundingClientRect();
    this.current = {tool: this.tool, color: this.tool === "region" ? "#e53935" : this.q("[data-color]").value, width: Number(this.q("[data-width]").value) / Math.min(rect.width, rect.height), points: [this.point(event)]};
    this.current.width = Math.min(.2, this.current.width);
    this.invalidate(); this.redo = []; this.paint();
  }

  moveStroke(event) {
    if (!this.current || event.pointerId !== this.pointerId) return;
    if (this.strokes.reduce((n, s) => n + s.points.length, 0) + this.current.points.length >= 30000) return;
    this.current.points.push(this.point(event)); this.paint();
  }

  endStroke(event) {
    if (!this.current || event.pointerId !== this.pointerId) return;
    this.strokes.push(this.current); this.current = null;
    if (this.canvas.hasPointerCapture(event.pointerId)) this.canvas.releasePointerCapture(event.pointerId);
    this.changed();
  }

  paint() { paintArenaStrokes(this.canvas, this.strokes, this.current); }
  changed() {
    this.invalidate(); this.paint();
    this.q("[data-undo]").disabled = !this.strokes.length;
    this.q("[data-redo]").disabled = !this.redo.length;
  }
  invalidate() {
    this.packet = null; this.result = null;
    this.q("[data-packet]").hidden = true; this.q("[data-retry]").hidden = true;
  }

  async prepare() {
    const instruction = this.q("#edit-instruction").value.trim();
    if (!instruction) { this.q("#edit-instruction").focus(); return this.message("Nhập điều bạn muốn sửa; không cần vẽ nếu yêu cầu đã rõ.", true); }
    this.setBusy(true); this.message("Đang chuẩn bị prompt và ảnh phác thảo…");
    try {
      const description = {instruction, keep: this.q("#edit-keep").value.trim(), strokes: this.strokes};
      const composite = document.createElement("canvas"); composite.width = this.canvas.width; composite.height = this.canvas.height;
      const ctx = composite.getContext("2d"); ctx.drawImage(this.q(".editor-stage img"), 0, 0); ctx.drawImage(this.canvas, 0, 0);
      const blob = await new Promise(resolve => composite.toBlob(resolve, "image/png"));
      if (!blob) throw new Error("Không xuất được ảnh phác thảo.");
      const guide = await readArenaImageFile(new File([blob], "02-anh-phac-thao.png", {type: "image/png"}));
      const assets = await api(`/requests/${this.source.job.request_id}/image-edit-prompt`, {method: "POST", body: JSON.stringify({candidate_id: this.source.candidateId, ...description, original: this.source.image, guide: guide.image})});
      const {prompt} = assets;
      this.packet = {...description, ...assets, strokes: structuredClone(this.strokes), prompt, guide: guide.image, original: this.source.image};
      this.q("[data-prompt]").value = prompt; this.q("[data-packet]").hidden = false;
      this.message("Bộ ảnh và prompt đã sẵn sàng. Tải hai ảnh để đính kèm vào Gemini.");
    } catch (error) { this.message(error.message, true); }
    finally { this.setBusy(false); }
  }

  setBusy(busy) {
    this.busy = busy;
    this.dialog.querySelectorAll("button,input,textarea,select").forEach(el => { el.disabled = busy; });
    if (!busy) {
      this.q("[data-undo]").disabled = !this.strokes.length;
      this.q("[data-redo]").disabled = !this.redo.length;
      this.q("[data-color]").disabled = this.tool !== "sketch";
    }
  }

  download(image, name, assetUrl = null) {
    const extension = {"image/png": "png", "image/jpeg": "jpg", "image/webp": "webp"}[image.mime_type];
    const url = assetUrl || URL.createObjectURL(new Blob([Uint8Array.from(atob(image.data), c => c.charCodeAt(0))], {type: image.mime_type}));
    const link = document.createElement("a"); link.href = url; link.download = `${name}.${extension}`;
    document.body.appendChild(link); link.click(); link.remove();
    if (!assetUrl) setTimeout(() => URL.revokeObjectURL(url), 1000);
  }

  async receive(file) {
    if (!file || this.busy || !this.packet) return;
    this.setBusy(true);
    try {
      this.result = await readArenaImageFile(file);
      this.packet.prompt = this.q("[data-prompt]").value;
      if (!this.packet.prompt.trim()) throw new Error("Prompt sửa không được để trống.");
    } catch (error) { this.result = null; this.message(error.message, true); }
    finally { this.setBusy(false); }
    if (this.result) await this.commit();
  }

  async commit() {
    if (!this.result || !this.packet || this.busy) return;
    this.setBusy(true); this.message("Đang cập nhật ảnh hoàn thiện…");
    try {
      await this.source.onComplete(this.result, this.packet);
      this.setBusy(false); this.close();
    } catch (error) { this.message(error.message, true); this.q("[data-retry]").hidden = false; }
    finally { this.setBusy(false); }
  }
}
