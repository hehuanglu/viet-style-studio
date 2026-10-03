"""Explicit simulation responses. No network and no claim to domain expertise."""
import copy

from .viet_phuc import rubric, ratings_score, total_score
from .core import read_json
from .viet_phuc import DATA


def fixture_response(task, p):
    meta = p.get('REQUEST_METADATA', {})
    if task == 'VP01':
        raw = p['RAW_PROMPT']
        value = dict(meta, clean_text=raw, domains=[{'domain_id': 'open', 'label': 'Yêu cầu nguyên văn (fixture)', 'summary': raw, 'related_domain_ids': []}],
                     atoms=[{'atom_id': 'raw', 'domain_ids': ['open'], 'meaning': raw, 'intent_type': 'context', 'polarity': 'neutral', 'source_refs': [{'turn_id': 'T1', 'quote': raw}], 'resolution': 'explicit', 'supersedes_atom_ids': []}], relations=[], conflicts=[], coverage=[{'source_ref': {'turn_id': 'T1', 'quote': raw}, 'atom_ids': ['raw'], 'disposition': 'retained', 'reason': 'Fixture giữ nguyên văn; không phân tích chuyên môn'}])
    elif task == 'VP02R':
        value = {'references': [], 'unresolved_reference_needs': ['Fixture không tìm nguồn web']}
    elif task == 'VP02':
        clean = copy.deepcopy(p['CLEAN_PROMPT']); clean.update(meta)
        value = dict(meta, clean_prompt=clean, form_id=p['FORM_CONFIG']['form_id'], references=copy.deepcopy(p['REFERENCE_BUNDLE']['references']), open_conflicts=[], groups=[{'group_id': 'exploration', 'domain_ids': ['open'], 'label': 'Hướng khám phá (fixture)', 'question': 'Bạn muốn khám phá phần còn mở thế nào?', 'why_it_matters': 'Kiểm tra giao diện và lựa chọn, không hiểu yêu cầu thật', 'status': 'needs_choice', 'selection_mode': 'single', 'min': 1, 'max': 1, 'related_atom_ids': ['raw'], 'depends_on': [], 'allows_custom': True, 'options': [{'option_id': 'delegate', 'label': 'Để AI đề xuất', 'description': 'Mô phỏng phần được giao AI', 'decision_text': 'Để AI đề xuất cách tổ chức thiết kế trong phần còn mở.', 'reference_ids': [], 'origin': 'gemini_suggestion', 'is_recommended': True, 'is_ai_delegate': True, 'compatible_option_ids': [], 'incompatible_option_ids': []}, {'option_id': 'quiet', 'label': 'Điểm nhấn tiết chế', 'description': 'Ví dụ fixture', 'decision_text': 'Chọn điểm nhấn tiết chế trong phần còn mở.', 'reference_ids': [], 'origin': 'gemini_suggestion', 'is_recommended': False, 'is_ai_delegate': False, 'compatible_option_ids': [], 'incompatible_option_ids': []}]}])
        group = value['groups'][0]
        for index, label in enumerate(('Mảng màu', 'Nhịp đường cắt', 'Tỉ lệ lớp', 'Bề mặt chất liệu')):
            option = copy.deepcopy(group['options'][1])
            option.update(option_id='concrete-' + str(index), label=label, description='Ví dụ fixture: ' + label, decision_text='Chọn ' + label + ' trong phần còn mở.')
            group['options'].append(option)
    elif task == 'VP02C':
        value = dict(meta, form_id=p['CHECKLIST']['form_id'], status='clear', conflicts=[], summary='Fixture kiểm tra workflow; không xác minh tương thích thiết kế.')
    elif task == 'VP03':
        clean = p['CLEAN_PROMPT']; selections = p['VALIDATED_SELECTIONS']; turn = selections['turn_id']
        atoms = copy.deepcopy(clean['atoms']); locked = [a['atom_id'] for a in atoms if a['intent_type'] in ('must', 'avoid')]; delegated = []; decisions = []
        opts = {o['option_id']: o for g in p['CHECKLIST']['groups'] for o in g['options']}
        for change in selections['explicit_changes']:
            aid = 'change-' + change['atom_id']
            old = next(a for a in atoms if a['atom_id'] == change['atom_id'])
            atoms.append(dict(old, atom_id=aid, meaning=change['replacement_text'], source_refs=[{'turn_id': turn, 'quote': change['replacement_text']}], supersedes_atom_ids=[change['atom_id']]))
            locked = [x for x in locked if x != change['atom_id']] + [aid]
        for selection in selections['selections']:
            if not selection['option_ids'] and not selection['custom_text'].strip(): continue
            aid = 'decision-' + selection['group_id']; delegate = any(opts[x]['is_ai_delegate'] for x in selection['option_ids'])
            text = selection['custom_text'] or ' '.join(opts[x]['decision_text'] for x in selection['option_ids'])
            atoms.append({'atom_id': aid, 'domain_ids': ['open'], 'meaning': text, 'intent_type': 'delegated' if delegate else 'must', 'polarity': 'positive', 'source_refs': [{'turn_id': turn, 'quote': text}], 'resolution': 'explicit', 'supersedes_atom_ids': []})
            (delegated if delegate else locked).append(aid)
            decisions.append(dict(selection, delegated=delegate, atom_ids=[aid]))
        value = dict(meta, resolved_text=clean['clean_text'] + '\n' + '\n'.join(a['meaning'] for a in atoms if a['atom_id'] != 'raw'), domains=clean['domains'], atoms=atoms, locked_atom_ids=locked, delegated_atom_ids=delegated, creative_space=[{'domain_id': 'open', 'description': 'Khám phá cách tổ chức phần còn mở trong fixture', 'allowed_variations': ['vị trí', 'nhịp', 'tỉ lệ']}], reference_ids=[], historical_mode='neutral', decisions=decisions, conflicts=[], status='ready')
    elif task == 'VP04':
        brief = p['RESOLVED_BRIEF']; candidates = []
        atoms = {a['atom_id']: a for a in brief['atoms']}
        offset = int(p['GENERATION_DIRECTION']['direction_id'][1:]) * 3
        for i, slot in enumerate(p['CANDIDATE_SLOTS']['slots']):
            design = f'Fixture: vị trí {offset+i}, nhịp {offset+i+1}, tỉ lệ {offset+i+2}; không phải kiểm chứng thiết kế thật.'
            prompt = brief['resolved_text'] + '\n' + design + '\n' + '\n'.join(atoms[x]['meaning'] for x in brief['locked_atom_ids'])
            candidates.append(dict(slot, batch_id=p['CANDIDATE_SLOTS']['batch_id'], title=f'Phương án fixture {offset+i}', image_prompt=prompt, design_sections=[{'domain_id': 'open', 'description': design, 'related_atom_ids': brief['locked_atom_ids']}], fashion_summary=design, art_summary=design, culture_summary='Không xác nhận văn hóa bằng fixture.', choices_made=[design], claims=[], locked_coverage=[{'atom_id': x, 'prompt_quote': atoms[x]['meaning']} for x in brief['locked_atom_ids']], assumptions=[], limitations=['Fixture chỉ kiểm tra workflow']))
        value = {'candidates': candidates, 'limitations': []}
    elif task in ('VP05', 'VP06', 'VP07'):
        role = p['ROLE_RUBRIC']['role']; audits = []
        for c in p['CANDIDATE_BATCH']:
            rating = 5 if c['candidate_id'].endswith('C1') else 4
            audits.append({'candidate_id': c['candidate_id'], 'candidate_revision': c['revision'], 'content_hash': c['content_hash'], 'role': role,
                           'checks': [{'check_id': x['check_id'], 'owner_role': role, 'severity': x['severity'], 'status': 'pass' if x['applicability'] else 'not_applicable', 'prompt_quote': c['image_prompt'] if x['applicability'] else '', 'source_ids': [], 'reason': 'Fixture; không xác minh chuyên môn'} for x in p['EXPECTED_CHECKS']],
                           'criterion_ratings': [{'criterion_id': x['criterion_id'], 'applicable': x['applicable'], 'rating': rating if x['applicable'] else None, 'reason': 'Fixture có điều kiện áp dụng'} for x in p['ROLE_RUBRIC']['criteria']], 'score': rating * 20 if any(x['applicable'] for x in p['ROLE_RUBRIC']['criteria']) else None, 'score_reason': 'Điểm fixture theo rubric; không đánh giá thật.', 'strengths': ['Fixture'], 'concerns': [], 'suggested_fixes': [], 'summary': 'Nhận xét fixture; chưa có xác nhận thật.'})
        value = {'role': role, 'audits': audits}
    elif task == 'VP08':
        audits = []
        for c in p['CANDIDATE_BATCH']:
            source = p['VALIDATED_SPECIALIST_AUDITS'][c['candidate_id']]
            scores = {role: item['score'] for role, item in source.items()}
            ratings = [{'criterion_id': x['criterion_id'], 'applicable': x['applicable'], 'rating': 4 if x['applicable'] else None, 'reason': 'Fixture'} for x in p['HARMONY_RUBRIC']['criteria']]
            h = ratings_score(ratings, p['HARMONY_RUBRIC'])
            audits.append({'candidate_id': c['candidate_id'], 'candidate_revision': c['revision'], 'content_hash': c['content_hash'], 'source_scores': scores, 'harmony_ratings': ratings, 'harmony_score': h, 'proposed_total': total_score(scores, h, p['SCORING_CONFIG']['weights']), 'cross_domain_conflicts': [], 'recommendation': 'eligible', 'summary': 'Hài hòa fixture; chưa kiểm chứng thực tế.'})
        value = {'audits': audits}
    else:
        raise ValueError(task)
    return value, {'mock': True}, {'fixture': True}
