"""User report is derived from persisted facts, never from model instructions."""

PURPOSES = {"P02": "Hiểu và chuẩn hóa yêu cầu", "P03": "Đề xuất phương án", "P04": "Audit phương án",
            "P10": "Kiểm tra và bổ sung thông tin đã nhận diện",
            "P08": "Sửa phương án", "P09": "Viết prompt tạo ảnh bằng API", "P06": "Audit ảnh", "image": "Tạo ảnh", "image_repair": "Sửa ảnh"}
GATES = {"visible_user_constraints": "Yêu cầu và ràng buộc nhìn thấy", "visible_invariants": "Chi tiết cần giữ",
         "major_visual_defects": "Lỗi tạo hình lớn", "edit_preservation": "Giữ phần không cần sửa so với ảnh gốc",
         "user_constraints": "Ràng buộc người dùng", "applicable_cultural_rules": "Quy tắc có căn cứ",
         "claim_support": "Căn cứ của lời giải thích", "historical_scope": "Phạm vi lịch sử", "renderability": "Khả năng thể hiện thành ảnh"}
STATUSES = {"pass": "Đạt", "fail": "Chưa đạt", "uncertain": "Chưa xác định", "not_applicable": "Không áp dụng"}
DIMENSIONS = {"need_fit": "phù hợp nhu cầu", "usability": "dễ sử dụng", "aesthetics": "thẩm mỹ", "originality": "ý tưởng riêng", "grounded_explanation": "giải thích có căn cứ"}
FIELDS = {"subject": "Đối tượng", "palette": "Màu sắc", "accessories": "Phụ kiện", "scene": "Bối cảnh", "composition": "Bố cục", "bottom_garment": "Trang phục thân dưới", "accessory_count": "Số phụ kiện", "palette_count": "Số màu", "subject_description": "Mô tả chủ thể", "occasion": "Dịp sử dụng", "style": "Phong cách", "goal": "Mục tiêu"}
FIELDS.update(event="Dịp sử dụng", period="Thời kỳ", region="Vùng", subject_scope="Phạm vi đối tượng")
FIELDS.update(base_garment="Form dáng nền", design_intent="Ý định cách tân", motifs="Họa tiết gợi ý", motif_policy="Cách chọn họa tiết")
VALUES = {"create_look": "tạo cách phối", "explore": "khám phá lựa chọn", "ao_dai": "áo dài", "ao_tu_than": "áo tứ thân", "ao_ngu_than": "áo ngũ thân", "inspired": "lấy cảm hứng", "historical": "theo phạm vi lịch sử"}
VALUES["au_phuc"] = "âu phục"
VALUES.update(ao_va_chan_vay="áo phối chân váy", vay_lien="váy liền thân")
OPERATORS = {"include": "phải có", "exclude": "không có", "equals": "là", "preserve": "giữ", "at_most": "tối đa", "at_least": "tối thiểu"}
OUTCOMES = {"complete": "Hoàn tất", "cards_only": "Chỉ có thẻ đề xuất; chưa có ảnh đạt",
            "cancelled": "Đã hủy", "failed": "Bị lỗi", "needs_evidence": "Thiếu căn cứ để tiếp tục",
            "needs_resolution": "Yêu cầu chưa được giải quyết", "awaiting_image": "Đang chờ ảnh tạo",
            "awaiting_image_repair": "Đang chờ ảnh sửa", "awaiting_manual_audit": "Đang chờ kết quả audit thủ công",
            "awaiting_audit_choice": "Audit API chưa khả dụng; chờ chọn audit thủ công", "image_checking": "Đang audit ảnh"}


