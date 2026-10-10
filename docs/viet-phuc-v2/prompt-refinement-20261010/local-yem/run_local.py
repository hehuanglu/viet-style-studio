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
provider=GeminiProvider(getpass.getpass('Gemini API key (hidden): '),evidence_dir=ROOT/'backend/evidence/prompt-refinement-20261010-local-yem')
def call(name,task,payload):
 schema=contracts.schema(vp.SCHEMAS[task]);cfg=dict(config['tasks'][task],structured=True,web_tools=False)
 if task in vp.ROLES:schema=vp.audit_response_schema(schema,payload['CANDIDATE_BATCH']);payload['CANDIDATE_BATCH']=vp.audit_candidates(payload['CANDIDATE_BATCH'])
 if task=='VP08':schema=vp.harmony_response_schema(schema)
 prompt=prompts.render(task,payload);save(name+'-input',dict(task=task,payload=payload,prompt=prompt,schema=schema,config=cfg,template_version=prompts.version))
 try:
  value,usage,metadata=provider.structured_v2(task,prompts.system,prompt,schema,payload,110,cfg);save(name+'-output',dict(value=value,usage=usage,metadata=metadata));print(name,'done',flush=True);return value
 except Exception as exc:
  save(name+'-error',dict(code=getattr(exc,'code',None),message=str(exc)));print(name,'failed',flush=True);return None

p=copy.deepcopy(rec('VP02',SPARSE)['payload']);extra=' Muốn tham khảo cách chuyển thể áo yếm nếu phù hợp; đi học phải che kín vai, ngực, eo và lưng, không mặc áo yếm độc lập.'
p['USER_TURNS'][0]['text']+=extra;p['CLEAN_PROMPT']['clean_text']+=extra
p['CLEAN_PROMPT']['domains'].append({'domain_id':'LOCAL_YEM','label':'Chuyển thể áo yếm','summary':extra.strip(),'related_domain_ids':[]})
for aid,intent,quote in [('LOCAL_YEM_EXAMPLE','example','Muốn tham khảo cách chuyển thể áo yếm nếu phù hợp'),('LOCAL_SCHOOL_COVER','must','đi học phải che kín vai, ngực, eo và lưng'),('LOCAL_NO_YEM_ALONE','avoid','không mặc áo yếm độc lập')]:
 a={'atom_id':aid,'domain_ids':['LOCAL_YEM'],'meaning':quote,'intent_type':intent,'polarity':'negative' if intent=='avoid' else 'positive','source_refs':[{'turn_id':'T1','quote':quote}],'resolution':'explicit','supersedes_atom_ids':[]};p['CLEAN_PROMPT']['atoms'].append(a);p['CLEAN_PROMPT']['coverage'].append({'source_ref':a['source_refs'][0],'atom_ids':[aid],'disposition':'example' if intent=='example' else 'retained','reason':'Synthetic local regression input, not a VP01 output.'})
v=call('school-yem-checklist','VP02',p)
if v is None:raise SystemExit('API failed')
rows=[{'group':g['label'],'label':o['label'],'description':o['description'],'decision_text':o['decision_text']} for g in v['groups'] for o in g['options'] if not o['is_ai_delegate']]
save('options-for-sol-review',rows);print(json.dumps(rows,ensure_ascii=False),flush=True)
