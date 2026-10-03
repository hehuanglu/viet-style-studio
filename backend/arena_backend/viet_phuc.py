"""Open content contracts, deterministic gates and scoring for Việt phục v2.

These checks establish structural integrity and provenance, not cultural truth.
"""
import copy
import re
from pathlib import Path
from urllib.parse import urlsplit

from .core import Contracts, PROJECT, digest, require

DATA = PROJECT / 'backend' / 'viet_phuc'
PROMPT_DIR = PROJECT / 'docs' / 'viet-phuc-v2' / 'prompts'
SCHEMAS = {'VP01': 'CleanPrompt', 'VP02': 'ClarificationChecklist', 'VP02R': 'ReferenceDiscoveryBundle',
           'VP02C': 'SelectionConflictReview', 'VP03': 'ResolvedBrief', 'VP04': 'ImagePromptBatch', 'VP05': 'SpecialistAuditBatch',
           'VP06': 'SpecialistAuditBatch', 'VP07': 'SpecialistAuditBatch', 'VP08': 'HarmonyAuditBatch'}
ROLES = {'VP05': 'fashion', 'VP06': 'culture', 'VP07': 'art'}
CONTENT_FIELDS = ('title', 'image_prompt', 'design_sections', 'fashion_summary', 'art_summary',
                  'culture_summary', 'choices_made', 'claims', 'locked_coverage', 'assumptions', 'limitations')


class VPPrompts:
    def __init__(self, directory=PROMPT_DIR):
        self.system = (directory / 'VP00_SYSTEM.txt').read_text(encoding='utf-8')
        self.templates = {}
        for path in directory.glob('VP*.txt'):
            name = path.name.split('_')[0]
            if name != 'VP00':
                self.templates[name] = path.read_text(encoding='utf-8')
        require(set(self.templates) == set(SCHEMAS), 'Thiếu template VPxx', 'prompt_invalid', 500)
        self.version = digest({'system': self.system, 'templates': self.templates})

    def render(self, name, payload):
        def replace(match):
            import json
            key = match.group(1)
            require(key in payload, 'Thiếu biến prompt: ' + key, 'prompt_invalid', 500)
            return json.dumps(payload[key], ensure_ascii=False)
        return re.sub(r'\{\{([A-Z_]+)\}\}', replace, self.templates[name])


def valid(condition, message):
    require(condition, message, 'semantic_invalid', 502)


def unique(rows, key):
    values = [r[key] for r in rows]
    valid(len(values) == len(set(values)), 'Mã trùng: ' + key)
    return {r[key]: r for r in rows}


def exact_ids(actual, expected, message):
    valid(len(actual) == len(set(actual)) and set(actual) == set(expected), message)


def quote_ref(ref, turns):
    turns = {t['id']: t['text'] for t in turns}
    valid(ref['turn_id'] in turns and ref['quote'] in turns[ref['turn_id']], 'Quote không nguyên văn trong đúng lượt nguồn')
    start = turns[ref['turn_id']].index(ref['quote'])
    return {'turn_id': ref['turn_id'], 'start': start, 'end': start + len(ref['quote'])}


def validate_content(value, turns):
    domains = unique(value['domains'], 'domain_id')
    atoms = unique(value['atoms'], 'atom_id')
    for domain in domains.values():
        valid(set(domain['related_domain_ids']) <= domains.keys(), 'Miền liên quan không tồn tại')
    for atom in atoms.values():
        valid(bool(atom['domain_ids']) and set(atom['domain_ids']) <= domains.keys(), 'Atom thiếu/sai miền')
        for source in atom['source_refs']:
            quote_ref(source, turns)
        valid(not (atom['intent_type'] in ('must', 'avoid') and atom['resolution'] == 'inferred'), 'Không khóa yêu cầu suy diễn')
    return domains, atoms


