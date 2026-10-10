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
provider=GeminiProvider(getpass.getpass('Gemini API key (hidden): '),evidence_dir=ROOT/'backend/evidence/prompt-refinement-20261010-local-r5')
def call(name,task,payload):
 schema=contracts.schema(vp.SCHEMAS[task]);cfg=dict(config['tasks'][task],structured=True,web_tools=False)
 if task in vp.ROLES:schema=vp.audit_response_schema(schema,payload['CANDIDATE_BATCH']);payload['CANDIDATE_BATCH']=vp.audit_candidates(payload['CANDIDATE_BATCH'])
 if task=='VP08':schema=vp.harmony_response_schema(schema)
 prompt=prompts.render(task,payload);save(name+'-input',dict(task=task,payload=payload,prompt=prompt,schema=schema,config=cfg,template_version=prompts.version))
 try:
  value,usage,metadata=provider.structured_v2(task,prompts.system,prompt,schema,payload,110,cfg);save(name+'-output',dict(value=value,usage=usage,metadata=metadata));print(name,'done',flush=True);return value
 except Exception as exc:
  save(name+'-error',dict(code=getattr(exc,'code',None),message=str(exc)));print(name,'failed',flush=True);return None

import urllib.request
rid='b74d73f6-022b-479e-811e-a4448cf20b40';job=json.load(urllib.request.urlopen('http://127.0.0.1:8791/requests/'+rid));work=[];seen=set()
for r in records:
 if r['task']!='VP08' or r['request_id']!=rid or r['revision']!=6:continue
 p=copy.deepcopy(r['payload']);key=tuple(c['candidate_id'] for c in p['CANDIDATE_BATCH'])
 if key in seen:continue
 seen.add(key);p['HARMONY_RUBRIC']=vp.rubric(config,'harmony',p['RESOLVED_BRIEF']);p['SCORING_CONFIG']['source_numerator_terms']={cid:{role:p['SCORING_CONFIG']['weights'][role]*item['score'] for role,item in roles.items() if item['score'] is not None} for cid,roles in p['VALIDATED_SPECIALIST_AUDITS'].items()};p['SCORING_CONFIG']['source_numerator_subtotal']={cid:sum(terms.values()) for cid,terms in p['SCORING_CONFIG']['source_numerator_terms'].items()};work.append(('adversarial-'+p['CANDIDATE_BATCH'][0]['batch_id'],'VP08',p))
summary={}
with ThreadPoolExecutor(max_workers=2) as pool:
 futures={pool.submit(call,*w):w for w in work}
 for f in as_completed(futures):
  name,task,p=futures[f];v=f.result()
  if v is None:raise SystemExit('Stop: task API failure')
  rows=[]
  for a in v['audits']:
   h=vp.ratings_score(a['harmony_ratings'],p['HARMONY_RUBRIC']);total=vp.total_score(a['source_scores'],a['harmony_score'],p['SCORING_CONFIG']['weights']);rows.append({'candidate_id':a['candidate_id'],'harmony':a['harmony_score'],'calculated_harmony':h,'total':a['proposed_total'],'calculated_total':total});a.update(reported_harmony_score=a['harmony_score'],reported_total=a['proposed_total'],score_100=a['proposed_total']);job['harmony_audits'][a['candidate_id']]=a
  summary[name]=rows
save('objective-summary',summary)
from arena_backend.viet_phuc_adapter import adapt
job['ranking']=vp.rank_reported(job['prompt_pool'],job['specialist_audits'],job['harmony_audits'],config);adapt(job,job['ranking']);job['audit_scope']='Production workflow to revision6; only VP08 replayed after focused arithmetic repair.'
final=ROOT/'docs/viet-phuc-v2/prompt-refinement-20261010/final';old=final/'adversarial-audited-job.json';(final/'adversarial-pre-vp08-refinement.json').write_bytes(old.read_bytes());old.write_text(json.dumps(job,ensure_ascii=False,indent=2));print(json.dumps(summary,ensure_ascii=False),flush=True)
