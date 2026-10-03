# Phạm vi sáng tạo và provenance — v2

## Semantic scope

Domains/atoms/design_sections là cấu trúc mở, không fixed ontology. Giữ base garment và intent: âu phục lai nét Việt, váy hiện đại, áo ngũ thân hoặc silhouette mới; không remap mọi request sang áo dài/váy. Domain count và wording tùy semantic content, không cam kết cùng checklist cho mọi input.

Atom phân biệt must/avoid, preference, example, delegated và context. Một atom có thể liên quan nhiều domain mà không duplicate thành constraints. Source refs trỏ turn/quote nguyên văn; explicit changes cần user confirmation và supersedes binding. Không infer gender/age/body type từ occasion; presentation model không là user-provided identity.

## Creative boundary

Explore chỉ tác động hướng khám phá/scoring profile, không cho đổi locked decisions. Neutral/inspired/historical là intent riêng; không tự downgrade historical để vượt evidence requirement. Reference về silhouette/technique không tự support historical provenance. Không gán verified status chỉ vì source ID tồn tại hoặc Gemini đưa URL.

Selection severe conflict: cùng detail/location/layer có yêu cầu trực tiếp không thể đồng thời thực hiện. VP02C API review, backend validate shape/provenance; unfamiliar combinations/contrast/layering không blocker mặc định. Raw examples không bị convert thành bắt buộc dùng tất cả motifs/accessories.

## Presentation policy hiện hành

Optional presentation group: min0/max1, ≥5 concrete styles + delegation/custom; style không thay garment/context constraints. Single-model two-view presentation: một identity/garment, front view trái/back view phải trong cùng frame, consistent scale/material/accessories; không third view/crowd/additional design. Chưa có backend image person-count/layout detection hoặc live acceptance cho template này.

## Evaluation boundary

VP05/06/07 API audits và VP08 API aggregation không độc lập về provider/model; không tương đương expert sign-off. Backend VP04–VP08 không output schema/semantic validation hoặc score recomputation/eligibility/dedupe. Ranking dựa proposed_total của Gemini; không chứng minh garment manufacturability/historical accuracy. P06 image output validation/acceptance vẫn riêng. Background audit mode cho output/editing tiếp tục dù fail/unavailable, phải phân biệt checked với displayed artifact.