def retain_atoms(before, after, explicit_changes=()):
    """IDs/intent/provenance stay stable; only explicit user changes retire old atoms."""
    new = {a['atom_id']: a for a in after}
    changed = set(explicit_changes)
    for old in before:
        if old['atom_id'] in changed:
            valid(any(old['atom_id'] in a['supersedes_atom_ids'] for a in after), 'Thay đổi chưa ghi supersedes')
            continue
        valid(old['atom_id'] in new, 'Mất ý đã giữ: ' + old['atom_id'])
        item = new[old['atom_id']]
        valid(item['meaning'] == old['meaning'], 'Đổi nội dung ý đã hiểu chưa có thay đổi rõ ràng')
        valid(item['intent_type'] == old['intent_type'] and item['polarity'] == old['polarity'], 'Đổi loại/quyền chọn của ý gốc')
        valid(all(r in item['source_refs'] for r in old['source_refs']), 'Mất provenance cũ')
    for atom in after:
        valid(set(atom['supersedes_atom_ids']) <= changed, 'Tự thay yêu cầu chưa có thay đổi rõ ràng')


def validate_clean(value, job):
    valid(value['request_id'] == job['request_id'] and value['revision'] == job['revision'], 'Clean sai request/revision')
    _, atoms = validate_content(value, job['turns'])
    covered = set()
    for entry in value['coverage']:
        quote_ref(entry['source_ref'], job['turns'])
        valid(bool(entry['atom_ids']) and set(entry['atom_ids']) <= atoms.keys(), 'Coverage thiếu/sai atom')
        covered.update(entry['atom_ids'])
    valid(set(atoms) <= covered, 'Có atom không được coverage giữ')
    for relation in value['relations']:
        valid(relation['from_atom_id'] in atoms and relation['to_atom_id'] in atoms, 'Relation sai atom')


def safe_url(value):
    if not isinstance(value, str):
        return False
    try:
        url = urlsplit(value)
        return url.scheme in ('http', 'https') and bool(url.hostname) and not url.username and not url.password
    except ValueError:
        return False


def tool_urls(metadata):
    """Only provider response metadata supplies citation IDs; model JSON cannot."""
    records = {}
    for index, chunk in enumerate(metadata.get('groundingMetadata', {}).get('groundingChunks', [])):
        web = chunk.get('web', {})
        if safe_url(web.get('uri')):
            records['gc:' + str(index)] = {'url': web['uri'], 'read': False}
    for index, item in enumerate(metadata.get('urlContextMetadata', {}).get('urlMetadata', [])):
        url = item.get('retrievedUrl')
        if safe_url(url) and item.get('urlRetrievalStatus') == 'URL_RETRIEVAL_STATUS_SUCCESS':
            records['url:' + str(index)] = {'url': url, 'read': True}
    return records


def normalize_references(references, metadata, previous=()):
    refs = copy.deepcopy(references)
    unique(refs, 'reference_id')
    urls = tool_urls(metadata)
    previous = {r['reference_id']: r for r in previous}
    for ref in refs:
        valid(ref['url'] is None or safe_url(ref['url']), 'URL không phải HTTP(S)')
        valid(ref['preview_url'] is None or safe_url(ref['preview_url']), 'Ảnh xem nhanh không phải HTTP(S)')
        if ref['reference_id'] in previous:
            old = previous[ref['reference_id']]
            valid(ref == old, 'VP02 format_only thay nguồn VP02R')
            continue
        matches = [cid for cid, item in urls.items() if item['url'] == ref['url']]
        # No citation means unconfirmed, regardless of the label claimed by Gemini.
        ref['tool_citation_ids'] = matches
        ref['discovery_status'] = 'tool_grounded' if matches else 'not_found' if ref['url'] is None else 'unconfirmed'
        if not matches:
            # The original model output remains in task evidence. Product links
            # come only from provider tool metadata, never an invented URL.
            ref['url'] = None
            ref['supporting_excerpt'] = None
            ref['preview_url'] = None
        elif not any(urls[cid]['read'] for cid in matches):
            # A search citation establishes discovery, not that a page was read.
            ref['supporting_excerpt'] = None
        if matches and ref['preview_url'] not in {item['url'] for item in urls.values()}:
            # Never guess an illustration URL. It must also appear in tool output.
            ref['preview_url'] = None
    return refs


