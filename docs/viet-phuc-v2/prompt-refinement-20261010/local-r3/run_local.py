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
provider=GeminiProvider(getpass.getpass('Gemini API key (hidden): '),evidence_dir=ROOT/'backend/evidence/prompt-refinement-20261010-local-r3')
def call(name,task,payload):
 schema=contracts.schema(vp.SCHEMAS[task]);cfg=dict(config['tasks'][task],structured=True,web_tools=False)
 if task in vp.ROLES:schema=vp.audit_response_schema(schema,payload['CANDIDATE_BATCH']);payload['CANDIDATE_BATCH']=vp.audit_candidates(payload['CANDIDATE_BATCH'])
 if task=='VP08':schema=vp.harmony_response_schema(schema)
 prompt=prompts.render(task,payload);save(name+'-input',dict(task=task,payload=payload,prompt=prompt,schema=schema,config=cfg,template_version=prompts.version))
 try:
  value,usage,metadata=provider.structured_v2(task,prompts.system,prompt,schema,payload,110,cfg);save(name+'-output',dict(value=value,usage=usage,metadata=metadata));print(name,'done',flush=True);return value
 except Exception as exc:
  save(name+'-error',dict(code=getattr(exc,'code',None),message=str(exc)));print(name,'failed',flush=True);return None
work=[]
for name,task,rid,one in [('quote-full-fashion','VP05',FULL,False),('quote-full-culture','VP06',FULL,False),('score-sparse-fashion','VP05',SPARSE,True),('score-sparse-art','VP07',SPARSE,True),('total-sparse','VP08',SPARSE,True)]:
 p=copy.deepcopy(rec(task,rid)['payload'])
 if one:
  p['CANDIDATE_BATCH']=p['CANDIDATE_BATCH'][:1];cid=p['CANDIDATE_BATCH'][0]['candidate_id']
  if task=='VP08':p['VALIDATED_SPECIALIST_AUDITS']={cid:p['VALIDATED_SPECIALIST_AUDITS'][cid]};p['VALIDATED_GATE_SUMMARY']={cid:p['VALIDATED_GATE_SUMMARY'][cid]}
 work.append((name,task,p))
p=copy.deepcopy(rec('VP05',SPARSE)['payload']);base=p['CANDIDATE_BATCH'][0];cs=[]
for label,extra in [('missing',''),('present',', chất liệu và cấu tạo ưu tiên dễ giặt')]:
 c=copy.deepcopy(base);c['candidate_id']='LOCAL-'+label;c['image_prompt']='Trang phục nữ đi học đại học, áo ngắn cổ kín tay dài màu xanh chàm, vải cotton nhẹ và thoáng'+extra+'. Mặt trước áo trơn; mặt sau lưng kín không trang trí. Một người mẫu cùng bộ đồ qua mặt trước và mặt sau trong hai ô.';c['fashion_summary']=c['image_prompt'];c['art_summary']=c['image_prompt'];c['culture_summary']='Thiết kế sáng tạo, không phục dựng lịch sử.';c['design_sections']=[];c['claims']=[];c['locked_coverage']=[];c['content_hash']=vp.content_hash(c);cs.append(c)
p['CANDIDATE_BATCH']=cs;p['EXPECTED_CHECKS']=[{'check_id':'locked:TEST_COMPOUND','owner_role':'fashion','severity':'hard','applicability':True,'content':'Chất liệu nhẹ, thoáng, dễ giặt.'}];p['RESOLVED_BRIEF']['locked_atom_ids']=['TEST_COMPOUND'];a=copy.deepcopy(p['RESOLVED_BRIEF']['atoms'][0]);a.update(atom_id='TEST_COMPOUND',meaning='Chất liệu nhẹ, thoáng, dễ giặt.',intent_type='must');p['RESOLVED_BRIEF']['atoms']=[a];p['RESOLVED_BRIEF']['resolved_text']='Trang phục nữ đi học đại học, chất liệu nhẹ, thoáng, dễ giặt.';work.append(('compound-control','VP05',p))
summary={}
with ThreadPoolExecutor(max_workers=3) as pool:
 futures={pool.submit(call,*w):(w[0],w[1],w[2]) for w in work}
 for f in as_completed(futures):
  name,task,p=futures[f];value=f.result();row={'api_success':value is not None}
  if value and task in vp.ROLES:
   byid={c['candidate_id']:c for c in p['CANDIDATE_BATCH']};row['quote_mismatches']=[];row['score_mismatches']=[];row['check_statuses']={}
   for a in value['audits']:
    for c in a['checks']:
     if c['prompt_quote'] and c['prompt_quote'] not in byid[a['candidate_id']]['image_prompt']:row['quote_mismatches'].append(dict(candidate_id=a['candidate_id'],check_id=c['check_id'],quote=c['prompt_quote']))
    score=vp.ratings_score(a['criterion_ratings'],p['ROLE_RUBRIC'])
    if a['score']!=score:row['score_mismatches'].append(dict(candidate_id=a['candidate_id'],reported=a['score'],calculated=score))
    row['check_statuses'][a['candidate_id']]={c['check_id']:c['status'] for c in a['checks']}
  if value and task=='VP08':
   row['math']=[]
   for a in value['audits']:
    h=vp.ratings_score(a['harmony_ratings'],p['HARMONY_RUBRIC']);total=vp.total_score(a['source_scores'],a['harmony_score'],p['SCORING_CONFIG']['weights']);row['math'].append(dict(candidate_id=a['candidate_id'],harmony=a['harmony_score'],calculated_harmony=h,total=a['proposed_total'],calculated_total=total))
  summary[name]=row
save('objective-summary',summary)
print(json.dumps(summary,ensure_ascii=False),flush=True)
