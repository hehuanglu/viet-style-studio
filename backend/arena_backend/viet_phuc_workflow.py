"""Revision-safe orchestration. All parallel calls checkpoint into fresh SQLite jobs."""
import copy
import time
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

from .core import ArenaError, Budget, Contracts, digest, read_json, require
from .providers import ProviderError
from . import viet_phuc as vp
from .viet_phuc_adapter import adapt


class VietPhucWorkflow:
    def _assert_v2_prompts(self, job):
        # Output acceptance belongs to API tasks from VP04 onward.
        return

    def choose_image_candidate(self, request_id, payload):
        with self.lock:
            job = self.store.get_job(request_id)
            if job.get('workflow_version') != 2:
                return super().choose_image_candidate(request_id, payload)
            self._assert_v2_prompts(job)
            self._pending(job, payload, {'awaiting_image'})
            current_ids = {p['candidate_id'] for p in job['image_prompts']}
            require(not any(a['candidate_id'] in current_ids for a in job['artifacts']),
                    'Chọn phương án trước khi gửi ảnh đầu tiên của thiết kế này', 'image_selection_started', 409)
            cid = payload.get('candidate_id')
            entry = next((p for p in job['image_prompts'] if p['candidate_id'] == cid), None)
            require(entry is not None, 'Phương án không thuộc yêu cầu này', 'invalid_candidate')
            job['image_target_ids'] = [cid]
            job['compiled_image_prompt'] = entry['prompt']
            job['image_workflow'] = {'phase': 'generate', 'prompt': entry['prompt'], 'parent_artifact_id': None,
                                     'candidate_id': cid, 'candidate_index': 0}
            job.pop('pending_manual', None)
            self._journal(job, 'manual', 'Chọn phương án để tạo ảnh', entry['title'])
            self._wait_manual(job, 'generate', entry['prompt'], candidate_id=cid, candidate_index=0)
            self.store.save_job(job)
            return {'request_id': request_id, 'status': job['status'], 'revision': job['revision']}

    def image_edit_prompt(self, request_id, payload):
        with self.lock:
            self._assert_v2_prompts(self.store.get_job(request_id))
            return super().image_edit_prompt(request_id, payload)

    def _image_candidate(self, job):
        self._assert_v2_prompts(job)
        return super()._image_candidate(job)

    def _init_v2(self):
        self.vp_config = read_json(vp.DATA / 'config.json')
        for key, values in self.runtime_config.items():
            self.vp_config[key].update(values)
        if self.design_attempts_override is not None:
            self.vp_config['design_budget']['total_provider_calls_max'] = self.design_attempts_override
            self.vp_config['status'] = 'explicit_runtime_budget_experiment'
        self.vp_contracts = Contracts(vp.DATA / 'contracts.json')
        self.vp_prompts = vp.VPPrompts()
        self.vp_slots = threading.BoundedSemaphore(3)
        self.vp_version = digest({'config': self.vp_config, 'contracts': self.vp_contracts.document,
                                  'templates': self.vp_prompts.version, 'code': self.cache_version})

    def _create_v2(self, payload):
        require(isinstance(payload, dict), 'Body phải là object JSON')
        raw = payload.get('raw_prompt', payload.get('input'))
        require(isinstance(raw, str) and bool(raw.strip()) and len(raw) <= 6000, 'raw_prompt phải là chuỗi 1–6000 ký tự')
        require(not ('input' in payload and 'raw_prompt' in payload) or payload['input'] == raw, 'input và raw_prompt khác nhau')
        require(payload.get('creative_level', 'explore') in ('moderate', 'balanced', 'explore'), 'Mức sáng tạo không hợp lệ')
        require(payload.get('image_mode', 'gemini_manual') in ('gemini_manual', 'api'), 'image_mode không hợp lệ')
        require(payload.get('audit_mode', 'background') in ('none', 'background', 'api', 'gemini_manual'), 'audit_mode không hợp lệ')
        require(type(payload.get('render_image', True)) is bool, 'render_image phải là boolean')
        require(payload.get('reference_mode', 'gemini_web') in ('gemini_web', 'text_only'), 'reference_mode không hợp lệ')
        session = payload.get('session_id') or str(uuid.uuid4()); idem = payload.get('idempotency_key')
        require(isinstance(session, str) and 0 < len(session) <= 120, 'session_id không hợp lệ')
        require(idem is None or isinstance(idem, str) and 0 < len(idem) <= 120, 'idempotency_key không hợp lệ')
        with self.lock:
            require(self.provider.name != 'mock' or self.allow_mock_requests, 'Mock chỉ dành cho kiểm thử', 'text_api_required', 409)
            require(self.provider.name != 'gemini' or self.provider.configured, 'Kết nối Gemini API key trước khi gửi yêu cầu', 'missing_api_key', 409)
            options = {'creative_level': payload.get('creative_level', 'explore'), 'scoring_profile': self.vp_config['scoring_by_creative_level'][payload.get('creative_level', 'explore')], 'image_mode': payload.get('image_mode', 'gemini_manual'), 'audit_mode': payload.get('audit_mode', 'background'), 'render_image': payload.get('render_image', True)}
            options['reference_mode'] = 'text_only'
            fingerprint = digest({'raw': raw, 'options': options, 'version': self.vp_version, 'model': self.provider.text_model, 'provider': self.provider.name})
            key = digest({'session': session, 'v2': idem or fingerprint})
            old = self.store.submission_get(key)
            if old:
                require(old['fingerprint'] == fingerprint, 'idempotency_key đã dùng cho payload khác', 'idempotency_conflict', 409)
                saved = self.store.get_job(old['job_id'])
                return {'request_id': saved['request_id'], 'session_id': session, 'revision': saved['revision'], 'status': saved['status'], 'deduplicated': True}
            rid = str(uuid.uuid4())
            job = {'request_id': rid, 'session_id': session, 'workflow_version': 2, 'revision': 1, 'status': 'queued', 'provider': self.provider.name,
                   **options, 'raw_prompt': raw, 'turns': [{'id': 'T1', 'text': raw}], 'brief': None, 'questions': [],
                   'cards': [], 'ranking': None, 'artifacts': [], 'image_audit': None, 'image_prompts': [],
                   'error': None, 'warnings': [], 'events': [], 'trace': [], 'workflow_steps': [], 'created_at': time.time(),
                   'budget_config': {'design': copy.deepcopy(self.vp_config['design_budget']), 'media': copy.deepcopy(self.vp_config['media_budget'])},
                   'clean_prompt': None, 'checklist': None, 'resolved_brief': None, 'choices': None, 'references': [], 'reference_metadata': [],
                   'checkpoints': {}, 'call_records': {}, 'selection_receipts': {}, 'generation_batches': {}, 'prompt_pool': [],
                   'specialist_audits': {}, 'harmony_audits': {}, 'design_stories': {}, 'supplemental_batches': 0, 'checklist_round': 0,
                   'metrics': {'provider_calls': 0, 'actual_api_calls': 0, 'cache_hits': 0, 'active_seconds': 0.0,
                               'design': {'attempts': 0, 'actual_api_calls': 0, 'active_seconds': 0.0},
                               'media': {'attempts': 0, 'actual_api_calls': 0, 'active_seconds': 0.0},
                               'cards_ready_seconds': None, 'image_ready_seconds': None, 'manual_image_prompts': 0, 'manual_images_received': 0, 'manual_audit_prompts': 0, 'manual_audits_received': 0},
                   'manifest': {'kit_hash': self.cache_version, 'vp_hash': self.vp_version, 'template_version': self.vp_prompts.version,
                                'schema_version': self.vp_contracts.document['version'], 'rubric_version': self.vp_config['rubric_version'],
                                'text_model': self.provider.text_model, 'image_model': self.provider.image_model, 'pack_hash': self.domain.hash},
                   'server_images_enabled': self.enable_images, 'repair_counts': {'concept': 0, 'image': 0}, 'recovery_count': 0}
            if options['reference_mode'] == 'text_only':
                job['warnings'].append('Ứng dụng không tìm nguồn web và không có link tham khảo đã xác minh. Chỉ hỗ trợ ý tưởng hiện đại; không xác nhận tái hiện lịch sử.')
            self.store.save_job(job)
            self.store.submission_put(key, fingerprint, rid, self.policy['cache']['session_ttl_seconds'])
            self.executor.submit(self._run, rid)
            return {'request_id': rid, 'session_id': session, 'revision': 1, 'status': 'queued'}

    def _v2_job(self, rid, revision):
        job = self.store.get_job(rid)
        require(job['revision'] == revision and job['status'] != 'cancelled', 'Request đã hủy hoặc revision đã đổi', 'cancelled', 409)
        return job

    def _v2_update(self, rid, revision, update):
        with self.lock:
            job = self._v2_job(rid, revision)
            update(job)
            self._v2_tick(job)
            self.store.save_job(job)
            return job

    def _v2_tick(self, job):
        clock = job.get('design_clock')
        if clock:
            job['metrics']['design']['active_seconds'] = round(clock['base'] + time.time() - clock['started_at'], 3)
            clock['checkpoint_at'] = time.time()
        job['metrics']['active_seconds'] = round(sum(job['metrics'].get(p, {}).get('active_seconds', 0) for p in ('design', 'media')), 3)

    def _v2_remaining(self, job):
        clock = job.get('design_clock')
        spent = clock['base'] + time.time() - clock['started_at'] if clock else job['metrics']['design']['active_seconds']
        return self.vp_config['design_budget']['active_processing_deadline_seconds'] - spent

    def _v2_stage(self, rid, revision, status, **updates):
        def mutate(job):
            job.update(updates)
            self._event(job, status)
        return self._v2_update(rid, revision, mutate)

    def selections(self, rid, payload):
        require(isinstance(payload, dict), 'Body phải là object JSON')
        with self.lock:
            job = self.store.get_job(rid)
            require(job.get('workflow_version') == 2, 'Request v1 dùng đường tương thích cũ', 'legacy_request', 409)
            idem = payload.get('idempotency_key')
            require(isinstance(idem, str) and 0 < len(idem) <= 120, 'Cần idempotency_key')
            previous = job['selection_receipts'].get(idem)
            if previous:
                require(previous['fingerprint'] == digest(payload), 'Khóa gửi trùng dùng payload khác', 'idempotency_conflict', 409)
                return dict(previous['result'], deduplicated=True)
            require(job['status'] == 'awaiting_choices', 'Request không chờ lựa chọn', 'invalid_state', 409)
            choices = vp.validate_selections(payload, job, self.vp_contracts)
            options = {o['option_id']: o for g in job['checklist']['groups'] for o in g['options']}
            lines = []
            for selection in choices['selections']:
                lines += [options[oid]['decision_text'] for oid in selection['option_ids']]
                if selection['custom_text'].strip():
                    lines.append(selection['custom_text'])
            lines += [c['replacement_text'] for c in choices['explicit_changes']]
            turn_id = 'S' + str(len(job['turns']))
            job['turns'].append({'id': turn_id, 'text': '\n'.join(lines) or 'Chốt các phần đã hiểu, không thêm lựa chọn.'})
            choices['turn_id'] = turn_id
            if job.get('selection_review'):
                job.setdefault('selection_review_history', []).append({'review': copy.deepcopy(job['selection_review']), 'choices': copy.deepcopy(job.get('choices'))})
            job.pop('selection_review', None)
            job.pop('resolved_brief', None)
            job.pop('choice_restore', None)
            job['choices'] = choices
            job['revision'] += 1
            job['status'] = 'queued'; job['error'] = None
            result = {'request_id': rid, 'revision': job['revision'], 'status': 'queued'}
            job['selection_receipts'][idem] = {'fingerprint': digest(payload), 'result': result}
            self._journal(job, 'app', 'Chốt lựa chọn có căn cứ từ form', job['turns'][-1]['text'])
            self.store.save_job(job)
            self.executor.submit(self._run, rid)
            return result

    def reopen_choices(self, rid, payload):
        require(isinstance(payload, dict), 'Body phải là object JSON')
        require(type(payload.get('reuse_checklist', False)) is bool, 'reuse_checklist phải là boolean')
        with self.lock:
            job = self.store.get_job(rid)
            require(job.get('workflow_version') == 2 and job['checklist'], 'Chưa có bảng v2', 'invalid_state', 409)
            require(type(payload.get('revision')) is int and payload['revision'] == job['revision'], 'revision cũ', 'stale_revision', 409)
            require(job['status'] in ('awaiting_choices', 'awaiting_image', 'complete', 'cards_only', 'needs_evidence', 'needs_resolution', 'failed') and not any(c['status'] == 'inflight' for c in job['call_records'].values()), 'Bước API đang chạy', 'invalid_state', 409)
            job.setdefault('design_history', []).append({key: copy.deepcopy(job.get(key)) for key in ('revision', 'clean_prompt', 'checklist', 'choices', 'resolved_brief', 'prompt_pool', 'specialist_audits', 'harmony_audits', 'design_stories', 'cards', 'image_prompts', 'image_workflow', 'output_artifact_ids', 'image_audit')})
            previous = copy.deepcopy({'checklist': job['checklist'], 'choices': job.get('choices') or job.get('choice_restore')})
            job['previous_selection_snapshot'] = previous
            reuse = payload.get('reuse_checklist', False)
            self._archive_v2_warnings(job)
            job['revision'] += 1
            for key in ('resolved_brief', 'choices', 'checklist', 'image_workflow', 'pending_manual', 'image_target_ids', 'selected_artifact_id', 'selected_artifact_ids', 'audit_resume_only', 'selection_review'):
                job.pop(key, None)
            job.update(status='queued', cards=[], image_prompts=[], prompt_pool=[], generation_batches={}, specialist_audits={}, harmony_audits={}, design_stories={}, supplemental_batches=0, error=None, ranking=None, generation_inputs={}, output_artifact_ids=[], image_audit=None)
            job.pop('choice_restore', None)
            if reuse:
                job['checklist'] = copy.deepcopy(previous['checklist'])
                job['checklist'].update(revision=job['revision'], form_id=str(uuid.uuid4()))
                job['checklist']['clean_prompt']['revision'] = job['revision']
                job['clean_prompt'] = copy.deepcopy(job['checklist']['clean_prompt'])
                job['choice_restore'] = previous['choices']
                job['status'] = 'awaiting_choices'
            self.store.save_job(job)
            if not reuse:
                self.executor.submit(self._run, rid)
            return {'request_id': rid, 'revision': job['revision'], 'status': job['status']}

    def _archive_v2_warnings(self, job):
        job.setdefault('warning_history', []).append({'revision': job['revision'], 'warnings': copy.deepcopy(job['warnings'])})
        job['warnings'] = []
        if job.get('reference_mode') == 'text_only':
            job['warnings'].append('Ứng dụng không tìm nguồn web và không có link tham khảo đã xác minh. Chỉ hỗ trợ ý tưởng hiện đại; không xác nhận tái hiện lịch sử.')

    def retry_resolution(self, rid, payload):
        """Explicit retry keeps approved inputs and cumulative budget, in a new revision."""
        require(isinstance(payload, dict), 'Body phải là object JSON')
        with self.lock:
            job = self.store.get_job(rid)
            require(type(payload.get('revision')) is int and payload['revision'] == job['revision'], 'revision cũ', 'stale_revision', 409)
            resolving = job['status'] == 'failed' and job.get('failed_stage') in ('checking_selection_conflicts', 'resolving_choices') and not job.get('resolved_brief')
            generating = job['status'] in ('needs_resolution', 'failed') and (job.get('resolved_brief') or {}).get('status') == 'ready' and not job['prompt_pool'] and not job['cards']
            require(job.get('workflow_version') == 2 and job.get('choices') and (resolving or generating), 'Chỉ tiếp tục tổng hợp hoặc sinh tập rỗng có nhu cầu đã chốt hợp lệ', 'invalid_state', 409)
            require(not any(c['status'] == 'inflight' for c in job['call_records'].values()), 'API còn đang chạy', 'invalid_state', 409)
            require(job['provider'] == self.provider.name and job['manifest']['text_model'] == self.provider.text_model and job['manifest']['schema_version'] == self.vp_contracts.document['version'] and job['manifest']['pack_hash'] == self.domain.hash, 'Nguồn/model/hợp đồng đã đổi; tạo yêu cầu mới', 'recovery_incompatible', 409)
            require(job['metrics']['design']['attempts'] < self.vp_config['design_budget']['total_provider_calls_max'] and self._v2_remaining(job) > 0, 'Đã hết ngân sách thiết kế', 'budget_exhausted', 409)
            self.vp_contracts.validate('ClarificationChecklist', job['checklist'])
            checked = copy.deepcopy(job['checklist']); checked['revision'] = job['revision']; checked['clean_prompt']['revision'] = job['revision']
            vp.validate_checklist(checked, job, checked['form_id'], job['references'])
            choices = {k: v for k, v in job['choices'].items() if k != 'turn_id'}
            choices['revision'] = job['revision']
            vp.validate_selections(choices, job, self.vp_contracts)
            if generating:
                self.vp_contracts.validate('ResolvedBrief', job['resolved_brief'])
                vp.validate_resolved(job['resolved_brief'], job)
            job.setdefault('resolution_retry_history', []).append({'revision': job['revision'], 'manifest': copy.deepcopy(job['manifest']), 'error': copy.deepcopy(job['error']), 'choices': copy.deepcopy(job['choices']), 'resolved_brief': copy.deepcopy(job.get('resolved_brief')), 'generation_batches': copy.deepcopy(job['generation_batches']), 'supplemental_batches': job['supplemental_batches']})
            self._archive_v2_warnings(job)
            job['budget_config'] = {'design': copy.deepcopy(self.vp_config['design_budget']), 'media': copy.deepcopy(self.vp_config['media_budget'])}
            job['revision'] += 1
            for value in (job['clean_prompt'], job['checklist'], job['checklist']['clean_prompt'], job['choices']):
                value['revision'] = job['revision']
            if job.get('selection_review'):
                job['selection_review']['revision'] = job['revision']
            if generating:
                job['resolved_brief']['revision'] = job['revision']
                job.update(generation_batches={}, generation_inputs={}, supplemental_batches=0, specialist_audits={}, harmony_audits={}, design_stories={})
                job.pop('pool_barrier', None)
            job['manifest'].update(vp_hash=self.vp_version, kit_hash=self.cache_version, template_version=self.vp_prompts.version)
            job.update(status='queued', error=None)
            job.pop('failed_stage', None)
            self._journal(job, 'app', 'Tiếp tục tổng hợp lựa chọn', 'Giữ lựa chọn và ngân sách đã dùng; tăng revision để chặn kết quả cũ.')
            self.store.save_job(job); self.executor.submit(self._run, rid)
            return {'request_id': rid, 'revision': job['revision'], 'status': 'queued'}

    def retry_audits(self, rid, payload):
        require(isinstance(payload, dict), 'Body phải là object JSON')
        with self.lock:
            job = self.store.get_job(rid)
            require(type(payload.get('revision')) is int and payload['revision'] == job['revision'], 'revision cũ', 'stale_revision', 409)
            require(job.get('workflow_version') == 2 and job['status'] in ('failed', 'needs_resolution') and job['prompt_pool'] and not job['cards'] and (job.get('resolved_brief') or {}).get('status') == 'ready', 'Chưa có tập prompt để tiếp tục audit', 'invalid_state', 409)
            require(not any(c['status'] == 'inflight' for c in job['call_records'].values()), 'API còn đang chạy', 'invalid_state', 409)
            require(job['provider'] == self.provider.name and job['manifest']['text_model'] == self.provider.text_model and job['manifest']['schema_version'] == self.vp_contracts.document['version'] and job['manifest']['rubric_version'] == self.vp_config['rubric_version'] and job['manifest']['pack_hash'] == self.domain.hash, 'Model/hợp đồng/rubric/pack đã đổi', 'recovery_incompatible', 409)
            require(job['metrics']['design']['attempts'] < self.vp_config['design_budget']['total_provider_calls_max'] and self._v2_remaining(job) > 0, 'Đã hết ngân sách thiết kế', 'budget_exhausted', 409)
            self.vp_contracts.validate('ResolvedBrief', job['resolved_brief']); vp.validate_resolved(job['resolved_brief'], job)
            job.setdefault('audit_retry_history', []).append({'revision': job['revision'], 'manifest': copy.deepcopy(job['manifest']), 'design_budget': copy.deepcopy(self.vp_config['design_budget']), 'prompt_hashes': {c['candidate_id']: c['content_hash'] for c in job['prompt_pool']}, 'specialist_audits': copy.deepcopy(job['specialist_audits']), 'error': job['error']})
            self._archive_v2_warnings(job)
            job['budget_config'] = {'design': copy.deepcopy(self.vp_config['design_budget']), 'media': copy.deepcopy(self.vp_config['media_budget'])}
            job['revision'] += 1; job['resolved_brief']['revision'] = job['revision']
            job['api_only_outputs'] = True
            job['audit_resume_only'] = True
            job['manifest'].update(vp_hash=self.vp_version, kit_hash=self.cache_version, template_version=self.vp_prompts.version)
            job.update(status='queued', error=None)
            job.pop('failed_stage', None)
            self._journal(job, 'app', 'Tiếp tục đánh giá còn thiếu', 'Prompt và đánh giá hợp lệ giữ nguyên; không đặt lại attempts hoặc thời gian.')
            self.store.save_job(job); self.executor.submit(self._run, rid)
            return {'request_id': rid, 'revision': job['revision'], 'status': 'queued'}

    def _vp_task(self, rid, revision, task, payload, validator, web_tools=False, structured=True):
        remaining = self._v2_remaining(self._v2_job(rid, revision))
        require(self.vp_slots.acquire(timeout=max(0, remaining)), 'Chờ API vượt design deadline', 'deadline_exceeded', 408)
        try:
            return self._vp_task_reserved(rid, revision, task, payload, validator, web_tools, structured)
        finally:
            self.vp_slots.release()

    def _vp_task_reserved(self, rid, revision, task, payload, validator, web_tools=False, structured=True):
        config = dict(self.vp_config['tasks'][task], web_tools=web_tools, structured=structured)
        schema = self.vp_contracts.schema(vp.SCHEMAS[task])
        if task in vp.ROLES:
            schema = vp.audit_response_schema(schema, payload['CANDIDATE_BATCH'])
        elif task == 'VP08':
            schema = vp.harmony_response_schema(schema)
        key = digest({'version': self.vp_version, 'model': self.provider.text_model, 'config': config, 'task': task, 'payload': payload})
        job = self._v2_job(rid, revision)
        if key in job['checkpoints']:
            saved = copy.deepcopy(job['checkpoints'][key]); value = saved['value']
            if task not in ('VP04', 'VP05', 'VP06', 'VP07', 'VP08'):
                self.vp_contracts.validate(vp.SCHEMAS[task], value); validator(value, saved['metadata'])
            self._v2_update(rid, revision, lambda j: j['metrics'].__setitem__('checkpoint_hits', j['metrics'].get('checkpoint_hits', 0) + 1))
            return value, saved['metadata']
        prompt = self.vp_prompts.render(task, payload)
        for attempt in range(1 + self.vp_config['design_budget']['retry_per_task_max']):
            attempt_id = str(uuid.uuid4()); started = time.monotonic(); usage = {}; metadata = {}; error = None; value = None
            with self.lock:
                job = self._v2_job(rid, revision)
                used = sum(c['task_key'] == key for c in job['call_records'].values())
                require(used < 1 + self.vp_config['design_budget']['retry_per_task_max'], 'Task đã hết retry', 'task_retry_exhausted', 409)
                require(job['metrics']['design']['attempts'] < self.vp_config['design_budget']['total_provider_calls_max'], 'Hết design budget', 'budget_exhausted', 409)
                remaining = self._v2_remaining(job)
                require(remaining > 0, 'Hết thời gian thiết kế', 'deadline_exceeded', 408)
                timeout = min(config['timeout_seconds'], remaining)
                job['metrics']['provider_calls'] += 1; job['metrics']['design']['attempts'] += 1
                job['call_records'][attempt_id] = {'task_key': key, 'task': task, 'stage': job['status'], 'role': vp.ROLES.get(task), 'revision': revision, 'batch_id': payload.get('CANDIDATE_SLOTS', {}).get('batch_id') or (payload.get('CANDIDATE_BATCH') or [{}])[0].get('batch_id'), 'status': 'inflight', 'started_at': time.time(), 'timeout_seconds': timeout, 'provider_call_id': None}
                self._v2_tick(job); self.store.save_job(job)
            def observe(call_id):
                with self.lock:
                    current = self.store.get_job(rid)
                    warning = getattr(self.provider, 'last_call_warning', None)
                    if warning:
                        current['warnings'].append(warning)
                        current.setdefault('api_call_warnings', []).append(warning)
                    current['call_records'][attempt_id]['provider_call_id'] = call_id
                    current['metrics']['actual_api_calls'] += 1
                    current['metrics']['design']['actual_api_calls'] += 1
                    self._v2_tick(current); self.store.save_job(current)
            if hasattr(self.provider, 'prepare_attempt'):
                self.provider.prepare_attempt()
            if hasattr(self.provider, 'observe_attempt'):
                self.provider.observe_attempt(observe)
            try:
                self.evidence.write('vp-task-inputs', {'request_id': rid, 'revision': revision, 'attempt_id': attempt_id, 'task': task, 'payload': payload, 'prompt': prompt, 'schema': schema, 'config': config})
                value, usage, metadata = self.provider.structured_v2(task, self.vp_prompts.system, prompt, schema, payload, timeout, config)
                self._v2_job(rid, revision)
                if task not in ('VP04', 'VP05', 'VP06', 'VP07', 'VP08'):
                    self.vp_contracts.validate(vp.SCHEMAS[task], value)
                    validator(value, metadata)
            except ArenaError as exc:
                error = exc
            except Exception:
                error = ArenaError('internal_error', 'Lỗi provider/validator v2', 502)
            finally:
                if hasattr(self.provider, 'observe_attempt'):
                    self.provider.observe_attempt(None)
                if error:
                    usage = getattr(self.provider, 'last_response_usage', usage)
                    metadata = getattr(self.provider, 'last_response_metadata', metadata)
                with self.lock:
                    current = self.store.get_job(rid)
                    stale = current['revision'] != revision or current['status'] == 'cancelled'
                    record = current['call_records'][attempt_id]
                    record['status'] = 'discarded' if stale else 'failed' if error else 'complete'
                    record['finished_at'] = time.time()
                    entry = {'task': task, 'phase': 'design', 'attempt_id': attempt_id, 'revision': revision, 'role': vp.ROLES.get(task), 'batch_id': record['batch_id'], 'cache_hit': False, 'duration_ms': round(1000 * (time.monotonic() - started)), 'provider_call_id': record.get('provider_call_id'), 'provider_called': bool(record.get('provider_call_id')) if self.provider.name == 'gemini' else True, 'usage': usage, 'tool_metadata': metadata, 'input_hash': digest(payload), 'output_hash': digest(value) if value else None}
                    if error or stale:
                        entry['error_code'] = 'cancelled' if stale else error.code
                        entry['error_message'] = 'Kết quả muộn bị bỏ qua' if stale else error.message
                    self._record_trace(current, entry)
                    current['metrics']['design']['search_queries_reported'] = current['metrics']['design'].get('search_queries_reported', 0) + len(metadata.get('groundingMetadata', {}).get('webSearchQueries', []))
                    if not error and not stale:
                        current['checkpoints'][key] = {'task': task, 'value': copy.deepcopy(value), 'metadata': metadata, 'usage': usage}
                    self._v2_tick(current); self.store.save_job(current)
                    self.evidence.write('vp-task-results', {'request_id': rid, 'attempt_id': attempt_id, 'trace': entry, 'value': value})
            if stale:
                raise ArenaError('cancelled', 'Kết quả muộn chỉ được lưu vào lịch sử', 409)
            if not error:
                return value, metadata
            retryable = isinstance(error, ProviderError) and error.retryable or error.code in ('schema_invalid', 'semantic_invalid', 'provider_invalid_json', 'provider_incomplete_output', 'provider_empty_output')
            if not retryable or attempt == self.vp_config['design_budget']['retry_per_task_max']:
                raise error
            if isinstance(error, ProviderError):
                delay = error.retry_after_seconds or 1.0
                # Wait within the existing deadline and remain cancellation-safe.
                require(delay < self._v2_remaining(self._v2_job(rid, revision)), 'Chờ thử lại vượt thời gian thiết kế', 'deadline_exceeded', 408)
                until = time.monotonic() + delay
                while time.monotonic() < until:
                    self._v2_job(rid, revision)
                    time.sleep(max(0, min(.2, until - time.monotonic())))
            else:
                prompt += '\nLượt trước không hợp lệ: ' + error.message + '. Giữ nguyên input và sửa đúng hợp đồng.'

    def _vp_base(self, job):
        return {'REQUEST_METADATA': {'request_id': job['request_id'], 'revision': job['revision']}, 'USER_TURNS': job['turns']}

    def _vp_references(self, job):
        return {'references': job['references'], 'provider_metadata': job['reference_metadata'], 'reference_mode': job.get('reference_mode', 'gemini_web'), 'availability': 'unavailable_by_user_choice' if job.get('reference_mode') == 'text_only' else 'gemini_tools'}

    def _vp_checklist(self, rid, revision):
        job = self._v2_stage(rid, revision, 'designing_checklist')
        form_id = job.get('next_form_id') or str(uuid.uuid4())
        self._v2_update(rid, revision, lambda j: j.update(next_form_id=form_id))
        base = self._vp_base(job)
        guidance = {
            'source_domains': [{'domain_id': d['domain_id'], 'label': d['label']} for d in job['clean_prompt']['domains']],
            'design_dimensions_to_review': [
                'Bối cảnh và vai trò sử dụng', 'Nền trang phục và cách phối',
                'Phong cách trang phục và mức chuyển thể', 'Phom, che phủ và vận động',
                'Chất liệu, kỹ thuật và tính ứng dụng', 'Bảng màu',
                'Mỹ thuật, hoa văn, vị trí và độ phủ', 'Phụ kiện và cách tạo điểm nhấn',
                'Cách trình bày ảnh (riêng với phong cách trang phục)',
            ],
            'coverage_policy': 'Rà soát các chiều còn mở, không giới hạn theo source_domains. Chỉ tạo nhóm có ích; optional cho tinh chỉnh có thể giao AI. Không ép số nhóm, không tạo atom yêu cầu giả.',
        }
        # Source discovery has been removed, including for resumed legacy jobs.
        self._v2_update(rid, revision, lambda j: j.update(reference_mode='text_only', references=[], reference_metadata=[]))
        current = self._v2_job(rid, revision)
        payload = dict(base, CLEAN_PROMPT=current['clean_prompt'], DOMAIN_GUIDANCE=guidance,
                       REFERENCE_BUNDLE=self._vp_references(current),
                       REFERENCE_DISCOVERY_CONFIG={'mode': 'unavailable', 'tools': [], 'reason': 'Ứng dụng không tìm nguồn. references=[] và mọi reference_ids=[]; không sinh URL từ trí nhớ. Không xác nhận tái hiện lịch sử.'},
                       PREVIOUS_CHECKLIST_AND_CHOICES={'checklist': current.get('checklist'), 'choices': current.get('choices'), 'unresolved': current.get('resolved_brief')},
                       FORM_CONFIG={'form_id': form_id, 'open_groups_initial': 6, **self.vp_config['checklist']})
        def validate(value, metadata):
            vp.valid(value['references'] == [], 'Ứng dụng không tạo nguồn hoặc link từ trí nhớ')
            vp.validate_checklist(value, current, form_id, [])
        result, metadata = self._vp_task(rid, revision, 'VP02', payload, validate)
        def finish(j):
            j.update(clean_prompt=result['clean_prompt'], checklist=result, references=[], choices=None, resolved_brief=None)
            j.pop('next_form_id', None); j['checklist_round'] += 1
        self._v2_update(rid, revision, finish)
        self._v2_stage(rid, revision, 'awaiting_choices')

    def _vp_pool_target(self):
        generation = self.vp_config['generation']
        return generation.get('initial_pool_size', generation['batch_size'] * generation['initial_batches'])

    def _vp_generate(self, rid, revision, index, supplemental=False):
        job = self._v2_job(rid, revision); brief = job['resolved_brief']
        batch_id = 'B' + str(index + 1)
        spaces = brief['creative_space']
        ordered = spaces[index % len(spaces):] + spaces[:index % len(spaces)] if spaces else []
        focus = ordered[:2]
        level_instruction = {'moderate': 'Thay đổi tiết chế trong các phần mở, vẫn tạo khác biệt cụ thể.', 'balanced': 'Cân bằng mức thay đổi với tính sử dụng; khám phá quan hệ giữa các miền mở.', 'explore': 'Khám phá các tổ hợp mới có chủ đích của ít nhất hai quyết định còn mở, công bố giới hạn nếu không đủ tự do.'}[job['creative_level']]
        direction = {'direction_id': 'D' + str(index + 1), 'label': 'Khám phá ' + str(index + 1), 'focus_domain_ids': [s['domain_id'] for s in focus], 'allowed_variations': [dict(s, exploration_offset=index * 3) for s in ordered], 'locked_atom_ids': brief['locked_atom_ids'], 'creative_level': job['creative_level'], 'instruction': level_instruction + ' Nhóm này khám phá các biến thể kế tiếp, không thay điều khóa.'}
        batch_size = self.vp_config['generation']['batch_size']
        slot_count = batch_size if supplemental else min(batch_size, max(0, self._vp_pool_target() - index * batch_size))
        if not slot_count:
            return
        slots = {'batch_id': batch_id, 'slots': [{'candidate_id': f'R{revision}-{batch_id}-C{n + 1}', 'revision': revision} for n in range(slot_count)]}
        payload = dict(self._vp_base(job), RESOLVED_BRIEF=brief, GENERATION_DIRECTION=direction, CREATIVITY_CONFIG={'level': job['creative_level'], 'spaces': spaces}, CANDIDATE_SLOTS=slots, REFERENCE_BUNDLE=self._vp_references(job), PREVIOUS_DESIGN_DIGESTS=[{'candidate_id': c['candidate_id'], 'design_sections': c['design_sections'], 'choices_made': c['choices_made']} for c in job['prompt_pool']], LOCKED_REQUIREMENTS=[a for a in brief['atoms'] if a['atom_id'] in brief['locked_atom_ids']])
        if batch_id in job.get('generation_inputs', {}):
            payload = job['generation_inputs'][batch_id]
            slots = payload['CANDIDATE_SLOTS']
        else:
            self._v2_update(rid, revision, lambda j: j.setdefault('generation_inputs', {}).__setitem__(batch_id, payload))
        result, _ = self._vp_task(rid, revision, 'VP04', payload, lambda v, m: None)
        for candidate in result['candidates']:
            candidate['content_hash'] = vp.content_hash(candidate)
        def save(j):
            j['api_only_outputs'] = True
            j['generation_batches'][batch_id] = {'direction': direction, 'final_prompt': self.vp_prompts.render('VP04', payload), 'candidates': result['candidates'], 'limitations': result['limitations'], 'supplemental': supplemental}
            j['prompt_pool'] = [c for b in j['generation_batches'].values() for c in b['candidates']]
            j['warnings'].extend(result['limitations'])
            j['design_progress'] = {'pool_count': len(j['prompt_pool']), 'pool_target': self._vp_pool_target(), 'audit_started': False}
        self._v2_update(rid, revision, save)

    def _vp_audit(self, rid, revision, batch_id, role):
        job = self._v2_job(rid, revision); candidates = job['generation_batches'][batch_id]['candidates']; brief = job['resolved_brief']
        if not candidates:
            return
        task = next(t for t, r in vp.ROLES.items() if r == role)
        checks = vp.expected_checks(brief, candidates, role); role_rubric = vp.rubric(self.vp_config, role, brief)
        for check in checks:
            if check['check_id'].startswith('locked:'):
                aid = check['check_id'].removeprefix('locked:')
                check['exact_prompt_excerpts'] = {c['candidate_id']: next((x['prompt_quote'] for x in c['locked_coverage'] if x['atom_id'] == aid and x['prompt_quote'] and x['prompt_quote'] in c['image_prompt']), '') for c in candidates}
        payload = {'REQUEST_METADATA': self._vp_base(job)['REQUEST_METADATA'], 'RESOLVED_BRIEF': brief, 'CANDIDATE_BATCH': vp.audit_candidates(candidates), 'REFERENCE_BUNDLE': self._vp_references(job), 'EXPECTED_CHECKS': checks, 'ROLE_RUBRIC': role_rubric, 'AUDIT_POLICY': {'creative_level': job['creative_level'], 'profile': job['scoring_profile'], 'label': 'Ưu tiên sáng tạo' if job['scoring_profile'] == 'creative' else 'Cân bằng chuyên môn'}}
        # Deliberately no specialist_audits in this payload, even on retry/recovery.
        result, _ = self._vp_task(rid, revision, task, payload, lambda v, m: None)
        def save(j):
            for audit in result['audits']:
                item = copy.deepcopy(audit); item['score'] = audit['score']
                j['specialist_audits'].setdefault(item['candidate_id'], {})[role] = item
        self._v2_update(rid, revision, save)

    def _vp_harmony(self, rid, revision, batch_id):
        job = self._v2_job(rid, revision); brief = job['resolved_brief']
        candidates = [c for c in job['generation_batches'][batch_id]['candidates'] if set(job['specialist_audits'].get(c['candidate_id'], {})) == {'fashion', 'culture', 'art'}]
        if not candidates:
            return
        specialists = {c['candidate_id']: job['specialist_audits'][c['candidate_id']] for c in candidates}
        payload = {'REQUEST_METADATA': self._vp_base(job)['REQUEST_METADATA'], 'RESOLVED_BRIEF': brief, 'CANDIDATE_BATCH': candidates, 'VALIDATED_SPECIALIST_AUDITS': specialists, 'VALIDATED_GATE_SUMMARY': {cid: vp.gate_summary(items) for cid, items in specialists.items()}, 'HARMONY_RUBRIC': vp.rubric(self.vp_config, 'harmony', brief), 'SCORING_CONFIG': {'profile': job['scoring_profile'], 'weights': self.vp_config['profiles'][job['scoring_profile']], 'minimum_total': self.vp_config['minimum_total']}, 'REFERENCE_BUNDLE': self._vp_references(job)}
        weights = payload['SCORING_CONFIG']['weights']
        payload['SCORING_CONFIG']['source_numerator_terms'] = {cid: {role: weights[role] * item['score'] for role, item in roles.items() if isinstance(item.get('score'), (int, float))} for cid, roles in specialists.items()}
        payload['SCORING_CONFIG']['source_numerator_subtotal'] = {cid: sum(terms.values()) for cid, terms in payload['SCORING_CONFIG']['source_numerator_terms'].items()}
        result, _ = self._vp_task(rid, revision, 'VP08', payload, lambda v, m: None)
        def save(j):
            for audit in result['audits']:
                item = copy.deepcopy(audit)
                h = item['harmony_score']
                item['reported_harmony_score'] = item['harmony_score']; item['reported_total'] = item['proposed_total']
                item['harmony_score'] = h; item['score_100'] = item['proposed_total']
                j['harmony_audits'][item['candidate_id']] = item
        self._v2_update(rid, revision, save)

    def _vp_design_story(self, rid, revision, candidate):
        job = self._v2_job(rid, revision)
        cid = candidate['candidate_id']
        story = job.get('design_stories', {}).get(cid)
        if story and story['content_hash'] == candidate['content_hash'] and story['candidate_revision'] == candidate['revision']:
            self._v2_update(rid, revision, lambda j: next(c for c in j['cards'] if c['candidate_id'] == cid).update(design_story=copy.deepcopy(story)))
            return
        payload = {'REQUEST_METADATA': self._vp_base(job)['REQUEST_METADATA'],
                   'RESOLVED_BRIEF': job['resolved_brief'], 'CANDIDATE': candidate,
                   'CULTURE_REVIEW': job['specialist_audits'][cid]['culture'],
                   'REFERENCE_BUNDLE': self._vp_references(job)}
        def validate(value, metadata):
            vp.valid(value['candidate_id'] == cid and value['candidate_revision'] == candidate['revision']
                     and value['content_hash'] == candidate['content_hash'], 'Câu chuyện sai phương án/phiên bản/hash')
        story, _ = self._vp_task(rid, revision, 'VP09', payload, validate)
        def save(j):
            j.setdefault('design_stories', {})[cid] = copy.deepcopy(story)
            next(c for c in j['cards'] if c['candidate_id'] == cid)['design_story'] = copy.deepcopy(story)
        self._v2_update(rid, revision, save)

    def _vp_parallel(self, rid, revision, tasks, workers):
        errors = []
        with ThreadPoolExecutor(max_workers=workers, thread_name_prefix='vp-api') as pool:
            futures = [pool.submit(fn, *args) for fn, args in tasks]
            for future in as_completed(futures):
                try:
                    future.result()
                except ArenaError as error:
                    if error.code == 'cancelled':
                        raise
                    errors.append({'code': error.code, 'message': error.message})
        if errors:
            self._v2_update(rid, revision, lambda j: (j.setdefault('stage_errors', []).extend(errors), j['warnings'].extend(e['message'] for e in errors)))
        return errors

    def _vp_supplement(self, rid, revision):
        job = self._v2_job(rid, revision)
        if job['supplemental_batches'] >= self.vp_config['generation']['supplemental_batches_max'] or self.vp_config['design_budget']['total_provider_calls_max'] - job['metrics']['design']['attempts'] < 5 or self._v2_remaining(job) <= 0:
            return None
        index = self.vp_config['generation']['initial_batches']
        self._v2_update(rid, revision, lambda j: j.update(supplemental_batches=j['supplemental_batches'] + 1))
        errors = self._vp_parallel(rid, revision, [(self._vp_generate, (rid, revision, index, True))], 1)
        return 'B' + str(index + 1) if not errors else None

    def _return_selection_conflicts(self, rid, revision):
        def restore(job):
            job['choice_restore'] = copy.deepcopy(job['choices'])
            job['checklist']['revision'] = revision
            job['checklist']['clean_prompt']['revision'] = revision
            job['clean_prompt']['revision'] = revision
            self._journal(job, 'app', 'Cần sửa xung đột nghiêm trọng', 'Giữ bảng và lựa chọn; chưa chuyển sang tạo thiết kế.')
        self._v2_update(rid, revision, restore)
        self._v2_stage(rid, revision, 'awaiting_choices')

    def _run_v2(self, rid):
        job = self.store.get_job(rid); revision = job['revision']
        with self.lock:
            self._v2_update(rid, revision, lambda j: j.update(design_clock={'started_at': time.time(), 'checkpoint_at': time.time(), 'base': j['metrics']['design']['active_seconds']}))
        try:
            if not job.get('clean_prompt'):
                job = self._v2_stage(rid, revision, 'cleaning')
                payload = dict(self._vp_base(job), RAW_PROMPT=job['raw_prompt'], DOMAIN_GUIDANCE=['Bối cảnh', 'Cấu trúc', 'Chất liệu', 'Màu', 'Mỹ thuật', 'Văn hóa', 'Thể hiện ảnh', 'Tạo miền khác nếu cần'], PREVIOUS_CLEAN_PROMPT=None)
                result, _ = self._vp_task(rid, revision, 'VP01', payload, lambda v, m: vp.validate_clean(v, job))
                self._v2_update(rid, revision, lambda j: j.update(clean_prompt=result))
            job = self._v2_job(rid, revision)
            if not job.get('choices'):
                self._vp_checklist(rid, revision)
                return
            if not job.get('selection_review'):
                job = self._v2_stage(rid, revision, 'checking_selection_conflicts')
                payload = dict(self._vp_base(job), CLEAN_PROMPT=job['clean_prompt'], CHECKLIST=job['checklist'], CURRENT_SELECTIONS=job['choices'], CONFLICT_POLICY=self.vp_config['selection_review'])
                result, _ = self._vp_task(rid, revision, 'VP02C', payload, lambda v, m: vp.validate_selection_review(v, job))
                job = self._v2_update(rid, revision, lambda j: j.update(selection_review=result))
            if job['selection_review']['status'] == 'conflict':
                self._return_selection_conflicts(rid, revision)
                return
            if not job.get('resolved_brief'):
                job = self._v2_stage(rid, revision, 'resolving_choices')
                payload = dict(self._vp_base(job), CLEAN_PROMPT=job['clean_prompt'], CHECKLIST=job['checklist'], VALIDATED_SELECTIONS=job['choices'], SELECTION_CONFLICT_REVIEW=job['selection_review'], PREVIOUS_RESOLVED_BRIEF=(job.get('design_history') or [{}])[-1].get('resolved_brief'), REFERENCE_BUNDLE=self._vp_references(job))
                options = {o['option_id']: o for g in job['checklist']['groups'] for o in g['options']}
                payload['VALIDATED_SELECTIONS'] = dict(job['choices'], decision_contracts=[{'group_id': s['group_id'], 'delegated': any(options[oid]['is_ai_delegate'] for oid in s['option_ids']), 'option_ids': s['option_ids'], 'custom_text': s['custom_text']} for s in job['choices']['selections'] if s['option_ids'] or s['custom_text'].strip()])
                payload['VALIDATED_SELECTIONS']['old_atom_binding'] = vp.old_atom_binding(job['clean_prompt']['atoms'], job['choices']['explicit_changes'])
                result, _ = self._vp_task(rid, revision, 'VP03', payload, lambda v, m: vp.validate_resolved(v, job))
                job = self._v2_update(rid, revision, lambda j: j.update(resolved_brief=result))
            brief = job['resolved_brief']
            if brief['status'] == 'needs_evidence':
                self._v2_stage(rid, revision, 'needs_evidence'); return
            if brief['status'] == 'needs_resolution':
                self._return_selection_conflicts(rid, revision); return
            job = self._v2_stage(rid, revision, 'generating_prompt_pool')
            tasks = [(self._vp_generate, (rid, revision, i)) for i in range(self.vp_config['generation']['initial_batches']) if not job.get('audit_resume_only') and 'B' + str(i + 1) not in job['generation_batches']]
            self._vp_parallel(rid, revision, tasks, self.vp_config['generation']['generation_concurrency'])
            job = self._v2_job(rid, revision)
            if len(job['prompt_pool']) < self._vp_pool_target() and not job.get('audit_resume_only'):
                self._vp_supplement(rid, revision)
                job = self._v2_job(rid, revision)
                self._v2_update(rid, revision, lambda j: j['warnings'].append(f"Pool có {len(j['prompt_pool'])}/{self._vp_pool_target()} prompt trước audit; đã xử lý bổ sung trong giới hạn."))
            # Barrier: ALL initial generations (and a bounded shortage attempt) are settled.
            self._v2_stage(rid, revision, 'specialist_auditing', pool_barrier={'revision': revision, 'count': len(job['prompt_pool']), 'target': self._vp_pool_target(), 'closed': True, 'timestamp': time.time()})
            batches = [bid for bid, batch in job['generation_batches'].items() if batch['candidates']]
            tasks = [(self._vp_audit, (rid, revision, bid, role)) for bid in batches for role in ('fashion', 'culture', 'art') if not all(role in job['specialist_audits'].get(c['candidate_id'], {}) for c in job['generation_batches'][bid]['candidates'])]
            self._vp_parallel(rid, revision, tasks, self.vp_config['generation']['specialist_concurrency'])
            self._v2_stage(rid, revision, 'harmony_scoring')
            self._vp_parallel(rid, revision, [(self._vp_harmony, (rid, revision, bid)) for bid in batches], 2)
            job = self._v2_job(rid, revision)
            ranking = vp.rank_reported(job['prompt_pool'], job['specialist_audits'], job['harmony_audits'], self.vp_config)
            if len(ranking['ranked']) < 3 and not job.get('audit_resume_only'):
                bid = self._vp_supplement(rid, revision)
                if bid:
                    self._v2_stage(rid, revision, 'specialist_auditing')
                    self._vp_parallel(rid, revision, [(self._vp_audit, (rid, revision, bid, r)) for r in ('fashion', 'culture', 'art')], 3)
                    self._v2_stage(rid, revision, 'harmony_scoring'); self._vp_harmony(rid, revision, bid)
                    job = self._v2_job(rid, revision)
                    ranking = vp.rank_reported(job['prompt_pool'], job['specialist_audits'], job['harmony_audits'], self.vp_config)
            def select(j):
                j['ranking'] = ranking
                adapt(j, ranking)
                j['design_progress'] = {'pool_count': len(j['prompt_pool']), 'pool_target': self._vp_pool_target(), 'audited_count': len(j['harmony_audits']), 'selected_count': len(j['cards']), 'audit_started': True}
                if len(j['cards']) < 3:
                    j['warnings'].append(f"Chỉ có {len(j['cards'])}/3 phương án hợp lệ đạt ngưỡng; không đủ kết quả để hiển thị ba thẻ.")
            self._v2_stage(rid, revision, 'selecting')
            job = self._v2_update(rid, revision, select)
            if not job['cards']:
                self._v2_stage(rid, revision, 'needs_resolution', failed_stage='generating_prompt_pool' if not job['prompt_pool'] else 'selecting'); return
            self._v2_stage(rid, revision, 'writing_design_stories')
            tasks = [(self._vp_design_story, (rid, revision, row['candidate'])) for row in ranking['ranked']]
            errors = self._vp_parallel(rid, revision, tasks, 3)
            if errors:
                raise ArenaError(errors[0]['code'], errors[0]['message'], 502)
            self._v2_update(rid, revision, lambda j: j['metrics'].__setitem__('cards_ready_seconds', j['metrics']['design']['active_seconds']))
            self._v2_stage(rid, revision, 'cards_ready')
            if not job['render_image']:
                self._v2_stage(rid, revision, 'complete'); return
            if job['image_mode'] == 'api' and not self.enable_images:
                self._v2_stage(rid, revision, 'cards_only'); return
            # End design timing before handing off to the existing media workflow.
            self._finish_v2_clock(rid, revision)
            job = self._v2_job(rid, revision)
            budget = Budget(job, self.policy, 'media')
            try:
                self._render_image(job, budget, job['cards'][0], job['retrieval_bundle'])
            finally:
                budget.finish(); self.store.save_job(job)
        except ArenaError as error:
            if error.code != 'cancelled':
                stage = self._v2_job(rid, revision)['status']
                self._v2_stage(rid, revision, 'failed', failed_stage=stage, error={'code': error.code, 'message': error.message})
        except Exception as error:
            self.evidence.write('vp-internal-errors', {'request_id': rid, 'type': type(error).__name__})
            self._v2_stage(rid, revision, 'failed', error={'code': 'internal_error', 'message': 'Lỗi nội bộ workflow v2; kết quả hợp lệ vẫn giữ trong checkpoint.'})
        finally:
            self._finish_v2_clock(rid, revision)

    def _finish_v2_clock(self, rid, revision):
        with self.lock:
            job = self.store.get_job(rid)
            if job['revision'] != revision:
                return
            self._v2_tick(job); job.pop('design_clock', None); self.store.save_job(job)

    def _recover_v2(self, job):
        waiting = {'awaiting_choices', 'awaiting_image', 'awaiting_image_repair', 'awaiting_manual_audit', 'awaiting_audit_choice'}
        if job['status'] in waiting or job['status'] == 'needs_resolution':
            return
        if job['manifest'].get('vp_hash') != self.vp_version or job['provider'] != self.provider.name or job['manifest']['text_model'] != self.provider.text_model:
            job.update(status='failed', error={'code': 'recovery_incompatible', 'message': 'Cấu hình v2 đã đổi; giữ lịch sử và tạo yêu cầu mới.'})
            self.store.save_job(job); return
        if job['status'] == 'awaiting_choices':
            return
        inflight = [c for c in job['call_records'].values() if c['status'] == 'inflight']
        clock = job.pop('design_clock', None)
        if clock:
            extra = min(max(0, time.time() - clock['checkpoint_at']), max([c['timeout_seconds'] for c in inflight] or [0]))
            job['metrics']['design']['active_seconds'] += extra
        for record in inflight:
            record['status'] = 'interrupted'
            self._record_trace(job, {'task': record['task'], 'phase': 'design', 'revision': record['revision'], 'interrupted': True, 'provider_called': bool(record.get('provider_call_id')), 'provider_call_id': record.get('provider_call_id'), 'cache_hit': False, 'usage': {}})
        media_inflight = job.pop('inflight', None)
        if media_inflight:
            estimated = min(max(0, time.time() - media_inflight['started_at']), media_inflight['timeout_seconds'])
            job['metrics']['media']['active_seconds'] = round(job['metrics']['media']['active_seconds'] + estimated, 3)
            self._record_trace(job, {'task': media_inflight['task'], 'phase': 'media', 'interrupted': True,
                                     'provider_called': bool(media_inflight.get('provider_call_id')),
                                     'provider_call_id': media_inflight.get('provider_call_id'),
                                     'active_seconds_estimated': round(estimated, 3), 'cache_hit': False, 'usage': {}})
        self._v2_tick(job)
        job['recovery_count'] += 1
        job['warnings'].append('Phục hồi checkpoint v2; giữ attempts, API đã gửi và chỉ tiếp tục tác vụ còn thiếu.')
        self.store.save_job(job)
        self.executor.submit(self._run, job['request_id'])