def validate_checklist(value, job, form_id, references):
    valid(value['request_id'] == job['request_id'] and value['revision'] == job['revision'] and value['form_id'] == form_id, 'Checklist sai form/revision')
    validate_clean(value['clean_prompt'], job)
    # VP02 is allowed to correct a misclassified example; provenance remains mandatory.
    old_atoms = {a['atom_id']: a for a in job['clean_prompt']['atoms']}
    new_atoms = {a['atom_id']: a for a in value['clean_prompt']['atoms']}
    valid(set(old_atoms) <= set(new_atoms), 'VP02 bỏ atom trước khi đối chiếu')
    domains = {d['domain_id'] for d in value['clean_prompt']['domains']}
    groups = unique(value['groups'], 'group_id')
    options = unique([o for g in groups.values() for o in g['options']], 'option_id')
    refs = unique(references, 'reference_id')
    for ref in refs.values():
        valid(set(ref['domains']) <= domains, 'Nguồn thuộc miền không tồn tại')
    for group in groups.values():
        valid(bool(group['domain_ids']) and set(group['domain_ids']) <= domains, 'Nhóm sai miền')
        valid(set(group['related_atom_ids']) <= new_atoms.keys(), 'Nhóm sai atom')
        valid(group['status'] == 'locked' or group['allows_custom'], f"Nhóm {group['group_id']} chưa cho nhập ý riêng; nhóm đã hiểu dùng thay đổi yêu cầu riêng")
        valid(0 <= group['min'] <= group['max'] <= 8, 'Giới hạn lựa chọn không hợp lệ')
        valid(group['selection_mode'] != 'single' or group['max'] <= 1, 'Nhóm single không thể chọn nhiều')
        valid(group['status'] != 'needs_choice' or group['min'] >= 1, 'Needs_choice phải có quyết định rõ')
        if group['status'] != 'locked':
            concrete = [o for o in group['options'] if not o['is_ai_delegate']]
            delegates = [o for o in group['options'] if o['is_ai_delegate']]
            valid(5 <= len(concrete) and len(group['options']) <= 8, f"Nhóm {group['group_id']} cần ít nhất 5 gợi ý cụ thể, tối đa 8 options gồm AI")
            valid(len(delegates) == 1, f"Nhóm {group['group_id']} cần đúng một lựa chọn Để AI tự quyết")
            valid(len({o['label'].strip().casefold() for o in concrete}) == len(concrete), 'Gợi ý cụ thể không được trùng nhãn')
        for option in group['options']:
            valid(set(option['reference_ids']) <= refs.keys(), 'Option tham chiếu nguồn không tồn tại')
            valid(set(option['compatible_option_ids'] + option['incompatible_option_ids']) <= options.keys(), 'Option phụ thuộc mã không tồn tại')
            valid(option['option_id'] not in option['incompatible_option_ids'], 'Option tự loại chính nó')
        for dep in group['depends_on']:
            valid(dep['group_id'] in groups and dep['group_id'] != group['group_id'], 'Phụ thuộc nhóm không tồn tại')
            valid(bool(dep['option_ids']) and set(dep['option_ids']) <= {o['option_id'] for o in groups[dep['group_id']]['options']}, 'Sai option phụ thuộc')
    def walk(gid, path):
        valid(gid not in path, 'Vòng phụ thuộc checklist')
        for dep in groups[gid]['depends_on']:
            walk(dep['group_id'], path | {gid})
    for gid in groups:
        walk(gid, set())