def user_report(job, policy):
    brief = job.get("brief") or {}
    metrics = job["metrics"]
    steps, calls = [], []
    totals = {"success": 0, "failed": 0, "cache": 0, "interrupted": 0, "mock": 0}
    saved_steps = job.get("workflow_steps") or [{"kind": "provider", "trace": t} for t in job.get("trace", [])]
    for step in saved_steps:
        if step["kind"] != "provider":
            steps.append({"via": "Người dùng thao tác trên Gemini" if step["kind"] == "manual" else "Ứng dụng", "purpose": step["purpose"], "detail": step.get("detail", "")})
            continue
        trace = step["trace"]
        purpose = PURPOSES.get(trace["task"], "Xử lý yêu cầu")
        provider = trace.get("provider", job["provider"])
        called = trace.get("provider_called", bool(trace.get("provider_call_id")))
        if trace.get("checkpoint_hit"):
            steps.append({"via": "Ứng dụng", "purpose": purpose, "detail": "Tiếp tục từ kết quả đã lưu"})
            continue
        if trace.get("cache_hit"):
            result, count = "Dùng kết quả đã lưu, không gọi lại API", 0
            if provider == "gemini":
                totals["cache"] += 1
        elif trace.get("interrupted"):
            result, count = "Bị ngắt trước khi nhận được kết quả", int(bool(called))
            if provider == "gemini":
                totals["interrupted"] += count
        else:
            count = int(bool(called))
            result = "Thất bại hoặc phản hồi không hợp lệ" if trace.get("error_code") else "Thành công"
            if provider == "gemini":
                totals["failed" if trace.get("error_code") else "success"] += count
            else:
                totals["mock"] += count
            if count == 0:
                result = "Không gọi dịch vụ: " + result
        model = trace.get("model", job["manifest"]["image_model" if trace["task"] in ("image", "image_repair") else "text_model"])
        row = {"purpose": purpose, "provider": "Gemini" if provider == "gemini" else "Mock", "model": model, "calls": count if provider == "gemini" else 0, "result": result}
        calls.append(row)
        steps.append({"via": "API Gemini" if provider == "gemini" and count else "Ứng dụng", "purpose": purpose,
                      "detail": ("Mô phỏng kiểm tra luồng; " if provider == "mock" else "") + result + " · " + row["model"]})
    totals["actual"] = totals["success"] + totals["failed"] + totals["interrupted"]
    constraints = [f"{FIELDS.get(c['field'], c['field'])}: {OPERATORS.get(c['operator'], c['operator'])} {c['value']}" for c in brief.get("hard_constraints", [])]
    agreed = [f"{label}: {VALUES.get(brief[field]['value'], brief[field]['value'])}" for field, label in (("subject", "Đối tượng"), ("goal", "Mục tiêu")) if brief.get(field, {}).get("value")]
    agreed += [f"{FIELDS.get(p['field'], p['field'])}: {p['value']}" for p in brief.get("context", []) + brief.get("preferences", []) if p.get("value")]
    if brief.get("mode"):
        agreed.append("Hướng thực hiện: " + {"inspired": "lấy cảm hứng", "historical": "tái hiện trong phạm vi có căn cứ", "unresolved": "chưa chốt"}.get(brief["mode"], brief["mode"]))
    all_candidates = job.get("proposed_candidates", [])
    ranking = job.get("ranking") or {}
    targets = job.get("image_target_ids", [])
    selected = next((card for card in job.get("cards", []) if card["candidate_id"] in targets), None) or (job["cards"][0] if job.get("cards") else None)
    image_count = len(targets) or len(job.get("image_prompts", [])) or 1
    rejected = {r["candidate_id"]: r for r in ranking.get("rejected", [])}
    candidates = []
    for candidate in all_candidates:
        reason = "Qua các điều bắt buộc và được xếp hạng theo policy"
        rejection = rejected.get(candidate["candidate_id"])
        if rejection:
            if rejection["hard_findings"]:
                reason = "; ".join(f["reason"] for f in rejection["hard_findings"])
            elif rejection.get("reason") == "insufficient_diversity":
                reason = "Quá giống phương án đã giữ"
            elif rejection["floor_failures"]:
                reason = "Điểm chưa đủ ở: " + ", ".join(DIMENSIONS.get(d, d) for d in rejection["floor_failures"])
            else:
                reason = "Tổng điểm chưa đủ ngưỡng"
        candidates.append({"title": candidate["title"], "description": candidate["design"]["subject_description"], "reason": reason})
    audits = []
    candidate_audits = []
    for history in job.get("candidate_audit_history", []):
        for audit in history["audit"]["audits"]:
            candidate = next(c for c in history["candidates"] if c["candidate_id"] == audit["candidate_id"])
            candidate_audits.append({"title": candidate["title"], "is_repair": history["is_repair"],
                                     "findings": [f"{GATES.get(f['gate_id'], f['gate_id'])}: {STATUSES[f['status']]}. {f['reason']}" for f in audit["gate_findings"]]})
    for batch in job.get("image_audits", []):
        audit = batch["audits"][0]
        artifact = next(a for a in job["artifacts"] if a["artifact_id"] == audit["artifact_id"])
        origin = {"api": "API Gemini", "gemini_manual": "Người dùng chuyển kết quả từ Gemini", "mock": "Mock, chỉ kiểm tra luồng"}.get(artifact.get("audit_origin"), "Chưa audit")
        audits.append({"image": ("Ảnh sửa" if artifact["parent_artifact_id"] else "Ảnh tạo") + " · " + next((c["title"] for c in job["cards"] if c["candidate_id"] == artifact["candidate_id"]), artifact["candidate_id"]), "via": origin,
                       "quality": f"Chất lượng {audit['visual_quality']}/4: {audit['quality_reason']}",
                       "findings": [f"{GATES.get(f['gate_id'], f['gate_id'])}: {STATUSES[f['status']]}. {f['evidence']} — {f['reason']}" for f in audit["findings"]],
                       "fixes": [f["minimal_fix"] for f in audit["findings"] if f["status"] in ("fail", "uncertain") and f["minimal_fix"]]})
    final = OUTCOMES.get(job["status"], "Ứng dụng đang xử lý")
    final_artifact = next((a for a in job["artifacts"] if a["artifact_id"] == job.get("selected_artifact_id")), None)
    if final_artifact:
        count = len(job.get("selected_artifact_ids", [final_artifact["artifact_id"]]))
        total = image_count
        final = f"Có {count}/{total} phương án có ảnh qua audit" if final_artifact["check_status"] == "passed" else f"Có {count}/{total} phương án có ảnh đã kiểm tra luồng bằng mock; chưa kiểm tra chất lượng ảnh thật"
    elif job["status"] == "complete" and job["cards"]:
        final = "Hoàn tất thẻ đề xuất; không yêu cầu tạo ảnh"
    current_ids = job.get("output_artifact_ids")
    if current_ids:
        current_images = [a for a in job["artifacts"] if a["artifact_id"] in current_ids]
        final_artifact = current_images[0]
        checked = sum(a["check_status"] == "passed" for a in current_images)
        final = f"Đã nhận ảnh cho {len(current_images)}/{image_count} phương án; {checked} ảnh qua kiểm tra thị giác. Ảnh hoàn thiện được cập nhật ngay."
    selection_reason = "Ứng dụng chọn phương án đã qua các điều bắt buộc, theo điểm có trọng số và ưu tiên phù hợp nhu cầu, dễ sử dụng khi điểm gần nhau."
    if targets:
        selection_reason = "Người dùng chọn phương án này để tạo và chỉnh sửa ảnh."
    return {"inputs": {"initial": job["turns"][0]["text"], "answers": [t["text"] for t in job["turns"][1:]],
                       "images": [{"name": a.get("filename", "Ảnh mock" if a["output_origin"] == "mock" else "Ảnh API"), "source": {"gemini": "API Gemini", "mock": "Mock"}.get(a["output_origin"], a["output_origin"]), "role": "Ảnh sửa" if a["parent_artifact_id"] else "Ảnh tạo"} for a in job["artifacts"]],
                       "manual_audits": [f"{a['image']}: {a['quality']}. " + "; ".join(a["findings"]) for a in audits if a["via"] == "Người dùng chuyển kết quả từ Gemini"]},
            "agreed": agreed + constraints, "assumptions": brief.get("assumptions", []),
            "candidates": candidates, "selected": selected["title"] if selected else None, "selection_reason": selection_reason if selected else "Chưa chọn được phương án",
            "steps": steps, "api": {"totals": totals, "calls": calls},
            "manual": {"image_prompts": metrics.get("manual_image_prompts", 0), "images_received": metrics.get("manual_images_received", 0), "audit_prompts": metrics.get("manual_audit_prompts", 0), "audits_received": metrics.get("manual_audits_received", 0)},
            "audits": audits, "candidate_audits": candidate_audits, "repairs": [{"fixes": [f.get("fix") or f.get("reason") for f in h["findings"]], "quality": h.get("quality_reason", "")} for h in job.get("repair_history", []) if h["kind"] == "image"],
            "final": final, "selected_image_url": final_artifact["url"] if final_artifact else None,
            "limits": ["Có thể tiếp tục phác thảo và gửi ảnh hoàn thiện nhiều lượt; không có bước so sánh hay chọn giữ. Kiểm tra API vẫn dùng ngân sách còn lại của request." if job.get("audit_mode") == "background" or current_ids else str(len(job.get("image_prompts", [])) or 1) + " prompt, mỗi phương án một ảnh; tối đa một vòng sửa ảnh tự động trong request; đã dùng " + str(job.get("repair_counts", {}).get("image", 0)) + " lượt sửa.",
                       "Audit là kết quả hỗ trợ, chưa thay thế đánh giá của chuyên gia.",
                       *job.get("warnings", []), *([job["error"]["message"]] if job.get("error") else [])]}
