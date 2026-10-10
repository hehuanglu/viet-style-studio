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
provider=GeminiProvider(getpass.getpass('Gemini API key (hidden): '),evidence_dir=ROOT/'backend/evidence/prompt-refinement-20261010-local-r4')
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
for name,task,rid in [('score-full-fashion','VP05',FULL),('score-full-culture','VP06',FULL),('total-sparse','VP08',SPARSE)]:
 p=copy.deepcopy(rec(task,rid)['payload']);p['CANDIDATE_BATCH']=p['CANDIDATE_BATCH'][:1];cid=p['CANDIDATE_BATCH'][0]['candidate_id']
 if task in vp.ROLES:p['ROLE_RUBRIC']=vp.rubric(config,vp.ROLES[task],p['RESOLVED_BRIEF'])
 if task=='VP08':
  p['VALIDATED_SPECIALIST_AUDITS']={cid:p['VALIDATED_SPECIALIST_AUDITS'][cid]};p['VALIDATED_GATE_SUMMARY']={cid:p['VALIDATED_GATE_SUMMARY'][cid]};p['HARMONY_RUBRIC']=vp.rubric(config,'harmony',p['RESOLVED_BRIEF']);p['SCORING_CONFIG']['source_numerator_terms']={r:p['SCORING_CONFIG']['weights'][r]*v['score'] for r,v in p['VALIDATED_SPECIALIST_AUDITS'][cid].items() if v['score'] is not None}
 work.append((name,task,p))
r=next(r for r in records if r['task']=='VP03' and r['request_id']=='b74d73f6-022b-479e-811e-a4448cf20b40' and r['revision']==5);work.append(('multiple-explicit-changes','VP03',copy.deepcopy(r['payload'])))
p=copy.deepcopy(rec('VP04',SPARSE)['payload']);job=json.loads((ROOT/'docs/viet-phuc-v2/prompt-refinement-20261010/round2/sparse-complete-job.json').read_text());ids={c['candidate_id'] for c in job['cards']};cs=[c for c in job['prompt_pool'] if c['candidate_id'] in ids];p['CANDIDATE_SLOTS']={'batch_id':'LOCAL_REPAIR_SPARSE','slots':[{'candidate_id':c['candidate_id'],'revision':c['revision']} for c in cs]};p['GENERATION_DIRECTION']={'mode':'repair_existing_text_only','instructions':'Chỉ sửa ba image_prompt đã cho: bổ sung mô tả cổ/lưng và đường may/độ trang trí mặt sau cho hai prompt thiếu; đổi chữ mặtหลัง thành mặt sau; nói đặc tính cotton lạnh là mục tiêu đề xuất, không xác nhận khả năng thấm hút đã kiểm chứng. Giữ nguyên loại áo, quần, bảng màu, hoa văn, phụ kiện, bối cảnh và từng candidate_id của mỗi phương án. Không tạo thiết kế khác. Tóm tắt phải trùng prompt đã sửa.','existing_candidates':cs};work.append(('sparse-text-repair','VP04',p))
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
  if value and task=='VP03':
   import urllib.request
   job=json.load(urllib.request.urlopen('http://127.0.0.1:8791/requests/b74d73f6-022b-479e-811e-a4448cf20b40'))
   try:contracts.validate(vp.SCHEMAS[task],value);vp.validate_resolved(value,job);row['contract_valid']=True
   except Exception as exc:row['contract_valid']=False;row['error']=str(exc)
   row['status']=value['status'];row['historical_mode']=value['historical_mode'];row['superseded_locked']=list(set(value['locked_atom_ids'])&{'atom_04','atom_09'})
  if value and task=='VP04':row['candidate_count']=len(value['candidates']);row['foreign_word_remains']=any('หลัง' in c['image_prompt'] for c in value['candidates']);row['back_descriptions']={c['candidate_id']:c['image_prompt'].lower().count('mặt sau') for c in value['candidates']}
  summary[name]=row
save('objective-summary',summary)
print(json.dumps(summary,ensure_ascii=False),flush=True)