def validate_selections(payload, job, contracts):
    contracts.validate('SelectionSubmission', payload)
    require(payload['revision'] == job['revision'], 'revision cũ', 'stale_revision', 409)
    require(payload['form_id'] == job['checklist']['form_id'], 'form cũ', 'stale_form', 409)
    groups = {g['group_id']: g for g in job['checklist']['groups']}
    selections = payload['selections']
    require(len({s['group_id'] for s in selections}) == len(selections), 'Nhóm gửi trùng')
    selected = {s['group_id']: s for s in selections}
    require(set(selected) <= groups.keys(), 'Nhóm không thuộc form')
    all_ids = {oid for s in selections for oid in s['option_ids']}
    for gid, group in groups.items():
        active = all(set(dep['option_ids']) & set(selected.get(dep['group_id'], {}).get('option_ids', [])) for dep in group['depends_on'])
        item = selected.get(gid, {'option_ids': [], 'custom_text': ''})
        ids = item['option_ids']; custom = item['custom_text']
        require(active or not ids and not custom, 'Nhóm phụ không áp dụng cho lựa chọn hiện tại')
        require(group['status'] != 'locked' or not ids and not custom, 'Đã hiểu: dùng thay đổi rõ ràng để sửa')
        options = {o['option_id']: o for o in group['options']}
        require(set(ids) <= options.keys(), 'Option không thuộc nhóm')
        count = len(ids) + int(bool(custom.strip()))
        require(not custom or group['allows_custom'], 'Không cho custom')
        require(not active or group['status'] == 'locked' or count <= group['max'], 'Quá nhiều lựa chọn')
        require(not active or group['status'] != 'needs_choice' or count >= group['min'], 'Cần chọn rõ hoặc giao AI đề xuất')
        delegates = [o for o in ids if options[o]['is_ai_delegate']]
        require(not delegates or len(ids) == 1 and not custom.strip(), 'Không chọn AI cùng lựa chọn/custom khác')
    changes = payload['explicit_changes']
    atoms = {a['atom_id']: a for a in job['clean_prompt']['atoms']}
    require(len({c['atom_id'] for c in changes}) == len(changes), 'Thay đổi atom trùng')
    require(all(c['atom_id'] in atoms and c['confirmed'] == 'yes' for c in changes), 'Thay đổi thiếu xác nhận/atom')
    return copy.deepcopy(payload)


def validate_selection_review(value, job):
    """Validate provenance/shape, leaving design compatibility to the API."""
    valid(value['request_id'] == job['request_id'] and value['revision'] == job['revision'], 'Review sai request/revision')
    valid(value['form_id'] == job['checklist']['form_id'], 'Review sai form')
    selected = {s['group_id']: s for s in job['choices']['selections']}
    atoms = {a['atom_id']: a for a in job['clean_prompt']['atoms']}
    changed = {c['atom_id'] for c in job['choices']['explicit_changes']}
    unique(value['conflicts'], 'conflict_id')
    for conflict in value['conflicts']:
        valid(len(conflict['evidence']) >= 2, 'Conflict cần ít nhất hai yêu cầu đối nghịch')
        for evidence in conflict['evidence']:
            if evidence['kind'] == 'option':
                valid(evidence['option_id'] in selected.get(evidence['group_id'], {}).get('option_ids', []), 'Conflict dùng option chưa chọn')
                option = next(o for g in job['checklist']['groups'] for o in g['options'] if o['option_id'] == evidence['option_id'])
                valid(not option['is_ai_delegate'], 'Không dùng quyền giao AI làm conflict')
                valid(evidence['quote'] in option['decision_text'], 'Conflict sai quote option')
            elif evidence['kind'] == 'custom':
                valid(bool(evidence['quote'].strip()) and evidence['quote'] in selected.get(evidence['group_id'], {}).get('custom_text', ''), 'Conflict sai custom')
            elif evidence['kind'] == 'change':
                valid(any(c['atom_id'] == evidence['atom_id'] and evidence['quote'] in c['replacement_text'] for c in job['choices']['explicit_changes']), 'Conflict sai thay đổi')
            else:
                valid(evidence['atom_id'] in atoms and evidence['atom_id'] not in changed, 'Conflict dùng ý đã thay hoặc không tồn tại')
                atom = atoms[evidence['atom_id']]
                valid(atom['intent_type'] in ('must', 'avoid') and evidence['quote'] in atom['meaning'], 'Conflict phải dựa trên ý đã khóa')
        keys = {(e['kind'], e['group_id'], e['option_id'], e['atom_id'], e['quote']) for e in conflict['evidence']}
        valid(len(keys) >= 2, 'Conflict lặp cùng bằng chứng')
    valid((value['status'] == 'conflict') == bool(value['conflicts']), 'Status conflict không khớp kết quả')


