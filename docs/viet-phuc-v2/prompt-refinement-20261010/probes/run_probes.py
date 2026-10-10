#!/usr/bin/env python3
"""Live template probes and bounded replays; credential read only from hidden stdin."""
import copy, getpass, json, sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
ROOT=Path(__file__).resolve().parents[4];sys.path.insert(0,str(ROOT/'backend'))
from arena_backend import viet_phuc as vp
from arena_backend.providers import GeminiProvider
from arena_backend.core import Contracts
OUT=Path(__file__).parent
prompts=vp.VPPrompts(); config=json.loads((vp.DATA/'config.json').read_text());contracts=Contracts(vp.DATA/'contracts.json')
records=[json.loads(f.read_text()) for f in (ROOT/'backend/evidence/prompt-refinement-20261010-r1/vp-task-inputs').glob('*.json')]
def record(task, rid):
 return next(r for r in records if r['task']==task and r['request_id']==rid)
def save(name,value):
 (OUT/(name+'.json')).write_text(json.dumps(value,ensure_ascii=False,indent=2))
provider=GeminiProvider(getpass.getpass('Gemini API key (hidden): '),evidence_dir=ROOT/'backend/evidence/prompt-refinement-20261010-probes')
def call(name,task,payload):
 schema=contracts.schema(vp.SCHEMAS[task]); cfg=dict(config['tasks'][task],structured=True,web_tools=False);prompt=prompts.render(task,payload)
 save(name+'-input',dict(task=task,payload=payload,prompt=prompt,schema=schema,config=cfg,template_version=prompts.version))
 try:
  value,usage,metadata=provider.structured_v2(task,prompts.system,prompt,schema,payload,100,cfg)
  save(name+'-output',dict(value=value,usage=usage,metadata=metadata));print(name,'done',flush=True);return value
 except Exception as exc:
  save(name+'-error',dict(type=type(exc).__name__,code=getattr(exc,'code',None),message=str(exc))); print(name,'failed',flush=True);return None
SPARSE='13920343-ddc9-4374-8b62-e59e989a4d89';ADV='1d9c0b9e-a3c0-4ae4-9c21-9a5754a01a2a'
work=[]
for task in ['VP05','VP06','VP07']:
 p=copy.deepcopy(record(task,SPARSE)['payload']); p['CANDIDATE_BATCH']=vp.audit_candidates(p['CANDIDATE_BATCH'][:1]);p['EXPECTED_CHECKS']=vp.expected_checks(p['RESOLVED_BRIEF'],p['CANDIDATE_BATCH'],vp.ROLES[task]);work.append(('arithmetic-'+task,task,p))
p=copy.deepcopy(record('VP03',ADV)['payload']);work.append(('historical-no-sources','VP03',p))
p=copy.deepcopy(record('VP02C',ADV)['payload']);p['CURRENT_SELECTIONS']['explicit_changes']=[{'atom_id':'A_04','replacement_text':'Cùng cổ áo, cùng lớp và cùng phần ngực: bắt buộc che kín toàn bộ ngực; đồng thời khoét chữ V sâu để chính phần ngực đó hở trực tiếp, không vải phủ, không cổ giả, không lớp trong.','confirmed':'yes'}];work.append(('severe-same-feature','VP02C',p))
p=copy.deepcopy(p);p['CURRENT_SELECTIONS']['explicit_changes']=[{'atom_id':'A_04','replacement_text':'Áo trong có cổ kín cao; áo ngoài cổ chữ V sâu; phần ngực vẫn được lớp trong che kín.','confirmed':'yes'},{'atom_id':'A_05','replacement_text':'Cho phép hai lớp áo nhẹ, trong cổ kín và ngoài chữ V.','confirmed':'yes'}];work.append(('benign-two-layers','VP02C',p))
results={}
with ThreadPoolExecutor(max_workers=3) as pool:
 futures={pool.submit(call,*item):item[0] for item in work}
 for f in as_completed(futures):results[futures[f]]=f.result()
if all(results.get('arithmetic-'+t) for t in ['VP05','VP06','VP07']):
 p=copy.deepcopy(record('VP08',SPARSE)['payload']);p['CANDIDATE_BATCH']=p['CANDIDATE_BATCH'][:1];cid=p['CANDIDATE_BATCH'][0]['candidate_id'];audits={vp.ROLES[t]:results['arithmetic-'+t]['audits'][0] for t in ['VP05','VP06','VP07']};p['VALIDATED_SPECIALIST_AUDITS']={cid:audits};p['VALIDATED_GATE_SUMMARY']={cid:vp.gate_summary(audits)};call('arithmetic-VP08','VP08',p)
# Missing compound requirement probe; full pipeline data is unnecessary to expose this case.
p=copy.deepcopy(work[0][2]);c=p['CANDIDATE_BATCH'][0];c['image_prompt']='Trang phục nữ đi học đại học, áo ngắn cổ kín tay dài màu xanh chàm, vải cotton nhẹ và thoáng. Mặt trước áo trơn; mặt sau lưng kín không trang trí. Một người mẫu cùng bộ đồ qua mặt trước và mặt sau trong hai ô.';c['verbatim_excerpt_bank']=vp.audit_candidates([c])[0]['verbatim_excerpt_bank'];c['fashion_summary']=c['image_prompt'];c['design_sections']=[];c['locked_coverage']=[];p['EXPECTED_CHECKS']=[{'check_id':'locked:TEST_COMPOUND','owner_role':'fashion','severity':'hard','applicability':True,'content':'Chất liệu nhẹ, thoáng, dễ giặt.'}];call('compound-missing-easy-wash','VP05',p)
