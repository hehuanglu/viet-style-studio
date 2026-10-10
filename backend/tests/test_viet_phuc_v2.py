"""V2 fixture and injected-transport tests; ZERO live Gemini calls."""
import copy
import json
import tempfile
import threading
import time
import unittest
import uuid
from pathlib import Path
from unittest.mock import patch

from arena_backend.core import ArenaError, Budget, Contracts, PROJECT
from arena_backend.engine import Engine
from arena_backend.providers import GeminiProvider, MockProvider, ProviderError, gemini_wire_schema, google_retry_delay
from arena_backend.report import user_report
from arena_backend.server import create_server
from arena_backend import viet_phuc as vp
from test_manual_workflow import image

RAW = 'Âu phục lai nét Việt; chỉ xanh; sen, rồng, mây là ví dụ, không cần tất cả; vải nhẹ; đi đám cưới; không chỉ định giới tính; để AI đề xuất; thêm túi cảm biến.'
STOP = {'awaiting_choices', 'awaiting_image', 'complete', 'needs_evidence', 'needs_resolution', 'failed', 'cancelled', 'cards_only'}


def wait(engine, rid):
    until = time.monotonic() + 8
    while time.monotonic() < until:
        job = engine.store.get_job(rid)
        if job['status'] in STOP:
            return job
        time.sleep(.005)
    raise AssertionError('Request không tới checkpoint')


class Recorder(MockProvider):
    def __init__(self):
        self.payloads = []; self.lock = threading.Lock()
    def structured_v2(self, task, system, prompt, schema, payload, timeout, config):
        with self.lock:
            self.payloads.append((task, copy.deepcopy(payload)))
        return super().structured_v2(task, system, prompt, schema, payload, timeout, config)
    def image(self, *args, **kwargs):
        raise AssertionError('Không gọi API tạo ảnh trong đường chính')


class OpenAtoms(Recorder):
    """Hand-authored semantic fixture, not a regex understanding engine."""
    def structured_v2(self, task, *args, **kwargs):
        value, usage, metadata = super().structured_v2(task, *args, **kwargs)
        if task == 'VP01':
            atoms = []; coverage = []
            domains = ['Cấu trúc lai', 'Màu', 'Ví dụ mô-típ', 'Quyền chọn', 'Chất liệu', 'Bối cảnh', 'Người mặc', 'Giao AI', 'Công nghệ may mặc']
            quotes = ['Âu phục lai nét Việt', 'chỉ xanh', 'sen, rồng, mây là ví dụ', 'không cần tất cả', 'vải nhẹ', 'đi đám cưới', 'không chỉ định giới tính', 'để AI đề xuất', 'thêm túi cảm biến']
            intents = ['must', 'must', 'example', 'context', 'preference', 'context', 'avoid', 'delegated', 'must']
            value['domains'] = [{'domain_id': 'open', 'label': 'Yêu cầu mở', 'summary': RAW, 'related_domain_ids': []}] + [{'domain_id': 'D' + str(i), 'label': label, 'summary': quote, 'related_domain_ids': []} for i, (label, quote) in enumerate(zip(domains, quotes))]
            for i, (quote, intent) in enumerate(zip(quotes, intents)):
                aid = 'raw' if i == 0 else 'A' + str(i)
                source = {'turn_id': 'T1', 'quote': quote}
                atoms.append({'atom_id': aid, 'domain_ids': ['open', 'D' + str(i)], 'meaning': quote, 'intent_type': intent, 'polarity': 'negative' if intent == 'avoid' else 'positive', 'source_refs': [source], 'resolution': 'explicit', 'supersedes_atom_ids': []})
                coverage.append({'source_ref': source, 'atom_ids': [aid], 'disposition': 'example' if intent == 'example' else 'retained', 'reason': 'Fixture nguyên văn'})
            value.update(atoms=atoms, coverage=coverage)
        return value, usage, metadata