def validate_resolved(value, job):
    valid(value['request_id'] == job['request_id'] and value['revision'] == job['revision'], 'Resolved sai revision')
    domains, atoms = validate_content(value, job['turns'])
    changes = {c['atom_id']: c for c in job['choices']['explicit_changes']}
    retain_atoms(job['clean_prompt']['atoms'], value['atoms'], changes)
    for cid, change in changes.items():
        replacements = [a for a in value['atoms'] if cid in a['supersedes_atom_ids']]
        valid(any(any(r['quote'] == change['replacement_text'] for r in a['source_refs']) for a in replacements), 'Thay đổi không giữ nguyên văn mới')
        valid(cid not in value['locked_atom_ids'], 'Ý đã thay vẫn bị khóa')
    valid(set(value['locked_atom_ids'] + value['delegated_atom_ids']) <= atoms.keys(), 'Khóa/giao AI sai atom')
    valid(not set(value['locked_atom_ids']) & set(value['delegated_atom_ids']), 'Không khóa phần giao AI')
    valid({a['atom_id'] for a in value['atoms'] if a['intent_type'] in ('must', 'avoid') and a['atom_id'] not in changes} <= set(value['locked_atom_ids']), 'Mất điều bắt buộc')
    refs = {r['reference_id'] for r in job['references']}
    valid(set(value['reference_ids']) <= refs, 'Resolved thêm nguồn')
    for space in value['creative_space']:
        valid(space['domain_id'] in domains, 'Không gian sáng tạo sai miền')
    expected = {s['group_id']: s for s in job['choices']['selections'] if s['option_ids'] or s['custom_text'].strip()}
    decisions = unique(value['decisions'], 'group_id')
    exact_ids(list(decisions), expected, f"decisions chỉ có group_ids={list(expected)}; không thêm nhóm locked hoặc nhóm chưa chọn")
    options = {o['option_id']: o for g in job['checklist']['groups'] for o in g['options']}
    for gid, decision in decisions.items():
        original = expected[gid]
        valid(decision['option_ids'] == original['option_ids'] and decision['custom_text'] == original['custom_text'], 'Resolved đổi lựa chọn đã chốt')
        delegated = any(options[o]['is_ai_delegate'] for o in decision['option_ids'])
        valid(decision['delegated'] == delegated, 'Resolved đổi quyền AI chọn')
        valid(bool(decision['atom_ids']) and set(decision['atom_ids']) <= atoms.keys(), 'Quyết định thiếu/sai atom')
        valid(all(any(r['turn_id'] == job['choices']['turn_id'] for r in atoms[aid]['source_refs']) for aid in decision['atom_ids']), 'Quyết định thiếu provenance của lượt chốt')
        target = value['delegated_atom_ids'] if delegated else value['locked_atom_ids']
        valid(set(decision['atom_ids']) <= set(target), 'Quyết định chưa được khóa/giao AI')
        if original['custom_text'].strip():
            valid(any(any(r['quote'] == original['custom_text'] for r in atoms[aid]['source_refs']) for aid in decision['atom_ids']), 'Mất custom_text provenance')
    explicitly_chosen = {aid for d in decisions.values() if not d['delegated'] for aid in d['atom_ids']}
    delegated_choices = {aid for d in decisions.values() if d['delegated'] for aid in d['atom_ids']}
    allowed_locked = {aid for aid, a in atoms.items() if a['intent_type'] in ('must', 'avoid')} | explicitly_chosen
    valid(set(value['locked_atom_ids']) <= allowed_locked,
          f"locked_atom_ids chứa ý chưa được chốt {sorted(set(value['locked_atom_ids']) - allowed_locked)}; chỉ khóa must/avoid hoặc atom mới của quyết định không delegated")
    valid(set(value['delegated_atom_ids']) <= {aid for aid, a in atoms.items() if a['intent_type'] == 'delegated'} | delegated_choices,
          'Tự giao AI quyết định phần chưa được người dùng cho phép')
    valid(value['status'] != 'ready' or not value['conflicts'] and value['historical_mode'] != 'unresolved', 'Không ready khi còn mâu thuẫn')
    if value['historical_mode'] == 'historical' and value['status'] == 'ready':
        valid(any(r['reference_id'] in value['reference_ids'] and r['discovery_status'] == 'tool_grounded' and r['supporting_excerpt'] and r['source_type'] in ('museum', 'research', 'historical_document', 'artifact') for r in job['references']), 'Tái hiện thiếu nguồn lịch sử đúng phạm vi')


