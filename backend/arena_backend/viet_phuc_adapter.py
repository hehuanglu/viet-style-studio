"""The only conversion from open v2 semantics to the existing image workflow."""
import copy



def adapt(job, ranking):
    brief = job['resolved_brief']
    atoms = {a['atom_id']: a for a in brief['atoms']}
    invariants = [atoms[aid]['meaning'] for aid in brief['locked_atom_ids']]
    # No ontology lookup and no inferred garment/gender/color. The full design
    # lives in context/extensions so arbitrary new domains reach P06 and edits.
    mode = 'inspired' if brief['historical_mode'] == 'neutral' else brief['historical_mode']
    job['brief'] = {'mode': mode, 'original_historical_mode': brief['historical_mode'],
                    'subject': {'field': 'subject', 'value': brief['resolved_text'], 'status': 'explicit'},
                    'goal': {'field': 'goal', 'value': 'create_look', 'status': 'explicit'},
                    'context': [{'field': d['label'], 'value': d['summary'], 'status': 'explicit'} for d in brief['domains']],
                    'preferences': [{'field': 'resolved_brief', 'value': brief['resolved_text'], 'status': 'explicit'}],
                    'hard_constraints': [{'id': aid, 'field': 'open_requirement', 'operator': 'preserve', 'value': atoms[aid]['meaning'], 'provenance': 'user_provided'} for aid in brief['locked_atom_ids']],
                    'assumptions': []}
    # Gemini tool provenance is not the v1 pack's human verification status.
    sources = [{'id': r['reference_id'], 'url': r['url'], 'label': r['label'], 'kind': r['source_type'],
                'discovery_status': r['discovery_status'], 'scope': r['scope']} for r in job['references']]
    units = [{'id': r['reference_id'], 'source_id': r['reference_id'], 'claim': r['description'],
              'source_excerpt': r['supporting_excerpt'], 'scope': r['scope'], 'status': 'tool_grounded',
              'kind': 'reference', 'verification_method': 'gemini_tool_metadata_only'} for r in job['references'] if r['discovery_status'] == 'tool_grounded' and r['supporting_excerpt']]
    job['retrieval_bundle'] = {'rules': [], 'cultural_units': [], 'knowledge_units': units, 'sources': sources,
                               'references': copy.deepcopy(job['references']), 'historical_scope_supported': brief['historical_mode'] != 'historical' or bool(units)}
    cards = []
    for row in ranking['ranked']:
        candidate = copy.deepcopy(row['candidate'])
        cid = candidate['candidate_id']
        reviews = job['specialist_audits'][cid]
        candidate.update(score=row['score'], specialist_scores=row['scores'], harmony=row['harmony'],
                         specialist_reviews=copy.deepcopy(reviews), target_need=brief['resolved_text'],
                         design={'subject_description': candidate['fashion_summary'], 'palette': [], 'accessories': [],
                                 'composition': candidate['art_summary'], 'scene': brief['resolved_text'],
                                 'extensions': [{'key': s['domain_id'], 'value': s['description']} for s in candidate['design_sections']]},
                         keep_invariants=invariants, allowed_changes=[s['description'] for s in brief['creative_space']],
                         caveats=candidate['limitations'], design_mode=mode, subject=brief['resolved_text'],
                         source_caption=[{'text': c['text'], 'source_id': c['source_id'], 'source_url': next((r['url'] for r in job['references'] if r['reference_id'] == c['reference_id']), ''), 'verification': 'Gemini tool metadata; chưa xác nhận chuyên môn'} for c in candidate['claims']],
                         output_origin=job['provider'])
        cards.append(candidate)
    job['cards'] = cards
    job['image_prompts'] = [{'candidate_id': c['candidate_id'], 'title': c['title'], 'prompt': c['image_prompt'], 'content_hash': c['content_hash']} for c in cards]
    job['selected_prompt_ids'] = [c['candidate_id'] for c in cards]
    if cards:
        job['compiled_image_prompt'] = cards[0]['image_prompt']