class V2Tests(unittest.TestCase):
    def test_excerpt_bank_is_verbatim_and_does_not_modify_candidate_hash(self):
        candidates = [{'image_prompt':'Áo kín. Mặt sau xanh! TP.HCM, vải nhẹ.', 'content_hash':'original'}]
        enriched = vp.audit_candidates(candidates)
        self.assertNotIn('verbatim_excerpt_bank', candidates[0])
        self.assertEqual(enriched[0]['content_hash'], 'original')
        self.assertTrue(all(q in candidates[0]['image_prompt'] for q in enriched[0]['verbatim_excerpt_bank']))

    def test_api_quote_enum_uses_only_verbatim_excerpts_without_mutating_schema(self):
        schema = {'properties':{'prompt_quote':{'type':'string'}}}
        enriched = vp.audit_response_schema(schema, [{'image_prompt':'Cổ kín. Lưng kín.'}])
        self.assertNotIn('enum', schema['properties']['prompt_quote'])
        self.assertEqual(enriched['properties']['prompt_quote']['enum'], ['', 'Cổ kín.', 'Lưng kín.'])

    def test_response_calculation_order_is_consistent_in_properties_and_required(self):
        schema = {'properties':{'score':{'type':'number'},'score_reason':{'type':'string'}},'required':['score','score_reason']}
        result = vp.audit_response_schema(schema, [])
        self.assertEqual(result['required'], ['score_reason', 'score'])
        self.assertEqual(list(result['properties']), result['required'])
        harmony = {'properties':{k:{'type':'string' if k == 'summary' else 'number'} for k in ('harmony_score','proposed_total','summary')},'required':['harmony_score','proposed_total','summary']}
        result = vp.harmony_response_schema(harmony)
        self.assertEqual(result['required'], ['summary','harmony_score','proposed_total'])
        self.assertEqual(list(result['properties']), result['required'])

    def test_confirmed_changes_retire_both_old_lock_and_delegation(self):
        atoms = [{'atom_id':'a','intent_type':'must'}, {'atom_id':'b','intent_type':'delegated'}, {'atom_id':'c','intent_type':'avoid'}, {'atom_id':'d','intent_type':'context'}]
        binding = vp.old_atom_binding(atoms, [{'atom_id':'a'}, {'atom_id':'b'}])
        self.assertEqual(binding['must_lock'], ['c'])
        self.assertEqual(binding['keep_delegated'], [])
        self.assertEqual(binding['superseded'], ['a', 'b'])
        self.assertFalse(set(binding['must_lock']) & set(binding['do_not_lock']))
        self.assertEqual(vp.old_atom_binding(atoms, [])['keep_delegated'], ['b'])

    def test_edit_prompt_without_guide_retains_full_v2_prompt_context(self):
        e = self.engine(); j = self.finish(e, self.start(e))
        cid = j['cards'][0]['candidate_id']
        packet = e.image_edit_prompt(j['request_id'], {'candidate_id':cid, 'instruction':'Đổi vị trí đường thêu', 'keep':'Giữ bộ đồ', 'strokes':[]})
        self.assertEqual(packet['required_images'], ['original'])
        self.assertNotIn('Ảnh 2', packet['prompt'])
        self.assertNotIn('{{', packet['prompt'])
        prompt = next(p['prompt'] for p in j['image_prompts'] if p['candidate_id'] == cid)
        self.assertIn(json.dumps(prompt, ensure_ascii=False), packet['prompt'])
        self.assertIn('resolved_text', packet['prompt'])

    def test_edit_packet_accepts_original_without_requiring_an_unused_guide(self):
        e = self.engine(); j = self.finish(e, self.start(e))
        packet = e.image_edit_prompt(j['request_id'], {'candidate_id':j['cards'][0]['candidate_id'], 'instruction':'Thu nhỏ hoa văn', 'strokes':[], 'original':image()})
        self.assertEqual(packet['required_images'], ['original'])
        self.assertIn('original_url', packet)
        self.assertNotIn('guide_url', packet)

    def test_quote_case_repair_copies_original_and_never_changes_prompt(self):
        def value(prompt, quote):
            return {'candidates':[{'candidate_id':'c','image_prompt':prompt,'locked_coverage':[{'atom_id':'a','prompt_quote':quote}]}]}
        v = value('Một khung hình thiết kế váy màu xanh.', 'Thiết kế váy màu xanh.')
        original = v['candidates'][0]['image_prompt']
        repairs = vp.normalize_quote_case(v)
        self.assertEqual(v['candidates'][0]['image_prompt'], original)
        self.assertEqual(v['candidates'][0]['locked_coverage'][0]['prompt_quote'], 'thiết kế váy màu xanh.')
        self.assertEqual(len(repairs), 1)
        for prompt, quote in [('váy màu xanh.', 'váy màu xanh'), ('váy màu xanh.', 'váy màu xanh!'), ('váy màu xanh.', 'vay mau xanh.'), ('váy màu xanh.', 'váy xanh.'), ('thiết kế. thiết kế.', 'Thiết kế.')]:
            v = value(prompt, quote)
            self.assertEqual(vp.normalize_quote_case(v), [])
            self.assertEqual(v['candidates'][0]['locked_coverage'][0]['prompt_quote'], quote)

    def test_workflow_vp04_unmatched_or_missing_coverage_does_not_regenerate_batch(self):
        class UpperQuotes(Recorder):
            def structured_v2(self, task, *args, **kwargs):
                value, usage, metadata = super().structured_v2(task, *args, **kwargs)
                if task == 'VP04':
                    for c in value['candidates']:
                        for coverage in c['locked_coverage']:
                            coverage['prompt_quote'] = 'Quote diễn đạt lại không có trong prompt'
                        c['locked_coverage'] = c['locked_coverage'][:1]
                return value, usage, metadata
        provider = UpperQuotes(); e = self.engine(provider)
        final = self.finish(e, self.start(e))
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        self.assertEqual(len([t for t, p in provider.payloads if t == 'VP04']), 2)
        for c in final['prompt_pool']:
            self.assertLessEqual(len(c['locked_coverage']), 1)
            for entry in c['locked_coverage']:
                self.assertEqual(entry['prompt_quote'], 'Quote diễn đạt lại không có trong prompt')

    def test_specialist_api_score_and_reason_are_persisted_and_sent_to_harmony(self):
        class ApiScores(Recorder):
            def structured_v2(self, task, *args, **kwargs):
                value, usage, metadata = super().structured_v2(task, *args, **kwargs)
                if task in ('VP05', 'VP06', 'VP07'):
                    for audit in value['audits']:
                        audit['score'] = 37.25
                        audit['score_reason'] = 'Điểm API độc lập với phép tính backend'
                return value, usage, metadata
        provider = ApiScores(); engine = self.engine(provider)
        final = self.finish(engine, self.start(engine))
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        for audits in final['specialist_audits'].values():
            for audit in audits.values():
                self.assertEqual(audit['score'], 37.25)
                self.assertEqual(audit['score_reason'], 'Điểm API độc lập với phép tính backend')
        harmony_inputs = [payload for task, payload in provider.payloads if task == 'VP08']
        self.assertEqual(len(harmony_inputs), 2)
        for payload in harmony_inputs:
            for audits in payload['VALIDATED_SPECIALIST_AUDITS'].values():
                for audit in audits.values():
                    self.assertEqual(audit['score'], 37.25)
                    self.assertIn('score_reason', audit)
                    self.assertIn('checks', audit)
                    self.assertIn('criterion_ratings', audit)

    def test_api_output_validators_are_not_called_from_vp04(self):
        from unittest.mock import patch
        class LooseAudit(Recorder):
            def structured_v2(self, task, *args, **kwargs):
                value, usage, metadata = super().structured_v2(task, *args, **kwargs)
                if task in ('VP05', 'VP06', 'VP07'):
                    for audit in value['audits']:
                        audit['content_hash'] = 'model-reported-hash'
                        for check in audit['checks']:
                            check['prompt_quote'] = 'Không có trong prompt'
                            check['source_ids'] = ['unverified-source']
                return value, usage, metadata
        provider = LooseAudit(); engine = self.engine(provider)
        original = engine.vp_contracts.validate
        def validate(schema, value):
            self.assertNotIn(schema, ('ImagePromptBatch', 'SpecialistAuditBatch', 'HarmonyAuditBatch'))
            return original(schema, value)
        with patch.object(engine.vp_contracts, 'validate', side_effect=validate), \
             patch.object(vp, 'validate_candidates', side_effect=AssertionError('VP04 gate called')), \
             patch.object(vp, 'validate_specialists', side_effect=AssertionError('Audit gate called')), \
             patch.object(vp, 'validate_harmony', side_effect=AssertionError('Harmony gate called')):
            final = self.finish(engine, self.start(engine))
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        self.assertEqual(len(final['cards']), 3)

    def test_claim_inventory_absence_exception_is_scoped_to_empty_claims(self):
        e = self.engine(); final = self.finish(e, self.start(e)); c = final['prompt_pool'][0]
        brief = final['resolved_brief']; checks = vp.expected_checks(brief, [c], 'culture')
        rubric = vp.rubric(e.vp_config, 'culture', brief)
        audit = copy.deepcopy(final['specialist_audits'][c['candidate_id']]['culture'])
        # Stored score fields are not part of this validator's check contract.
        claim = next(x for x in audit['checks'] if x['check_id'] == 'claim_support')
        claim.update(prompt_quote='', source_ids=[], reason='Đã kiểm tra claims=[] và prompt/tóm tắt không có claim thực tế cần nguồn.')
        vp.validate_specialists({'role':'culture','audits':[audit]}, [c], checks, 'culture', rubric, [])
        bad = copy.deepcopy(audit)
        next(x for x in bad['checks'] if x['check_id'] == 'summary_prompt_consistency')['prompt_quote'] = ''
        with self.assertRaises(ArenaError):
            vp.validate_specialists({'role':'culture','audits':[bad]}, [c], checks, 'culture', rubric, [])
        claimed = copy.deepcopy(c); claimed['claims'] = [{'claim_id':'real-claim','reference_id':'r'}]
        claimed_audit = copy.deepcopy(audit); claimed_audit['content_hash'] = vp.content_hash(claimed)
        claimed_checks = vp.expected_checks(brief, [claimed], 'culture')
        with self.assertRaises(ArenaError):
            vp.validate_specialists({'role':'culture','audits':[claimed_audit]}, [claimed], claimed_checks, 'culture', rubric, [])
        claim['source_ids'] = ['r']
        with self.assertRaises(ArenaError):
            vp.validate_specialists({'role':'culture','audits':[audit]}, [c], checks, 'culture', rubric, [{'reference_id':'r'}])

    def test_selection_conflict_restores_same_form_and_only_latest_choices_advance(self):
        class ConflictReviewer(Recorder):
            def structured_v2(self, task, system, prompt, schema, payload, timeout, config):
                value, usage, metadata = super().structured_v2(task, system, prompt, schema, payload, timeout, config)
                if task == 'VP02C' and payload['CURRENT_SELECTIONS']['selections'][0]['custom_text'] == 'high collar; deep neckline':
                    value.update(status='conflict', conflicts=[{'conflict_id':'neck', 'severity':'severe', 'summary':'Opposing collar requirements', 'reason':'Same collar on same layer', 'same_feature':'collar', 'suggested_fix':'Separate the layers', 'evidence':[{'kind':'custom','group_id':'exploration','option_id':'','atom_id':'','quote':quote} for quote in ('high collar','deep neckline')]}])
                return value, usage, metadata
        provider = ConflictReviewer(); engine = self.engine(provider); job = self.start(engine)
        form = job['checklist']['form_id']; options = copy.deepcopy(job['checklist']['groups'])
        engine.selections(job['request_id'], self.choices(job, selections=[{'group_id':'exploration','option_ids':[],'custom_text':'high collar; deep neckline'}]))
        conflict = wait(engine, job['request_id'])
        self.assertEqual(conflict['status'], 'awaiting_choices')
        self.assertEqual(conflict['selection_review']['status'], 'conflict')
        self.assertEqual(conflict['checklist']['form_id'], form)
        self.assertEqual(conflict['checklist']['groups'], options)
        self.assertEqual(conflict['choice_restore'], conflict['choices'])
        self.assertNotIn('VP03', [task for task, _ in provider.payloads])
        self.assertNotIn('VP04', [task for task, _ in provider.payloads])
        engine.selections(job['request_id'], self.choices(conflict, selections=[{'group_id':'exploration','option_ids':[],'custom_text':'high inner collar; deep outer neckline'}]))
        final = wait(engine, job['request_id'])
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        self.assertEqual(final['selection_review']['status'], 'clear')
        self.assertEqual(len([t for t, _ in provider.payloads if t == 'VP02C']), 2)
        self.assertEqual(final['choices']['selections'][0]['custom_text'], 'high inner collar; deep outer neckline')
        self.assertNotIn('choice_restore', final)
        self.assertEqual(final['selection_review_history'][0]['review']['status'], 'conflict')

    def test_selection_review_api_failure_never_advances_and_is_retryable(self):
        class BrokenReviewer(Recorder):
            broken = True
            def structured_v2(self, task, *args, **kwargs):
                if task == 'VP02C' and self.broken:
                    raise ArenaError('semantic_invalid', 'Invalid review response')
                return super().structured_v2(task, *args, **kwargs)
        provider = BrokenReviewer(); engine = self.engine(provider); job = self.start(engine)
        engine.selections(job['request_id'], self.choices(job))
        failed = wait(engine, job['request_id'])
        self.assertEqual(failed['status'], 'failed')
        self.assertEqual(failed['failed_stage'], 'checking_selection_conflicts')
        self.assertNotIn('VP03', [t for t, _ in provider.payloads])
        provider.broken = False
        engine.retry_resolution(job['request_id'], {'revision': failed['revision']})
        final = wait(engine, job['request_id'])
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        self.assertEqual(final['selection_review']['status'], 'clear')

    def test_audit_retry_with_only_supplemental_pool_does_not_regenerate(self):
        class PartialPool(Recorder):
            unresolved = True
            def structured_v2(self, task, *args, **kwargs):
                value, usage, metadata = super().structured_v2(task, *args, **kwargs)
                if task == 'VP04' and value['candidates'][0]['batch_id'] in ('B1', 'B2'):
                    raise ArenaError('semantic_invalid', 'Fixture initial batch failure')
                if task == 'VP08' and self.unresolved:
                    for audit in value['audits']:
                        audit['cross_domain_conflicts'] = ['Fixture unresolved conflict']
                        audit['recommendation'] = 'unresolved'
                return value, usage, metadata
        provider = PartialPool(); engine = self.engine(provider)
        job = self.start(engine); engine.selections(job['request_id'], self.choices(job))
        failed = wait(engine, job['request_id'])
        self.assertEqual(failed['status'], 'awaiting_image')
        self.assertEqual(set(failed['generation_batches']), {'B3'})
        self.assertEqual(len(failed['cards']), 3)
        self.assertTrue(all(c['harmony']['recommendation'] == 'unresolved' for c in failed['cards']))

    def test_audit_retry_preserves_prompt_hashes_and_valid_roles(self):
        class Recoverable(Recorder):
            broken = True
            def structured_v2(self, task, *args, **kwargs):
                if task == 'VP06' and self.broken:
                    raise ArenaError('semantic_invalid', 'Fixture culture failure')
                return super().structured_v2(task, *args, **kwargs)
        provider = Recoverable(); engine = self.engine(provider)
        job = self.start(engine); engine.selections(job['request_id'], self.choices(job))
        failed = wait(engine, job['request_id'])
        self.assertEqual(failed['status'], 'needs_resolution')
        before = copy.deepcopy(failed['prompt_pool']); used = failed['metrics']['design']['attempts']
        called = len(provider.payloads); provider.broken = False
        engine.retry_audits(job['request_id'], {'revision': failed['revision']})
        final = wait(engine, job['request_id'])
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        self.assertEqual(final['prompt_pool'], before)
        batches = len(failed['generation_batches'])
        self.assertEqual(final['metrics']['design']['attempts'], used + 2 * batches + 3)
        self.assertEqual([t for t,p in provider.payloads[called:]].count('VP06'), batches)
        self.assertEqual([t for t,p in provider.payloads[called:]].count('VP08'), batches)
        self.assertNotIn('VP05', [t for t,p in provider.payloads[called:]])
        self.assertNotIn('VP04', [t for t,p in provider.payloads[called:]])
        for t,p in provider.payloads[called:]:
            if t == 'VP06':
                self.assertNotIn('specialist_audits', p)
                for check in p['EXPECTED_CHECKS']:
                    if check['check_id'].startswith('locked:'):
                        for c in p['CANDIDATE_BATCH']:
                            self.assertIn(check['exact_prompt_excerpts'][c['candidate_id']], c['image_prompt'])
        with self.assertRaises(ArenaError):
            engine.retry_audits(job['request_id'], {'revision': failed['revision']})

    def test_runtime_budget_override_is_explicit_and_media_stays_separate(self):
        base = self.engine()
        experimental = Engine(Recorder(), Path(self.temp.name) / 'budget', allow_mock_requests=True, design_attempts_override=32)
        self.engines.append(experimental)
        self.assertEqual(base.vp_config['design_budget']['total_provider_calls_max'], 36)
        self.assertEqual(experimental.vp_config['design_budget']['total_provider_calls_max'], 32)
        self.assertEqual(experimental.vp_config['design_budget']['active_processing_deadline_seconds'], 320)
        self.assertEqual(experimental.vp_config['media_budget']['total_provider_calls_max'], 13)

    def test_older_session_report_keeps_recorded_experimental_budget(self):
        engine = self.engine()
        job = self.finish(engine, self.start(engine))
        job.pop('budget_config')
        recorded = dict(engine.vp_config['design_budget'], total_provider_calls_max=32)
        job['audit_retry_history'] = [{'design_budget': recorded}]
        report = user_report(job, engine.policy)
        self.assertEqual(report['api']['budgets']['design']['total_provider_calls_max'], 32)
        self.assertEqual(report['api']['budgets']['media']['total_provider_calls_max'], 13)
        self.assertEqual(engine.vp_config['design_budget']['total_provider_calls_max'], 36)
        job['budget_config'] = {'design': engine.vp_config['design_budget'], 'media': engine.vp_config['media_budget']}
        self.assertEqual(user_report(job, engine.policy)['api']['budgets']['design']['total_provider_calls_max'], 36)

    def test_resolution_retry_keeps_choices_and_budget_and_rejects_old_revision(self):
        class Recoverable(Recorder):
            broken = True
            def structured_v2(self, task, *args, **kwargs):
                if task == 'VP03' and self.broken:
                    raise ArenaError('semantic_invalid', 'Fixture failure before resolution')
                return super().structured_v2(task, *args, **kwargs)
        provider = Recoverable(); engine = self.engine(provider)
        job = self.start(engine); engine.selections(job['request_id'], self.choices(job))
        failed = wait(engine, job['request_id']); spent = failed['metrics']['design']['attempts']
        self.assertEqual(failed['failed_stage'], 'resolving_choices')
        with engine.lock:
            failed = engine.store.get_job(job['request_id'])
            failed['warnings'].append('Fixture: lỗi của revision trước')
            engine.store.save_job(failed)
        provider.broken = False
        resumed = engine.retry_resolution(job['request_id'], {'revision': failed['revision']})
        self.assertEqual(resumed['revision'], failed['revision'] + 1)
        with self.assertRaises(ArenaError):
            engine.retry_resolution(job['request_id'], {'revision': failed['revision']})
        final = wait(engine, job['request_id'])
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        self.assertGreater(final['metrics']['design']['attempts'], spent)
        self.assertEqual(final['choices']['selections'], failed['choices']['selections'])
        self.assertEqual(final['resolution_retry_history'][0]['error'], failed['error'])
        self.assertTrue(any('Fixture: lỗi của revision trước' in h['warnings'] for h in final['warning_history']))
        self.assertNotIn('Fixture: lỗi của revision trước', final['warnings'])
        self.assertEqual(final['budget_config']['design']['total_provider_calls_max'], 36)
        contract = next(p['VALIDATED_SELECTIONS']['decision_contracts'] for t, p in provider.payloads if t == 'VP03')
        self.assertTrue(contract[0]['delegated'])
        self.assertEqual(contract[0]['option_ids'], ['delegate'])

    def test_basic_mode_has_no_web_calls_or_generated_links(self):
        class Basic(Recorder):
            def structured_v2(self, task, system, prompt, schema, payload, timeout, config):
                if config.get('web_tools'):
                    raise AssertionError('Basic mode must not invoke web tools')
                return super().structured_v2(task, system, prompt, schema, payload, timeout, config)
        provider = Basic(); engine = self.engine(provider)
        job = self.start(engine, reference_mode='text_only')
        self.assertEqual(job['references'], [])
        self.assertEqual(job['reference_mode'], 'text_only')
        self.assertTrue(any('không tìm nguồn web' in w for w in job['warnings']))
        final = self.finish(engine, job)
        self.assertEqual(len(final['cards']), 3)
        self.assertNotIn('VP02R', [task for task, _ in provider.payloads])
        checklist = next(p for task, p in provider.payloads if task == 'VP02')
        self.assertEqual(checklist['REFERENCE_DISCOVERY_CONFIG']['mode'], 'unavailable')
        self.assertEqual(set(checklist['REQUEST_METADATA']), {'request_id', 'revision'})

    def test_locked_group_can_use_explicit_changes_instead_of_custom(self):
        class Locked(Recorder):
            def structured_v2(self, task, *args, **kwargs):
                value, usage, metadata = super().structured_v2(task, *args, **kwargs)
                if task == 'VP02':
                    group = copy.deepcopy(value['groups'][0])
                    group.update(group_id='understood', status='locked', min=0, max=0, allows_custom=False, options=[])
                    value['groups'].append(group)
                return value, usage, metadata
        job = self.start(self.engine(Locked()))
        self.assertFalse(job['checklist']['groups'][-1]['allows_custom'])

    def test_basic_mode_rejects_model_invented_reference(self):
        class Invented(Recorder):
            def structured_v2(self, task, *args, **kwargs):
                value, usage, metadata = super().structured_v2(task, *args, **kwargs)
                if task == 'VP02':
                    value['references'] = [{'reference_id': 'invented', 'domains': ['open'], 'label': 'Unsourced', 'description': 'No tool evidence', 'url': 'https://example.org/unsupported', 'source_type': 'fashion', 'scope': 'Illustration', 'supporting_excerpt': None, 'discovery_status': 'not_found', 'preview_url': None}]
                return value, usage, metadata
        engine = self.engine(Invented())
        created = engine.create({'raw_prompt': RAW, 'reference_mode': 'text_only'})
        job = wait(engine, created['request_id'])
        self.assertEqual(job['status'], 'failed')
        self.assertEqual(job['references'], [])

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(); self.engines = []
    def tearDown(self):
        for engine in self.engines:
            engine.close()
        self.temp.cleanup()
    def engine(self, provider=None, directory=None):
        e = Engine(provider or Recorder(), directory or Path(self.temp.name) / str(len(self.engines)), allow_mock_requests=True)
        self.engines.append(e); return e
    def start(self, e, **options):
        response = e.create({'raw_prompt': RAW, **options})
        job = wait(e, response['request_id'])
        self.assertEqual(job['status'], 'awaiting_choices', job['error'])
        return job
    def choices(self, j, **kw):
        return {'revision': j['revision'], 'form_id': j['checklist']['form_id'], 'idempotency_key': str(uuid.uuid4()), 'selections': [{'group_id': 'exploration', 'option_ids': ['delegate'], 'custom_text': ''}], 'explicit_changes': [], **kw}
    def finish(self, e, j):
        e.selections(j['request_id'], self.choices(j)); result = wait(e, j['request_id'])
        self.assertEqual(result['status'], 'awaiting_image', result['error'])
        return result

    def test_design_story_calls_only_top_three_and_preserves_image_prompts(self):
        provider = Recorder(); e = self.engine(provider)
        final = self.finish(e, self.start(e))
        calls = [p for task, p in provider.payloads if task == 'VP09']
        self.assertEqual(len(calls), 3)
        self.assertEqual({p['CANDIDATE']['candidate_id'] for p in calls}, set(final['selected_prompt_ids']))
        original = {c['candidate_id']: c for c in final['prompt_pool']}
        for card in final['cards']:
            self.assertEqual(card['image_prompt'], original[card['candidate_id']]['image_prompt'])
            self.assertEqual(card['design_story']['content_hash'], card['content_hash'])
            self.assertEqual(card['design_story']['candidate_revision'], card['revision'])
            self.assertTrue(card['design_story']['origin_and_meaning'])
            self.assertTrue(card['design_story']['cultural_combination_warnings'])
            payload = next(p for p in calls if p['CANDIDATE']['candidate_id'] == card['candidate_id'])
            self.assertEqual(payload['CANDIDATE']['image_prompt'], card['image_prompt'])
            self.assertEqual(payload['CULTURE_REVIEW'], final['specialist_audits'][card['candidate_id']]['culture'])
        # Restart-style re-entry reattaches saved stories without another provider call.
        count = len(provider.payloads)
        for row in final['ranking']['ranked']:
            e._vp_design_story(final['request_id'], final['revision'], row['candidate'])
        self.assertEqual(len(provider.payloads), count)

    def test_restart_resumes_only_missing_design_story(self):
        e = self.engine(); final = self.finish(e, self.start(e))
        e.executor.shutdown(wait=True)
        job = e.store.get_job(final['request_id'])
        cid = job['cards'][-1]['candidate_id']
        del job['design_stories'][cid]
        for key, checkpoint in list(job['checkpoints'].items()):
            if checkpoint['task'] == 'VP09' and checkpoint['value']['candidate_id'] == cid:
                del job['checkpoints'][key]
                # Simulate one interrupted call that has not used the retry allowance.
                for record in job['call_records'].values():
                    if record['task_key'] == key:
                        record['status'] = 'interrupted'
        job['status'] = 'writing_design_stories'
        job.pop('image_workflow', None); job.pop('pending_manual', None)
        e.store.save_job(job); directory = e.store.directory
        e.store.close(); self.engines.remove(e)
        provider = Recorder(); restarted = self.engine(provider, directory)
        result = wait(restarted, job['request_id'])
        self.assertEqual(result['status'], 'awaiting_image', result['error'])
        self.assertEqual([task for task, payload in provider.payloads], ['VP09'])
        self.assertEqual(provider.payloads[0][1]['CANDIDATE']['candidate_id'], cid)
        self.assertTrue(all(card.get('design_story') for card in result['cards']))
        self.assertEqual(result['image_prompts'], final['image_prompts'])

    def test_design_story_rejects_wrong_candidate_without_claiming_complete(self):
        class WrongStory(Recorder):
            def structured_v2(self, task, *args, **kwargs):
                value, usage, metadata = super().structured_v2(task, *args, **kwargs)
                if task == 'VP09':
                    value['candidate_id'] = 'wrong-candidate'
                return value, usage, metadata
        e = self.engine(WrongStory()); job = self.start(e)
        e.selections(job['request_id'], self.choices(job)); final = wait(e, job['request_id'])
        self.assertEqual(final['status'], 'failed')
        self.assertEqual(final['failed_stage'], 'writing_design_stories')
        self.assertEqual(final['error']['code'], 'semantic_invalid')
        self.assertTrue(all('design_story' not in c for c in final['cards']))
        self.assertNotIn('pending_manual', final)

    def test_no_audit_mode_stores_uploaded_image_without_inspection(self):
        from test_manual_workflow import image
        engine = self.engine()
        def unexpected_audit(*args, **kwargs):
            raise AssertionError("No image API inspection is allowed")
        engine._inspect_image = unexpected_audit
        job = self.finish(engine, self.start(engine, audit_mode='none', reference_mode='text_only'))
        engine.choose_image_candidate(job['request_id'], {'revision': job['revision'], 'step_id': job['pending_manual']['step_id'], 'candidate_id': job['cards'][0]['candidate_id']})
        job = engine.store.get_job(job['request_id'])
        engine.submit_image(job['request_id'], {'revision': job['revision'], 'step_id': job['pending_manual']['step_id'], 'image': image(), 'filename': 'No audit.png'})
        final = wait(engine, job['request_id'])
        self.assertEqual(final['status'], 'complete')
        self.assertEqual(final['audit_mode'], 'none')
        self.assertEqual(final['artifacts'][-1]['check_status'], 'unverified')
        self.assertEqual(final['selected_artifact_ids'], [])
        self.assertEqual(final['output_artifact_ids'], [final['artifacts'][-1]['artifact_id']])

    def test_hundred_call_notice_is_persisted_without_stopping_workflow(self):
        import io
        provider = GeminiProvider('fake-test-key', session_call_limit=1)
        fixture = Recorder()
        provider._calls = 99
        def structured(task, system, prompt, schema, payload, timeout, config):
            provider._request(provider.text_model, {}, timeout)
            return fixture.structured_v2(task, system, prompt, schema, payload, timeout, config)
        provider.structured_v2 = structured
        e = self.engine(provider)
        with patch('urllib.request.urlopen', side_effect=lambda *a, **k: io.BytesIO(b'{}')):
            j = self.start(e)
            self.assertEqual(len(j['api_call_warnings']), 1)
            self.assertIn('100', j['api_call_warnings'][0])
            result = self.finish(e, j)
        self.assertEqual(result['status'], 'awaiting_image')
        self.assertEqual(len(result['api_call_warnings']), 1)
        self.assertIn(result['api_call_warnings'][0], result['warnings'])
        self.assertGreater(provider.api_call_usage['calls'], 100)

    def test_open_semantics_raw_examples_gender_and_new_domain(self):
        e = self.engine(OpenAtoms()); j = self.start(e)
        self.assertEqual(j['raw_prompt'], RAW)
        self.assertEqual(j['clean_prompt']['clean_text'], RAW)
        final = self.finish(e, j); brief = final['resolved_brief']
        atoms = {a['atom_id']: a for a in brief['atoms']}
        self.assertEqual(atoms['A2']['intent_type'], 'example')
        self.assertNotIn('A2', brief['locked_atom_ids'])
        self.assertEqual(atoms['A6']['intent_type'], 'avoid')
        self.assertIn('Công nghệ may mặc', [d['label'] for d in brief['domains']])
        for c in final['prompt_pool']:
            self.assertIn('Âu phục', c['image_prompt']); self.assertIn('túi cảm biến', c['image_prompt'])
            self.assertNotIn('cô dâu', c['image_prompt'])
            self.assertEqual({x['atom_id'] for x in c['locked_coverage']}, set(brief['locked_atom_ids']))

    def test_baseline_barrier_independent_calls_budget_and_unmodified_prompts(self):
        p = Recorder(); e = self.engine(p); final = self.finish(e, self.start(e))
        tasks = [t for t, _ in p.payloads]
        first_audit = min(tasks.index(t) for t in ('VP05', 'VP06', 'VP07'))
        self.assertEqual(tasks[:first_audit].count('VP04'), 2)
        self.assertEqual(final['pool_barrier']['count'], 5)
        self.assertEqual(final['pool_barrier']['target'], 5)
        self.assertEqual(final['design_progress']['pool_target'], 5)
        self.assertEqual(sorted(len(payload['CANDIDATE_SLOTS']['slots']) for task, payload in p.payloads if task == 'VP04'), [2, 3])
        self.assertEqual(final['supplemental_batches'], 0)
        self.assertEqual(final['metrics']['design']['attempts'], 17)
        self.assertEqual(final['metrics']['media']['attempts'], 0)
        self.assertEqual(final['metrics']['actual_api_calls'], 0)
        self.assertEqual(len(final['prompt_pool']), 5)
        self.assertEqual(len({json.dumps(c['design_sections']) for c in final['prompt_pool']}), 5)
        for task, payload in p.payloads:
            if task in vp.ROLES:
                self.assertNotIn('VALIDATED_SPECIALIST_AUDITS', payload)
                self.assertNotIn('specialist_audits', json.dumps(payload))
            if task == 'VP08':
                for reviews in payload['VALIDATED_SPECIALIST_AUDITS'].values():
                    self.assertEqual(set(reviews), {'fashion', 'culture', 'art'})
        originals = {c['candidate_id']: c['image_prompt'] for c in final['prompt_pool']}
        for c, entry in zip(final['cards'], final['image_prompts']):
            self.assertEqual(c['image_prompt'], originals[c['candidate_id']]); self.assertEqual(entry['prompt'], c['image_prompt'])
        report = user_report(final, e.policy)
        self.assertEqual(len(report['candidate_audits']), 20)
        self.assertEqual(report['api']['totals']['actual'], 0)
        self.assertNotIn('điểm gần', report['selection_reason'])

    def test_no_audit_when_second_generation_is_still_inflight(self):
        release = threading.Event(); entered = threading.Event()
        class Slow(Recorder):
            def structured_v2(self, task, system, prompt, schema, payload, timeout, config):
                if task == 'VP04' and payload['CANDIDATE_SLOTS']['batch_id'] == 'B2':
                    entered.set(); release.wait(3)
                return super().structured_v2(task, system, prompt, schema, payload, timeout, config)
        p = Slow(); e = self.engine(p); j = self.start(e)
        e.selections(j['request_id'], self.choices(j)); self.assertTrue(entered.wait(2))
        self.assertFalse(any(t in vp.ROLES for t, _ in p.payloads))
        release.set(); self.assertEqual(wait(e, j['request_id'])['status'], 'awaiting_image')

    def test_alias_conflict_workflow_old_and_invalid_types_rejected(self):
        e = self.engine()
        for p in ({'input': RAW, 'raw_prompt': 'khác'}, {'raw_prompt': RAW, 'workflow_version': True}, {'raw_prompt': RAW, 'workflow_version': 1}, {'raw_prompt': RAW, 'creative_level': 'anything'}):
            with self.assertRaises(ArenaError): e.create(p)
        response = e.create({'input': RAW, 'render_image': False}); j = wait(e, response['request_id']); self.assertEqual(j['workflow_version'], 2)

    def test_no_default_choices_multiple_ai_custom_stale_form_and_duplicate(self):
        e = self.engine(); j = self.start(e)
        invalid = [self.choices(j, selections=[]), self.choices(j, selections=[{'group_id': 'exploration', 'option_ids': ['quiet', 'delegate'], 'custom_text': ''}]), self.choices(j, selections=[{'group_id': 'exploration', 'option_ids': ['delegate'], 'custom_text': 'Ý riêng'}]), self.choices(j, form_id='old'), self.choices(j, revision=0)]
        for payload in invalid:
            with self.assertRaises(ArenaError): e.selections(j['request_id'], payload)
        payload = self.choices(j); first = e.selections(j['request_id'], payload); second = e.selections(j['request_id'], payload)
        self.assertTrue(second['deduplicated']); self.assertEqual(first['revision'], second['revision'])
        changed = dict(payload, explicit_changes=[{'atom_id': 'raw', 'replacement_text': 'khác', 'confirmed': 'yes'}])
        with self.assertRaises(ArenaError): e.selections(j['request_id'], changed)

    def test_custom_and_explicit_change_provenance(self):
        e = self.engine(OpenAtoms()); j = self.start(e)
        payload = self.choices(j, selections=[{'group_id': 'exploration', 'option_ids': [], 'custom_text': 'Tỉ lệ đường cắt theo sóng âm'}], explicit_changes=[{'atom_id': 'A1', 'replacement_text': 'Chỉ màu tím', 'confirmed': 'yes'}])
        e.selections(j['request_id'], payload); final = wait(e, j['request_id'])
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        brief = final['resolved_brief']
        self.assertNotIn('A1', brief['locked_atom_ids'])
        self.assertIn('change-A1', brief['locked_atom_ids'])
        atom = next(a for a in brief['atoms'] if a['atom_id'] == 'change-A1')
        self.assertEqual(atom['source_refs'][0]['quote'], 'Chỉ màu tím')
        self.assertEqual(brief['decisions'][0]['custom_text'], 'Tỉ lệ đường cắt theo sóng âm')

    def test_schema_rejects_nonfinite_bool_string_and_duplicate_array(self):
        contracts = Contracts(vp.DATA / 'contracts.json')
        for v in (True, 3.5, -1, 6, float('nan'), float('inf')):
            with self.assertRaises(ArenaError):
                contracts.validate('CriterionRating', {'criterion_id': 'x', 'applicable': True, 'rating': v, 'reason': 'Lý do'})
        with self.assertRaises(ArenaError): contracts.validate('SourceRef', {'turn_id': 'T1', 'quote': ''})
        with self.assertRaises(ArenaError): contracts.validate('Selection', {'group_id': 'g', 'option_ids': ['x','x'], 'custom_text': ''})

    def test_wire_schema_preserves_property_names_and_local_constraints(self):
        schema = {'type': 'object', 'properties': {
            'minLength': {'type': 'string', 'minLength': 1},
            'rows': {'type': 'array', 'minItems': 1, 'maxItems': 100,
                     'uniqueItems': True, 'items': {'type': 'string', 'maxLength': 80}},
        }, 'required': ['minLength', 'rows'], 'additionalProperties': False}
        original = copy.deepcopy(schema)
        wire = gemini_wire_schema(schema)
        self.assertEqual(schema, original)
        self.assertIn('minLength', wire['properties'])
        self.assertNotIn('minLength', wire['properties']['minLength'])
        self.assertIn('minLength=1', wire['properties']['minLength']['description'])
        self.assertNotIn('maxItems', wire['properties']['rows'])
        self.assertIn('maxItems=100', wire['properties']['rows']['description'])
        self.assertEqual(wire['required'], schema['required'])
        self.assertIs(wire['additionalProperties'], False)
        contracts = Contracts(vp.DATA / 'contracts.json')
        contracts.schema('CleanPrompt')  # Full local contract remains unchanged.
        with self.assertRaises(ArenaError):
            contracts.validate('Selection', {'group_id': 'g', 'option_ids': ['x', 'x'], 'custom_text': ''})

    def test_quota_without_retry_hint_is_not_retried_or_assumed_invalid_key(self):
        import io, urllib.error
        provider = GeminiProvider('injected-quota-test-key')
        denial = {'error': {'message': 'You exceeded your current quota', 'status': 'RESOURCE_EXHAUSTED',
                            'details': [{'@type': 'type.googleapis.com/google.rpc.Help', 'links': []}]}}
        error = urllib.error.HTTPError('https://example.invalid', 429, 'quota', {}, io.BytesIO(json.dumps(denial).encode()))
        with patch('urllib.request.urlopen', side_effect=error):
            with self.assertRaises(ProviderError) as caught:
                provider._request(provider.text_model, {'tools': [{'googleSearch': {}}]}, 5)
        self.assertEqual(caught.exception.code, 'google_http_429')
        self.assertFalse(caught.exception.retryable)
        self.assertTrue(provider.configured)
        self.assertEqual(google_retry_delay({'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': '23s'}]}), 23)
        for value in ('NaNs', 'infs', '-1s', 'nonsense'):
            self.assertIsNone(google_retry_delay({'details': [{'@type': 'type.googleapis.com/google.rpc.RetryInfo', 'retryDelay': value}]}))

    def test_quote_cannot_fix_typo_accents_or_merge_disjoint_segments(self):
        for quote in ('Au phục', 'Âu phục xanh', 'không chỉ định giới tính; thêm túi cảm biến'):
            with self.assertRaises(ArenaError): vp.quote_ref({'turn_id': 'T1', 'quote': quote}, [{'id': 'T1', 'text': RAW}])
        self.assertEqual(vp.quote_ref({'turn_id': 'T1', 'quote': 'Âu phục'}, [{'id': 'T1', 'text': RAW}])['start'], 0)

    def test_creative_level_derives_audit_profile_and_ignores_client_override(self):
        e = self.engine()
        for level, expected, supplied in [('explore', 'creative', 'balanced'), ('moderate', 'balanced', 'creative'), ('balanced', 'balanced', 'invalid')]:
            created = e.create({'raw_prompt': RAW, 'creative_level': level, 'scoring_profile': supplied})
            job = wait(e, created['request_id'])
            self.assertEqual(job['scoring_profile'], expected)

    def test_image_audit_uses_derived_creativity_policy(self):
        e = self.engine(); job = self.start(e)
        artifact = {'artifact_id': 'image', 'hash': 'hash', 'parent_artifact_id': None}
        job['brief'] = {'hard_constraints': []}; job['artifacts'] = []
        payload = e._image_audit_payload(job, {}, {'rules': []}, artifact)
        self.assertEqual(payload['AUDIT_POLICY']['profile'], 'creative')
        self.assertIn('Ưu tiên sáng tạo', e._image_audit_context(payload))
        job['creative_level'] = 'moderate'
        payload = e._image_audit_payload(job, {}, {'rules': []}, artifact)
        self.assertEqual(payload['AUDIT_POLICY']['profile'], 'balanced')

    def test_checklist_allows_fewer_contextual_options_and_requires_ai_and_custom(self):
        e = self.engine(); job = self.start(e)
        checked = copy.deepcopy(job['checklist']); group = checked['groups'][0]
        vp.validate_checklist(checked, job, checked['form_id'], [])
        self.assertEqual(sum(not o['is_ai_delegate'] for o in group['options']), 5)
        for concrete_count in (4, 3, 1):
            group['options'] = [o for o in job['checklist']['groups'][0]['options'] if o['is_ai_delegate']] + [o for o in job['checklist']['groups'][0]['options'] if not o['is_ai_delegate']][:concrete_count]
            vp.validate_checklist(checked, job, checked['form_id'], [])
        group['options'] = [o for o in group['options'] if o['is_ai_delegate']]
        with self.assertRaises(ArenaError): vp.validate_checklist(checked, job, checked['form_id'], [])
        checked = copy.deepcopy(job['checklist'])
        checked['groups'][0]['options'][0]['is_ai_delegate'] = False
        with self.assertRaises(ArenaError): vp.validate_checklist(checked, job, checked['form_id'], [])
        checked = copy.deepcopy(job['checklist']); checked['groups'][0]['allows_custom'] = False
        with self.assertRaises(ArenaError): vp.validate_checklist(checked, job, checked['form_id'], [])

    def test_dependency_and_exclusion_validation(self):
        e = self.engine(); j = self.start(e); checklist = j['checklist']; group = checklist['groups'][0]
        child = copy.deepcopy(group); child.update(group_id='child', depends_on=[{'group_id': 'exploration', 'option_ids': ['quiet']}])
        for opt in child['options']: opt['option_id'] = 'child-' + opt['option_id']
        checklist['groups'].append(child)
        selected = self.choices(j, selections=[{'group_id':'exploration','option_ids':['delegate'],'custom_text':''},{'group_id':'child','option_ids':['child-quiet'],'custom_text':''}])
        with self.assertRaises(ArenaError): vp.validate_selections(selected,j,e.vp_contracts)
        selected['selections'][0]['option_ids']=['quiet']; vp.validate_selections(selected,j,e.vp_contracts)
        group['options'][1]['incompatible_option_ids']=['child-quiet']
        vp.validate_selections(selected,j,e.vp_contracts)  # Legacy metadata cannot block choices.
        child['depends_on']=[{'group_id':'exploration','option_ids':['quiet']}]
        group['depends_on']=[{'group_id':'child','option_ids':['child-quiet']}]
        with self.assertRaises(ArenaError): vp.validate_checklist(checklist,j,checklist['form_id'],[])

    def test_grounding_metadata_not_json_label_establishes_reference_provenance(self):
        ref = {'reference_id':'r','domains':['open'],'label':'Một nguồn','description':'Mô tả','url':'https://museum.vn/item','preview_url':'https://museum.vn/guessed.jpg','source_type':'museum','scope':'Một hiện vật','supporting_excerpt':'Đoạn đọc được','discovery_status':'tool_grounded','discovered_at':'2026-10-03','tool_citation_ids':['fake']}
        self.assertEqual(vp.normalize_references([ref],{})[0]['discovery_status'],'unconfirmed')
        self.assertIsNone(vp.normalize_references([ref],{})[0]['supporting_excerpt'])
        metadata={'urlContextMetadata':{'urlMetadata':[{'retrievedUrl':ref['url'],'urlRetrievalStatus':'URL_RETRIEVAL_STATUS_SUCCESS'}]}}
        normalized=vp.normalize_references([ref],metadata)[0]
        self.assertEqual(normalized['tool_citation_ids'],['url:0']);self.assertIsNone(normalized['preview_url'])
        with self.assertRaises(ArenaError): vp.normalize_references([dict(ref,url='javascript:alert(1)')],metadata)
        failed={'urlContextMetadata':{'urlMetadata':[{'retrievedUrl':ref['url'],'urlRetrievalStatus':'URL_RETRIEVAL_STATUS_ERROR'}]}}
        self.assertEqual(vp.normalize_references([ref],failed)[0]['discovery_status'],'unconfirmed')
        search={'groundingMetadata':{'groundingChunks':[{'web':{'uri':ref['url']}}]}}
        searched=vp.normalize_references([ref],search)[0]
        self.assertEqual(searched['discovery_status'],'tool_grounded');self.assertIsNone(searched['supporting_excerpt']);self.assertIsNone(searched['preview_url'])

    def test_split_reference_branch_includes_three_story_attempts(self):
        e=self.engine();e.vp_config['reference_discovery']='split'
        final=self.finish(e,self.start(e))
        self.assertEqual(final['metrics']['design']['attempts'],17)
        self.assertNotIn('VP02R',[t['task'] for t in final['trace']])

    def test_disabled_discovery_never_enters_tools_fallback(self):
        class Reject(Recorder):
            def structured_v2(self,task,system,prompt,schema,payload,timeout,config):
                if task=='VP02' and config['web_tools']:
                    raise ProviderError('google_http_400','Tools with response schema not supported')
                return super().structured_v2(task,system,prompt,schema,payload,timeout,config)
        e=self.engine(Reject());j=self.start(e)
        self.assertFalse(j.get('reference_split', False));self.assertNotIn('VP02R',[t['task'] for t in j['trace']])

    def test_tools_failure_is_not_a_manual_catalog_fallback(self):
        class Unavailable(Recorder):
            def structured_v2(self,task,*args,**kwargs):
                if task=='VP02':raise ProviderError('google_http_403','Search unavailable')
                return super().structured_v2(task,*args,**kwargs)
        e=self.engine(Unavailable());r=e.create({'raw_prompt':RAW});j=wait(e,r['request_id'])
        self.assertEqual(j['status'],'failed');self.assertEqual(j['references'],[])
        self.assertEqual(j['error']['code'],'google_http_403')

    def test_role_hash_criteria_severity_and_source_scores_cannot_change(self):
        e=self.engine();j=self.finish(e,self.start(e));c=j['prompt_pool'][0];brief=j['resolved_brief']
        audit=copy.deepcopy(j['specialist_audits'][c['candidate_id']]['fashion']);audit.pop('score')
        checks=vp.expected_checks(brief,[c],'fashion');rubric=vp.rubric(e.vp_config,'fashion',brief)
        for mutation in ('hash','role','criterion','severity','quote','applicability'):
            bad=copy.deepcopy(audit)
            if mutation=='hash':bad['content_hash']='0'*64
            if mutation=='role':bad['role']='art'
            if mutation=='criterion':bad['criterion_ratings'][0]['criterion_id']='extra'
            if mutation=='severity':bad['checks'][0]['severity']='soft'
            if mutation=='quote':bad['checks'][0]['prompt_quote']='Không có trong prompt'
            if mutation=='applicability':bad['criterion_ratings'][0].update(applicable=False,rating=None)
            with self.assertRaises(ArenaError):vp.validate_specialists({'role':'fashion','audits':[bad]},[c],checks,'fashion',rubric,[])
        harmony=copy.deepcopy(j['harmony_audits'][c['candidate_id']]);harmony['source_scores']['fashion']=0
        with self.assertRaises(ArenaError):vp.validate_harmony({'audits':[harmony]},[c],j['specialist_audits'],e.vp_config,brief,'creative')

    def test_api_totals_preserved_without_backend_correction(self):
        class BadMath(Recorder):
            def structured_v2(self,task,*args,**kwargs):
                v,u,m=super().structured_v2(task,*args,**kwargs)
                if task=='VP08':
                    for a in v['audits']:a['harmony_score']=2;a['proposed_total']=3
                return v,u,m
        e=self.engine(BadMath());j=self.finish(e,self.start(e))
        for card in j['cards']:
            self.assertIsNone(card['specialist_scores']['culture'])
            self.assertEqual(card['harmony']['harmony_score'],2)
            self.assertEqual(card['harmony']['reported_total'],3)
            self.assertEqual(card['score'],3)
        self.assertEqual(vp.total_score({'fashion':82,'culture':78,'art':90},84,e.vp_config['profiles']['creative']),84.4)

    def test_api_uncertain_is_displayed_without_backend_rejection(self):
        class Uncertain(Recorder):
            def structured_v2(self,task,*args,**kwargs):
                v,u,m=super().structured_v2(task,*args,**kwargs)
                if task=='VP05':
                    for a in v['audits']:a['checks'][0]['status']='uncertain'
                return v,u,m
        p=Uncertain();e=self.engine(p);j=self.start(e);e.selections(j['request_id'],self.choices(j));final=wait(e,j['request_id'])
        self.assertEqual(final['status'],'awaiting_image');self.assertEqual(len(final['cards']),3)
        self.assertEqual(final['supplemental_batches'],0);self.assertEqual(len(final['prompt_pool']),5)
        self.assertTrue(all(c['specialist_reviews']['fashion']['checks'][0]['status']=='uncertain' for c in final['cards']))

    def test_top_three_strict_score_even_similar_and_tie_id(self):
        e=self.engine();j=self.finish(e,self.start(e));harmonies=j['harmony_audits'];pool=j['prompt_pool']
        for i,c in enumerate(pool):
            h=harmonies[c['candidate_id']];h['score_100']=90-i*.1
        ranking=vp.rank(pool,j['specialist_audits'],harmonies,e.vp_config)
        self.assertEqual([r['candidate']['candidate_id'] for r in ranking['ranked']],[c['candidate_id'] for c in pool[:3]])
        for h in harmonies.values():h['score_100']=90
        ranking=vp.rank(list(reversed(pool)),j['specialist_audits'],harmonies,e.vp_config)
        self.assertEqual([r['candidate']['candidate_id'] for r in ranking['ranked']],sorted(c['candidate_id'] for c in pool)[:3])

    def test_content_change_invalidates_score(self):
        e=self.engine();j=self.finish(e,self.start(e));c=j['prompt_pool'][0]
        c['art_summary']+=' CHANGED'
        ranking=vp.rank(j['prompt_pool'],j['specialist_audits'],j['harmony_audits'],e.vp_config)
        self.assertIn(c['candidate_id'],[r['candidate_id'] for r in ranking['rejected']])

    def test_media_budget_stays_separate_after_design_and_wait(self):
        e=self.engine();j=self.finish(e,self.start(e));time.sleep(.03)
        e.choose_image_candidate(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'candidate_id':j['cards'][2]['candidate_id']})
        j=e.store.get_job(j['request_id']);design_seconds=j['metrics']['design']['active_seconds']
        e.submit_image(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'image':image(),'filename':'fixture.png'})
        final=wait(e,j['request_id']);self.assertEqual(final['status'],'complete',final['error'])
        self.assertEqual(final['metrics']['design']['attempts'],17)
        self.assertEqual(final['metrics']['media']['attempts'],1)
        self.assertEqual(final['metrics']['design']['active_seconds'],design_seconds)
        self.assertEqual(final['artifacts'][-1]['candidate_id'],j['cards'][2]['candidate_id'])
        budget=Budget(final,e.policy,'media');self.assertEqual(budget.calls_remaining(),12)

    def test_cancel_late_responses_do_not_publish_checkpoint(self):
        entered=threading.Event();release=threading.Event()
        class Slow(Recorder):
            def structured_v2(self,task,*args,**kwargs):
                if task=='VP01':entered.set();release.wait(3)
                return super().structured_v2(task,*args,**kwargs)
        e=self.engine(Slow());r=e.create({'raw_prompt':RAW});self.assertTrue(entered.wait(2));e.cancel(r['request_id']);release.set();e.executor.shutdown(wait=True)
        j=e.store.get_job(r['request_id']);self.assertEqual(j['status'],'cancelled');self.assertEqual(j['checkpoints'],{})
        self.assertEqual(j['metrics']['design']['attempts'],1);self.assertTrue(any(c['status']=='discarded' for c in j['call_records'].values()))

    def test_recovery_reuses_valid_specialists_and_generation(self):
        e=self.engine();final=self.finish(e,self.start(e));e.executor.shutdown(wait=True)
        job=e.store.get_job(final['request_id']);job['status']='specialist_auditing';job.pop('image_workflow',None);job.pop('pending_manual',None)
        batch=job['generation_batches']['B2']['candidates']
        for c in batch:job['specialist_audits'][c['candidate_id']].pop('culture')
        for key, checkpoint in list(job['checkpoints'].items()):
            if checkpoint['task']=='VP06' and checkpoint['value']['audits'][0]['candidate_id'] in {c['candidate_id'] for c in batch}:
                del job['checkpoints'][key]
                for record in job['call_records'].values():
                    if record['task_key']==key:record['status']='interrupted'
        e.store.save_job(job);directory=e.store.directory;e.close();self.engines.remove(e)
        p=Recorder();restarted=self.engine(p,directory);result=wait(restarted,job['request_id'])
        self.assertEqual(result['status'],'awaiting_image',result['error'])
        self.assertEqual([t for t,_ in p.payloads],['VP06'])
        self.assertEqual(result['metrics']['design']['attempts'],18)

    def test_reopen_saved_choices_reuses_options_without_provider_calls(self):
        provider = Recorder(); e = self.engine(provider)
        job = self.finish(e, self.start(e)); original = copy.deepcopy(job)
        calls = len(provider.payloads)
        result = e.reopen_choices(job['request_id'], {'revision': job['revision'], 'reuse_checklist': True})
        reopened = e.store.get_job(job['request_id'])
        self.assertEqual(result['status'], 'awaiting_choices')
        self.assertEqual(len(provider.payloads), calls)
        self.assertEqual(reopened['checklist']['groups'], original['checklist']['groups'])
        self.assertEqual(reopened['choice_restore'], original['choices'])
        self.assertEqual(reopened['previous_selection_snapshot']['choices'], original['choices'])
        self.assertNotEqual(reopened['checklist']['form_id'], original['checklist']['form_id'])
        self.assertEqual(reopened['checklist']['clean_prompt']['revision'], reopened['revision'])
        with self.assertRaises(ArenaError): e.selections(job['request_id'], self.choices(original))
        updated = self.choices(reopened, selections=[{'group_id':'exploration','option_ids':[], 'custom_text':'Điểm nhấn mới'}])
        e.selections(job['request_id'], updated)
        final = wait(e, job['request_id'])
        self.assertEqual(final['status'], 'awaiting_image', final['error'])
        self.assertEqual(final['choices']['selections'][0]['custom_text'], 'Điểm nhấn mới')
        self.assertEqual(final['design_history'][-1]['choices'], original['choices'])

    def test_revise_archives_design_rejects_old_form_and_changes_ids(self):
        e=self.engine();j=self.finish(e,self.start(e));oldcards=copy.deepcopy(j['cards'])
        e.reopen_choices(j['request_id'],{'revision':j['revision']});new=wait(e,j['request_id'])
        self.assertEqual(new['status'],'awaiting_choices',new['error']);self.assertEqual(new['cards'],[])
        self.assertEqual(new['design_history'][0]['cards'],oldcards)
        with self.assertRaises(ArenaError):e.selections(new['request_id'],self.choices(j))
        newer=self.finish(e,new)
        self.assertFalse(set(c['candidate_id'] for c in oldcards)&set(c['candidate_id'] for c in newer['cards']))

    def test_real_provider_wire_tools_tokens_temperature_and_metadata_without_network(self):
        provider=GeminiProvider('unit-test-placeholder');body_seen=[]
        result={'candidates':[{'finishReason':'STOP','content':{'parts':[{'text':'{"references":[],"unresolved_reference_needs":[]}'},{'text':'secret-thought','thought':True}]},'groundingMetadata':{'webSearchQueries':['vietnam clothing']},'urlContextMetadata':{}}], 'usageMetadata':{'totalTokenCount':20},'modelVersion':'wire-fixture'}
        with patch.object(provider,'_request',side_effect=lambda model,body,timeout:(body_seen.append(body) or result)):
            v,u,m=provider.structured_v2('VP02R','system','prompt',{'type':'object'}, {}, 20, {'max_output_tokens':16000,'web_tools':True,'structured':False})
        body=body_seen[0];self.assertNotIn('tools',body);self.assertNotIn('temperature',body['generationConfig'])
        self.assertNotIn('responseFormat',body['generationConfig']);self.assertEqual(u['totalTokenCount'],20)
        self.assertEqual(m['groundingMetadata']['webSearchQueries'],['vietnam clothing'])
        images = [{'mime_type': 'image/png', 'data': 'b3V0cHV0'}, {'mime_type': 'image/png', 'data': 'b3JpZ2luYWw='}]
        with patch.object(provider, '_request', side_effect=lambda model,body,timeout:(body_seen.append(body) or result)):
            provider.structured('P06', 'system', 'prompt', {'type':'object'}, {}, 20, images=images)
        self.assertNotIn('temperature', body_seen[-1]['generationConfig'])
        self.assertEqual([p['inlineData']['data'] for p in body_seen[-1]['contents'][0]['parts'] if 'inlineData' in p], [i['data'] for i in images])

    def test_transport_observer_counts_failed_attempts_and_parallel_calls(self):
        class Observed(Recorder):
            name = 'gemini'; text_model = 'gemini-3.5-flash-lite'; configured = True
            def __init__(self):
                super().__init__(); self.local=threading.local(); self.failed=False
            def prepare_attempt(self): self.local.call_id=None
            def observe_attempt(self,callback):self.local.observer=callback
            def structured_v2(self,task,*args,**kwargs):
                self.local.call_id=str(uuid.uuid4());self.local.observer(self.local.call_id)
                if task=='VP01' and not self.failed:
                    self.failed=True;raise ProviderError('google_http_500','Injected transport failure',retryable=True)
                return super().structured_v2(task,*args,**kwargs)
        e=self.engine(Observed());j=self.finish(e,self.start(e))
        self.assertEqual(j['metrics']['actual_api_calls'],18)
        self.assertEqual(j['metrics']['design']['actual_api_calls'],18)
        self.assertEqual(j['metrics']['design']['attempts'],18)
        ids=[c['provider_call_id'] for c in j['call_records'].values()]
        self.assertEqual(len(ids),len(set(ids)))
        report=user_report(j,e.policy)
        self.assertEqual(report['api']['totals']['actual'],18)
        self.assertEqual(report['api']['totals']['failed'],1)
        self.assertEqual(report['api']['totals']['success'],17)

    def test_missing_specialist_never_gets_harmony_and_other_roles_persist(self):
        class BrokenCulture(Recorder):
            def structured_v2(self,task,system,prompt,schema,payload,timeout,config):
                if task=='VP06' and payload['CANDIDATE_BATCH'][0]['batch_id']=='B2':
                    raise ProviderError('google_http_403','Injected unavailable culture audit')
                return super().structured_v2(task,system,prompt,schema,payload,timeout,config)
        e=self.engine(BrokenCulture());j=self.finish(e,self.start(e))
        for c in j['generation_batches']['B2']['candidates']:
            self.assertEqual(set(j['specialist_audits'][c['candidate_id']]),{'fashion','art'})
            self.assertNotIn(c['candidate_id'],j['harmony_audits'])
        self.assertTrue(all(c['batch_id']=='B1' for c in j['cards']))

    def test_parallel_budget_reservation_never_overshoots(self):
        e=self.engine();j=self.start(e);e.vp_config['design_budget']['total_provider_calls_max']=6
        e.selections(j['request_id'],self.choices(j));result=wait(e,j['request_id'])
        self.assertLessEqual(result['metrics']['design']['attempts'],6)
        self.assertEqual(result['cards'],[])
        self.assertTrue(any('budget' in x.lower() for x in result['warnings']))

    def test_duplicate_plan_removes_only_actual_duplicate_after_highest_score(self):
        e=self.engine();j=self.finish(e,self.start(e));first,second=j['prompt_pool'][:2]
        second['design_sections']=copy.deepcopy(first['design_sections']);second['content_hash']=vp.content_hash(second)
        for a in j['specialist_audits'][second['candidate_id']].values():a['content_hash']=second['content_hash']
        j['harmony_audits'][second['candidate_id']]['content_hash']=second['content_hash']
        for cid,h in j['harmony_audits'].items():h['score_100']=71
        j['harmony_audits'][second['candidate_id']]['score_100']=99
        ranking=vp.rank(j['prompt_pool'],j['specialist_audits'],j['harmony_audits'],e.vp_config)
        self.assertEqual(ranking['ranked'][0]['candidate']['candidate_id'],second['candidate_id'])
        self.assertTrue(any(r['candidate_id']==first['candidate_id'] and 'Trùng' in r['reason'] for r in ranking['rejected']))

    def test_historical_missing_evidence_is_not_neutral_or_inspired(self):
        class Historical(Recorder):
            def structured_v2(self,task,*args,**kw):
                v,u,m=super().structured_v2(task,*args,**kw)
                if task=='VP03':v.update(historical_mode='historical',status='needs_evidence')
                return v,u,m
        e=self.engine(Historical());j=self.start(e);e.selections(j['request_id'],self.choices(j));result=wait(e,j['request_id'])
        self.assertEqual(result['status'],'needs_evidence');self.assertEqual(result['resolved_brief']['historical_mode'],'historical')
        self.assertEqual(result['prompt_pool'],[])
        brief=dict(result['resolved_brief'],status='ready')
        with self.assertRaises(ArenaError):vp.validate_resolved(brief,result)

    def test_retain_atoms_does_not_promote_preference_or_examples(self):
        e=self.engine(OpenAtoms());j=self.start(e);before=j['clean_prompt']['atoms'];after=copy.deepcopy(before)
        after[2]['intent_type']='must'
        with self.assertRaises(ArenaError):vp.retain_atoms(before,after)
        after=copy.deepcopy(before);after.pop()
        with self.assertRaises(ArenaError):vp.retain_atoms(before,after)
        after=copy.deepcopy(before);after[1]['meaning']='chỉ đỏ'
        with self.assertRaises(ArenaError):vp.retain_atoms(before,after)
        j=self.finish(e,j)
        for aid in ('A2','A4','A5'):
            brief=copy.deepcopy(j['resolved_brief']);brief['locked_atom_ids'].append(aid)
            with self.assertRaises(ArenaError):vp.validate_resolved(brief,j)
        brief=copy.deepcopy(j['resolved_brief']);brief['delegated_atom_ids'].append('A4')
        with self.assertRaises(ArenaError):vp.validate_resolved(brief,j)
        brief=copy.deepcopy(j['resolved_brief'])
        for atom in brief['atoms']:
            if atom['atom_id']=='decision-exploration':atom['source_refs']=[{'turn_id':'T1','quote':'để AI đề xuất'}]
        with self.assertRaises(ArenaError):vp.validate_resolved(brief,j)

    def test_guessed_claim_sources_cannot_pass_structure_or_culture_gates(self):
        e=self.engine();j=self.finish(e,self.start(e));candidate=copy.deepcopy(j['prompt_pool'][0]);candidate.pop('content_hash')
        candidate['claims']=[{'claim_id':'c','text':'Rồng Lý–Trần đã xác minh','source_id':'invented','reference_id':'invented','excerpt':'Fake','scope':'Lý–Trần'}]
        slots={'batch_id':candidate['batch_id'],'slots':[{'candidate_id':candidate['candidate_id'],'revision':j['revision']}]}
        with self.assertRaises(ArenaError):vp.validate_candidates({'candidates':[candidate],'limitations':[]},j,slots)

    def test_handoff_has_no_backend_output_hash_gate(self):
        e=self.engine();j=self.finish(e,self.start(e))
        with e.lock:
            j=e.store.get_job(j['request_id']);j['image_prompts'][0]['prompt']+=' unauthorized change';e.store.save_job(j)
        e.choose_image_candidate(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'candidate_id':j['cards'][0]['candidate_id']})

    def test_v2_two_image_edit_template_update_and_restart_preserve_original_behavior(self):
        e=self.engine();j=self.finish(e,self.start(e))
        e.choose_image_candidate(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'candidate_id':j['cards'][2]['candidate_id']})
        j=e.store.get_job(j['request_id'])
        e.submit_image(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'image':image(),'filename':'Original.png'})
        j=wait(e,j['request_id']);root=j['artifacts'][0]['artifact_id']
        for i in range(2):
            description={'instruction':'Đổi cổ áo theo nét xanh','keep':'Giữ phần còn lại','strokes':[{'tool':'sketch','color':'#2060df','width':.02,'points':[[.2,.3],[.4,.5]]}]}
            packet=e.image_edit_prompt(j['request_id'],dict(description,candidate_id=j['cards'][2]['candidate_id'],original=image(),guide=image('red')))
            self.assertEqual(packet['template_version'],'visual-edit-v2')
            self.assertLess(packet['prompt'].index('Ảnh 1'),packet['prompt'].index('Ảnh 2'))
            parent=j['artifacts'][-1]['artifact_id']
            e.submit_user_image_edit(j['request_id'],dict(description,revision=j['revision'],parent_artifact_id=parent,image=image('green'),filename='Edited.png',guide=image('red'),prompt=packet['prompt']))
            j=wait(e,j['request_id']);self.assertEqual(j['status'],'complete',j['error'])
            self.assertEqual(len(j['output_artifact_ids']),1);self.assertEqual(j['artifacts'][-1]['parent_artifact_id'],parent)
        directory=e.store.directory;e.close();self.engines.remove(e);e=self.engine(directory=directory)
        saved=e.store.get_job(j['request_id']);self.assertEqual(saved['output_artifact_ids'],j['output_artifact_ids']);self.assertEqual(saved['artifacts'][0]['artifact_id'],root)
        self.assertEqual(saved['metrics']['design']['attempts'],17)
        self.assertEqual(saved['metrics']['media']['attempts'],3)

    def test_image_audit_template_remains_consistent(self):
        from arena_backend.core import Prompts,KIT
        self.assertEqual(Prompts(KIT/'image-audit.md').templates['P06'],Prompts().templates['P06'])

    def test_revised_design_keeps_old_image_and_allows_new_candidate_selection(self):
        e=self.engine();j=self.finish(e,self.start(e))
        e.submit_image(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'image':image(),'filename':'Before.png'})
        j=wait(e,j['request_id']);old=copy.deepcopy(j['artifacts']);old_step=j['revision']
        e.reopen_choices(j['request_id'],{'revision':j['revision']});j=wait(e,j['request_id'])
        j=self.finish(e,j)
        self.assertEqual(j['artifacts'],old);self.assertEqual(j['output_artifact_ids'],[])
        cid=j['cards'][-1]['candidate_id']
        e.choose_image_candidate(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'candidate_id':cid})
        j=e.store.get_job(j['request_id'])
        with self.assertRaises(ArenaError):e.submit_image(j['request_id'],{'revision':old_step,'step_id':'old','image':image()})
        e.submit_image(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'image':image('green')})
        j=wait(e,j['request_id']);self.assertEqual(j['status'],'complete',j['error'])
        self.assertEqual(j['artifacts'][:len(old)],old);self.assertEqual(j['artifacts'][-1]['candidate_id'],cid)
        self.assertEqual(j['output_artifact_ids'],[j['artifacts'][-1]['artifact_id']])

    def test_media_restart_retains_separate_accounting_and_resumes_only_p06(self):
        e=self.engine();j=self.finish(e,self.start(e))
        e.choose_image_candidate(j['request_id'],{'revision':j['revision'],'step_id':j['pending_manual']['step_id'],'candidate_id':j['cards'][0]['candidate_id']})
        e.close();self.engines.remove(e)
        # Persist a real-shape interrupted media checkpoint without issuing HTTP.
        from arena_backend.core import Store
        store=Store(e.store.directory);j=store.get_job(j['request_id'])
        import base64
        aid=str(uuid.uuid4());encoded=image();raw=base64.b64decode(encoded['data'])
        (store.directory/(aid+'.image')).write_bytes(raw)
        j['artifacts']=[{'artifact_id':aid,'candidate_id':j['cards'][0]['candidate_id'],'mime_type':'image/png','hash':vp.digest(raw),'check_status':'unverified','url':'/artifacts/'+aid,'output_origin':'gemini_manual','parent_artifact_id':None}]
        j['image_workflow'].update(phase='audit',artifact_id=aid)
        j.pop('pending_manual',None);j['revision']+=1;j['status']='auditing_image'
        j['metrics']['media'].update(attempts=1,actual_api_calls=1)
        j['metrics']['actual_api_calls']=1;j['metrics']['provider_calls']+=1
        j['inflight']={'task':'P06','started_at':time.time()-2,'timeout_seconds':45,'provider_call_id':'injected-old'}
        store.save_job(j);store.close();p=Recorder();e=self.engine(p,directory=e.store.directory)
        j=wait(e,j['request_id']);self.assertEqual(j['status'],'complete',j['error'])
        self.assertEqual(j['metrics']['design']['attempts'],17);self.assertEqual(j['metrics']['media']['attempts'],2)
        self.assertEqual(j['metrics']['media']['actual_api_calls'],1);self.assertGreaterEqual(j['metrics']['media']['active_seconds'],2)
        self.assertFalse(p.payloads);self.assertNotIn('inflight',j)
        self.assertTrue(any(t.get('interrupted') and t.get('phase')=='media' for t in j['trace']))

    def test_incomplete_provider_output_retains_usage_and_tool_metadata(self):
        p=GeminiProvider(key='injected-test-key')
        result={'usageMetadata':{'totalTokenCount':99},'candidates':[{'finishReason':'MAX_TOKENS','groundingMetadata':{'webSearchQueries':['injected query']}}]}
        with patch.object(p,'_request',return_value=result):
            with self.assertRaises(ArenaError):p.structured_v2('VP02','system','prompt',{}, {},10,{'max_output_tokens':100,'structured':True})
        self.assertEqual(p.last_response_usage,{'totalTokenCount':99})
        self.assertEqual(p.last_response_metadata['groundingMetadata']['webSearchQueries'],['injected query'])

    def test_reference_detail_endpoint_returns_only_request_snapshot(self):
        import urllib.request,urllib.error
        e=self.engine();j=self.start(e);ref={'reference_id':'r','domains':['open'],'label':'Fixture metadata reference','description':'Fixture','url':None,'preview_url':None,'source_type':'illustration','scope':'Fixture','supporting_excerpt':None,'discovery_status':'not_found','discovered_at':'2026-10-03','tool_citation_ids':[]}
        with e.lock:
            j=e.store.get_job(j['request_id']);j['references']=[ref];e.store.save_job(j)
        server=create_server(e,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            url=f"http://127.0.0.1:{server.server_port}/requests/{j['request_id']}/references/r"
            self.assertEqual(json.load(urllib.request.urlopen(url)),ref)
            with self.assertRaises(urllib.error.HTTPError):urllib.request.urlopen(url+'-missing')
        finally:server.shutdown();server.server_close();thread.join()

    def test_http_selection_reference_and_config_endpoints(self):
        import urllib.request
        e=self.engine();j=self.start(e);server=create_server(e,port=0);thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            base=f'http://127.0.0.1:{server.server_port}'
            config=json.load(urllib.request.urlopen(base+'/config'));self.assertEqual(config['workflow_version'],2)
            request=urllib.request.Request(base+f"/requests/{j['request_id']}/selections", data=json.dumps(self.choices(j)).encode(),headers={'Content-Type':'application/json'},method='POST')
            result=json.load(urllib.request.urlopen(request));self.assertGreater(result['revision'],j['revision'])
            final=wait(e,j['request_id']);public=json.load(urllib.request.urlopen(base+f"/requests/{j['request_id']}"))
            for key in ('checkpoints', 'generation_inputs', 'generation_batches', 'design_history'):
                self.assertNotIn(key, public)
            self.assertIn('generation_inputs', e.store.get_job(j['request_id']))
            self.assertEqual(public['prompt_pool'], final['prompt_pool'])
            self.assertNotIn('checkpoints',public);self.assertEqual(len(public['cards']),3);self.assertEqual(public['user_report']['api']['totals']['actual'],0)
        finally:server.shutdown();server.server_close();thread.join()