def normalize_quote_case(value, candidates=None):
    """Copy a unique original excerpt for a case-only mismatch; never paraphrase."""
    repairs = []
    by_id = {c['candidate_id']: c for c in (candidates or value.get('candidates', []))}
    rows = value.get('audits', []) if candidates is not None else value.get('candidates', [])
    for row in rows:
        candidate = by_id.get(row['candidate_id'])
        if candidate is None:
            continue  # The ordinary ID validator rejects unknown candidates.
        prompt = candidate['image_prompt']
        entries = row.get('checks', []) if candidates is not None else row.get('locked_coverage', [])
        for entry in entries:
            quote = entry['prompt_quote']
            if not quote or quote in prompt:
                continue
            matches = [m for m in re.finditer(re.escape(quote), prompt, re.IGNORECASE)
                       if m.group(0).casefold() == quote.casefold()]
            if len(matches) == 1:
                original = matches[0].group(0)
                repairs.append({'candidate_id': row['candidate_id'],
                                'entry_id': entry.get('atom_id', entry.get('check_id')),
                                'reported_quote': quote, 'original_quote': original,
                                'start': matches[0].start(), 'end': matches[0].end()})
                entry['prompt_quote'] = original
    return repairs


def content_hash(candidate):
    return digest({key: candidate[key] for key in CONTENT_FIELDS})


def validate_candidates(value, job, slots):
    candidates = value['candidates']
    unique(candidates, 'candidate_id')
    expected = {s['candidate_id']: s for s in slots['slots']}
    valid(set(c['candidate_id'] for c in candidates) <= expected.keys(), 'Candidate ngoài slots')
    brief = job['resolved_brief']; domains = {d['domain_id'] for d in brief['domains']}; atoms = {a['atom_id'] for a in brief['atoms']}
    references = {r['reference_id']: r for r in job['references']}
    for candidate in candidates:
        valid(candidate['revision'] == job['revision'] and candidate['batch_id'] == slots['batch_id'], 'Candidate sai batch/revision')
        for section in candidate['design_sections']:
            valid(section['domain_id'] in domains and set(section['related_atom_ids']) <= atoms, 'Design section sai miền/atom')
        # Coverage is model-declared context; API specialists assess locked requirements.
        unique(candidate['claims'], 'claim_id')
        for claim in candidate['claims']:
            valid(claim['reference_id'] in references and claim['source_id'] == claim['reference_id'], 'Claim sai nguồn')
            source = references[claim['reference_id']]
            valid(source['discovery_status'] == 'tool_grounded' and source['supporting_excerpt'] and claim['excerpt'] in source['supporting_excerpt'] and claim['scope'] == source['scope'], 'Claim không có đoạn hỗ trợ đúng phạm vi')


def rubric(config, role, brief):
    applicable = role != 'culture' or brief['historical_mode'] != 'neutral'
    return {'version': config['rubric_version'], 'role': role, 'rating_min': 0, 'rating_max': 5,
            'criteria': [{'criterion_id': key, 'weight': weight, 'applicable': applicable,
                          'applicability_reason': 'Không có yêu cầu văn hóa' if not applicable else 'Theo nhu cầu và vai trò'} for key, weight in config['rubrics'][role].items()]}


