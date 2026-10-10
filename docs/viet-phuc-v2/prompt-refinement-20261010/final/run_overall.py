#!/usr/bin/env python3
"""Focused live API checks. No UI, no workflow regeneration, no persisted credential."""
import copy,getpass,json,sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor,as_completed
ROOT=next(p for p in Path(__file__).resolve().parents if (p/'backend/viet_phuc').is_dir());sys.path.insert(0,str(ROOT/'backend'))
from arena_backend import viet_phuc as vp
from arena_backend.providers import GeminiProvider
from arena_backend.core import Contracts
OUT=Path(__file__).parent;records=[json.loads(f.read_text()) for f in (ROOT/'backend/evidence/prompt-refinement-20261010-r2/vp-task-inputs').glob('*.json')]
config=json.loads((vp.DATA/'config.json').read_text());contracts=Contracts(vp.DATA/'contracts.json');prompts=vp.VPPrompts()
FULL='cc1fc4fa-ea9d-4faa-945e-8fc373a1d449';SPARSE='da6d2259-358a-422d-a96e-a34370fc6b6a'
def rec(task,rid,cid=None):return next(r for r in records if r['task']==task and r['request_id']==rid and (cid is None or any(c['candidate_id']==cid for c in r['payload'].get('CANDIDATE_BATCH',[]))))
def save(name,value):(OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2))
provider=GeminiProvider(getpass.getpass('Gemini API key (hidden): '),evidence_dir=ROOT/'backend/evidence/prompt-refinement-20261010-final')
def call(name,task,payload):
 schema=contracts.schema(vp.SCHEMAS[task]);cfg=dict(config['tasks'][task],structured=True,web_tools=False)
 if task in vp.ROLES:schema=vp.audit_response_schema(schema,payload['CANDIDATE_BATCH']);payload['CANDIDATE_BATCH']=vp.audit_candidates(payload['CANDIDATE_BATCH'])
 if task=='VP08':schema=vp.harmony_response_schema(schema)
 prompt=prompts.render(task,payload);save(name+'-input',dict(task=task,payload=payload,prompt=prompt,schema=schema,config=cfg,template_version=prompts.version))
 try:
  value,usage,metadata=provider.structured_v2(task,prompts.system,prompt,schema,payload,110,cfg);save(name+'-output',dict(value=value,usage=usage,metadata=metadata));print(name,'done',flush=True);return value
 except Exception as exc:
  save(name+'-error',dict(code=getattr(exc,'code',None),message=str(exc)));print(name,'failed',flush=True);return None

for persona,rid in [('full',FULL),('sparse',SPARSE)]:
 original=json.loads((ROOT/f'docs/viet-phuc-v2/prompt-refinement-20261010/round2/{persona}-complete-job.json').read_text());job=copy.deepcopy(original);ids={c['candidate_id'] for c in job['cards']};selected=[c for c in job['prompt_pool'] if c['candidate_id'] in ids]
 if persona=='sparse':
  repaired=json.loads((ROOT/'docs/viet-phuc-v2/prompt-refinement-20261010/local-r4/sparse-text-repair-output.json').read_text())['value']['candidates'];byid={c['candidate_id']:c for c in repaired}
  for index,c in enumerate(selected):
   updated=byid[c['candidate_id']];updated['content_hash']=vp.content_hash(updated);selected[index]=updated
 job['prompt_pool']=selected;job['specialist_audits']={};job['harmony_audits']={};job['audit_scope']='Selected three final prompts; stage replay after local tests; no frontend or image generation.'
 work=[]
 for task,role in vp.ROLES.items():
  p=copy.deepcopy(rec(task,rid)['payload']);p['CANDIDATE_BATCH']=selected;p['EXPECTED_CHECKS']=vp.expected_checks(job['resolved_brief'],selected,role);p['ROLE_RUBRIC']=vp.rubric(config,role,job['resolved_brief']);work.append((persona+'-'+task,task,p))
 with ThreadPoolExecutor(max_workers=3) as pool:
  futures={pool.submit(call,*w):w[1] for w in work}
  for f in as_completed(futures):
   task=futures[f];value=f.result()
   if value is None:raise SystemExit('Stop: API failure, not an audit pass')
   for audit in value['audits']:job['specialist_audits'].setdefault(audit['candidate_id'],{})[vp.ROLES[task]]=audit
 p=copy.deepcopy(rec('VP08',rid)['payload']);p['CANDIDATE_BATCH']=selected;p['VALIDATED_SPECIALIST_AUDITS']=job['specialist_audits'];p['VALIDATED_GATE_SUMMARY']={cid:vp.gate_summary(roles) for cid,roles in job['specialist_audits'].items()};p['HARMONY_RUBRIC']=vp.rubric(config,'harmony',job['resolved_brief']);p['SCORING_CONFIG']['source_numerator_terms']={cid:{role:p['SCORING_CONFIG']['weights'][role]*item['score'] for role,item in roles.items() if item['score'] is not None} for cid,roles in job['specialist_audits'].items()}
 value=call(persona+'-VP08','VP08',p)
 if value is None:raise SystemExit('Stop: harmony API failure')
 for audit in value['audits']:
  audit['reported_harmony_score']=audit['harmony_score'];audit['reported_total']=audit['proposed_total'];audit['score_100']=audit['proposed_total'];job['harmony_audits'][audit['candidate_id']]=audit
 job['ranking']=vp.rank_reported(selected,job['specialist_audits'],job['harmony_audits'],config)
 for packet in job['image_prompts']:
  c=next(c for c in selected if c['candidate_id']==packet['candidate_id']);packet['prompt']=c['image_prompt']
 save(persona+'-audited-job',job)
print('Final selected-prompt overall audit completed',flush=True)