def expected_checks(brief, candidates, role):
    # Every locked atom is checked by each perspective; there is no domain-name classifier.
    result = [{'check_id': 'locked:' + aid, 'owner_role': role, 'severity': 'hard', 'applicability': True,
               'content': next(a['meaning'] for a in brief['atoms'] if a['atom_id'] == aid)} for aid in brief['locked_atom_ids']]
    result.append({'check_id': 'summary_prompt_consistency', 'owner_role': role, 'severity': 'hard', 'applicability': True, 'content': 'Toàn bộ kế hoạch/tóm tắt phải trùng prompt'})
    if role == 'culture':
        result += [{'check_id': 'claim_support', 'owner_role': role, 'severity': 'hard', 'applicability': True, 'content': 'Kiểm tra claims và phát biểu thực tế trong prompt/tóm tắt; không có claim sai nguồn', 'evidence_mode': 'claim_inventory', 'empty_quote_allowed_for_candidate_ids': [c['candidate_id'] for c in candidates if not c['claims']]},
                   {'check_id': 'historical_scope', 'owner_role': role, 'severity': 'hard', 'applicability': brief['historical_mode'] == 'historical', 'content': 'Mọi phần lịch sử bắt buộc có căn cứ đúng vùng/thời kỳ, không đổi mode'}]
    return result


def ratings_score(ratings, manifest):
    criteria = {c['criterion_id']: c for c in manifest['criteria']}
    exact_ids([r['criterion_id'] for r in ratings], criteria, 'Sai tập bốn tiêu chí')
    total = weight = 0
    for item in ratings:
        criterion = criteria[item['criterion_id']]
        valid(item['applicable'] == criterion['applicable'], 'Auditor đổi applicability')
        valid(bool(item['reason'].strip()), 'Thiếu lý do rating')
        if item['applicable']:
            valid(type(item['rating']) is int and 0 <= item['rating'] <= 5, 'Rating phải nguyên 0–5')
            total += criterion['weight'] * item['rating'] / 5
            weight += criterion['weight']
        else:
            valid(item['rating'] is None, 'Không áp dụng phải là null')
    return round(100 * total / weight, 2) if weight else None


def validate_specialists(value, candidates, checks, role, role_rubric, references):
    valid(value['role'] == role, 'Sai role của batch')
    by_id = {c['candidate_id']: c for c in candidates}
    exact_ids([a['candidate_id'] for a in value['audits']], by_id, 'Audit thiếu/thừa/đúp candidate')
    expected = {c['check_id']: c for c in checks}; sources = {r['reference_id'] for r in references}
    for audit in value['audits']:
        candidate = by_id[audit['candidate_id']]
        valid(audit['role'] == role and audit['candidate_revision'] == candidate['revision'] and audit['content_hash'] == content_hash(candidate), 'Audit sai role/revision/hash')
        exact_ids([c['check_id'] for c in audit['checks']], expected, 'Audit thiếu/thừa/đúp check')
        for check in audit['checks']:
            gate = expected[check['check_id']]
            valid(check['owner_role'] == role and check['severity'] == gate['severity'], 'Đổi chủ sở hữu/mức bắt buộc check')
            valid((check['status'] == 'not_applicable') == (not gate['applicability']), 'Đổi applicability check')
            valid(bool(check['reason'].strip()) and set(check['source_ids']) <= sources, 'Check thiếu lý do hoặc sai nguồn')
            valid(not check['prompt_quote'] or check['prompt_quote'] in candidate['image_prompt'], 'Audit quote không có trong prompt')
            inventory_absence = (role == 'culture' and check['check_id'] == 'claim_support'
                                 and gate.get('evidence_mode') == 'claim_inventory'
                                 and candidate['candidate_id'] in gate.get('empty_quote_allowed_for_candidate_ids', [])
                                 and not candidate['claims'] and not check['source_ids'])
            valid(check['status'] != 'pass' or bool(check['prompt_quote']) or inventory_absence, 'Pass phải có chi tiết prompt hoặc căn cứ claim_inventory được phép')
        ratings_score(audit['criterion_ratings'], role_rubric)


def gate_summary(specialists):
    return [dict(c) for audit in specialists.values() for c in audit['checks'] if c['severity'] == 'hard' and c['status'] not in ('pass', 'not_applicable')]


def total_score(scores, harmony, weights):
    values = dict(scores, harmony=harmony)
    weight = sum(weights[r] for r, v in values.items() if v is not None)
    return round(sum(weights[r] * v for r, v in values.items() if v is not None) / weight, 2) if weight else None


def validate_harmony(value, candidates, specialists, config, brief, profile):
    by_id = {c['candidate_id']: c for c in candidates}
    exact_ids([a['candidate_id'] for a in value['audits']], by_id, 'Harmony sai tập candidate')
    for audit in value['audits']:
        candidate = by_id[audit['candidate_id']]; source = specialists[candidate['candidate_id']]
        valid(set(source) == {'fashion', 'culture', 'art'}, 'Harmony thiếu chuyên môn')
        valid(audit['candidate_revision'] == candidate['revision'] and audit['content_hash'] == content_hash(candidate), 'Harmony sai revision/hash')
        scores = {role: item['score'] for role, item in source.items()}
        valid(audit['source_scores'] == scores, 'Harmony thay điểm nguồn')
        h = ratings_score(audit['harmony_ratings'], rubric(config, 'harmony', brief))
        total_score(scores, h, config['profiles'][profile])


def rank(candidates, specialists, harmonies, config):
    ranked, rejected = [], []
    seen_prompts, seen_plans = set(), set()
    for candidate in candidates:
        cid = candidate['candidate_id']; source = specialists.get(cid, {}); harmony = harmonies.get(cid)
        reason = None
        if set(source) != {'fashion', 'culture', 'art'} or not harmony:
            reason = 'Chưa đủ bốn đánh giá hợp lệ'
        elif harmony['content_hash'] != content_hash(candidate) or any(a['content_hash'] != content_hash(candidate) for a in source.values()):
            reason = 'Prompt đã đổi sau audit'
        elif gate_summary(source):
            reason = 'Điều bắt buộc chưa đạt/chưa rõ'
        elif harmony['recommendation'] != 'eligible' or harmony['cross_domain_conflicts']:
            reason = 'Hài hòa còn xung đột/chưa đủ điều kiện'
        elif harmony['score_100'] is None or harmony['score_100'] < config['minimum_total']:
            reason = 'Tổng điểm dưới ngưỡng'
        if reason:
            rejected.append({'candidate_id': cid, 'reason': reason})
        else:
            ranked.append({'candidate': candidate, 'score': harmony['score_100'], 'scores': harmony['source_scores'], 'harmony': harmony})
    ranked.sort(key=lambda row: (-row['score'], row['candidate']['candidate_id']))
    distinct = []
    for row in ranked:
        candidate = row['candidate']
        prompt = ' '.join(candidate['image_prompt'].split())
        plan = digest(sorted((s['domain_id'], ' '.join(s['description'].split())) for s in candidate['design_sections']))
        if prompt in seen_prompts or plan in seen_plans:
            rejected.append({'candidate_id': candidate['candidate_id'], 'reason': 'Trùng prompt/kế hoạch thực sự'})
            continue
        seen_prompts.add(prompt); seen_plans.add(plan); distinct.append(row)
    return {'ranked': distinct[:3], 'rejected': rejected, 'eligible_count': len(distinct)}


def reported_ratings_score(ratings, manifest):
    """Arithmetic for display only; no acceptance rules for API ratings."""
    weights = {c['criterion_id']: c['weight'] for c in manifest['criteria']}
    rows = [(weights.get(r.get('criterion_id'), 0), r.get('rating')) for r in ratings
            if r.get('applicable') and isinstance(r.get('rating'), (int, float))]
    total_weight = sum(w for w, rating in rows)
    return round(sum(w * rating / 5 for w, rating in rows) * 100 / total_weight, 2) if total_weight else None


def rank_reported(candidates, specialists, harmonies, config):
    """Order API results without backend eligibility, hash or duplicate gates."""
    ranked = []
    for candidate in candidates:
        cid = candidate['candidate_id']
        harmony = harmonies.get(cid)
        if not harmony:
            continue  # No score has arrived to present yet.
        ranked.append({'candidate': candidate, 'score': harmony.get('score_100'),
                       'scores': harmony.get('source_scores', {}), 'harmony': harmony})
    ranked.sort(key=lambda row: (-(row['score'] if isinstance(row['score'], (int, float)) else -1), row['candidate']['candidate_id']))
    return {'ranked': ranked[:3], 'rejected': [], 'eligible_count': len(ranked)}
