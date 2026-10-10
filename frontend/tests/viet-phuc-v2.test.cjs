const assert = require('node:assert/strict');
const fs = require('node:fs');
const vm = require('node:vm');
const path = require('node:path');
const selectors = new Map();
const copies = [];
const panel = {hidden:true, querySelector() {return {value:'Nguyên văn\nKhông tự đổi màu.',focus(){},select(){}};}};
const status = {textContent:''};
const parent = {querySelector(s){return s === '.option-prompt-textarea' ? panel : status;}};
function button(dataset) {return {dataset, parentElement:parent, closest(){return parent;}, textContent:'Copy prompt', events:{}, setAttribute(){}, addEventListener(name, fn){this.events[name]=fn;}};}
const copyButton=button({copyOption:'0'}), viewButton=button({viewOption:'0'});
const cards = {innerHTML:'',querySelector(){return copyButton;},querySelectorAll(s){return s === '[data-copy-option]' ? [copyButton] : s === '[data-view-option]' ? [viewButton] : [];}};
const context=vm.createContext({
  document:{querySelector(s){if(s==='#cards')return cards;if(!selectors.has(s))selectors.set(s,{addEventListener(){},classList:{add(){},remove(){},toggle(){}},value:'',hidden:false,style:{setProperty(){}},setAttribute(){},getAttribute(){return 'false';},querySelector(){return {textContent:''};}});return selectors.get(s);},querySelectorAll(){return[];}},
  navigator:{clipboard:{async writeText(text){copies.push(text);}}},
  localStorage:{getItem(key){return key==='arena-session-id'?'session':null;},setItem(){}},
  location:{search:''},URLSearchParams,AbortController,crypto:{randomUUID(){return'id';}},
  fetch(){return new Promise(()=>{});},setInterval(){},clearInterval(){},
});
vm.runInContext(fs.readFileSync(path.join(__dirname,'../app.js'),'utf8'),context);
const job={request_id:'r',workflow_version:2,status:'complete',cards:[{candidate_id:'c',title:'Phom mới',score:84.4,image_prompt:'Nguyên văn\nKhông tự đổi màu.',fashion_summary:'Phom',culture_summary:'Cảm hứng',art_summary:'Nhịp',specialist_reviews:{fashion:{score:82,summary:'F'},culture:{score:78,summary:'C'},art:{score:90,summary:'A'}},harmony:{harmony_score:84,summary:'H'}}]};
context.fixture=job;
vm.runInContext('renderCards(fixture)',context);
assert.match(cards.innerHTML,/Thời trang \/ cấu trúc/);
assert.match(cards.innerHTML,/Văn hóa \/ lịch sử/);
assert.match(cards.innerHTML,/Hội họa \/ mỹ thuật/);
assert.doesNotMatch(cards.innerHTML,/\/100|class="score"|84\.4/);
assert.match(cards.innerHTML,/<summary>Nhận xét AI<\/summary>/);
assert.match(cards.innerHTML,/Câu chuyện thiết kế/);
assert.doesNotMatch(cards.innerHTML,/Đánh giá tổng hợp/);
assert.match(cards.innerHTML,/Chưa có câu chuyện thiết kế/);
job.cards[0].design_story={origin_and_meaning:'Cảm hứng từ <áo> & nét Việt.',cultural_combination_warnings:['Không gán <biểu tượng> chưa xác minh.']};
vm.runInContext('renderCards(fixture)',context);
assert.match(cards.innerHTML,/Cảm hứng từ &lt;áo&gt; &amp; nét Việt\./);
assert.match(cards.innerHTML,/Lưu ý kết hợp văn hóa/);
assert.match(cards.innerHTML,/Không gán &lt;biểu tượng&gt; chưa xác minh\./);
assert.doesNotMatch(cards.innerHTML,/<áo>|<biểu tượng>|Đánh giá tổng hợp/);
context.usageFixture={workflow_version:2,status:'specialist_auditing',api_call_warnings:['Tiến trình đã thực hiện 100 lượt gọi Gemini API. Quy trình vẫn tiếp tục.'],warnings:[]};
vm.runInContext('renderWarnings(usageFixture)',context);
assert.match(selectors.get('#warnings').innerHTML, /role="status"/);
assert.match(selectors.get('#warnings').innerHTML, /100 lượt gọi/);
assert.doesNotMatch(selectors.get('#warnings').innerHTML, /<details>/);
context.quotaError={code:'google_http_429',message:'You exceeded your current quota'};
const quota=vm.runInContext('errorGuidance(quotaError)',context);
assert.match(quota.message,/giới hạn sử dụng/);assert.match(quota.next,/hạn mức API/);
assert.doesNotMatch(quota.message,/invalid key|sai key|You exceeded/);
vm.runInContext('showRequestError(quotaError)',context);
assert.match(selectors.get('#request-error').innerHTML,/<details><summary>Chi tiết kỹ thuật/);
assert.match(selectors.get('#request-error').innerHTML,/You exceeded/);
context.thirdChoice={status:'awaiting_image',workflow_version:2,cards:[{candidate_id:'1'},{candidate_id:'2'},{candidate_id:'3'}],artifacts:[],pending_manual:{step_id:'step'}};
assert.equal(vm.runInContext('shouldChooseCopiedCandidate(thirdChoice, thirdChoice.cards[2])',context),true);
context.thirdChoice.image_target_ids=['3'];
assert.equal(vm.runInContext('shouldChooseCopiedCandidate(thirdChoice, thirdChoice.cards[2])',context),false);
context.thirdChoice.image_target_ids=['1'];context.thirdChoice.artifacts=[{candidate_id:'1'}];
assert.equal(vm.runInContext('shouldChooseCopiedCandidate(thirdChoice, thirdChoice.cards[2])',context),false);
context.thirdChoice.artifacts=[{candidate_id:'old-revision'}];
assert.equal(vm.runInContext('shouldChooseCopiedCandidate(thirdChoice, thirdChoice.cards[2])',context),true);
job.status='awaiting_image';job.artifacts=[{candidate_id:'prior-revision'}];
vm.runInContext('renderCards(fixture)',context);assert.doesNotMatch(cards.innerHTML,/Chọn phương án này|data-view-option|Đánh giá AI hỗ trợ tham khảo/);assert.equal((cards.innerHTML.match(/<button /g)||[]).length,1);assert.match(cards.innerHTML,/>Copy prompt<\/button>/);
job.artifacts=[{candidate_id:'c'}];vm.runInContext('renderCards(fixture)',context);assert.doesNotMatch(cards.innerHTML,/Chọn phương án này/);
context.reference={label:'Fixture <chưa tìm>',description:'Giải thích vẫn đọc được',scope:'Chưa có nguồn',url:null,preview_url:null,discovery_status:'not_found'};
const missing=vm.runInContext('referenceMarkup(reference)',context);
assert.match(missing,/chưa tìm được link/);assert.match(missing,/<details><summary>Xem mẫu/);assert.match(missing,/role="tooltip"/);
assert.match(missing,/&lt;chưa tìm&gt;/);assert.doesNotMatch(missing,/<a |<img /);

const groupSpecs=[
  {group_id:'base',depends_on:[],options:[['one',false],['two',false],['ai',true]]},
  {group_id:'child',depends_on:[{group_id:'base',option_ids:['one']}],options:[['child-one',false],['child-ai',true]]},
  {group_id:'grandchild',depends_on:[{group_id:'child',option_ids:['child-one']}],options:[['grand-one',false],['grand-ai',true]]},
];
const sectionMap=new Map(groupSpecs.map(g=>{
  const inputs=g.options.map(([value,delegate])=>({value,checked:false,dataset:{delegate:String(delegate)},events:{},addEventListener(n,f){this.events[n]=f;}}));
  const custom={value:'',events:{},addEventListener(n,f){this.events[n]=f;}},field={disabled:false},inactive={hidden:true};
  return [g.group_id,{dataset:{group:g.group_id},inputs,custom,field,inactive,querySelector(s){return s==='fieldset'?field:s==='[data-custom]'?custom:inactive;},querySelectorAll(s){return s==='input:checked'?inputs.filter(i=>i.checked):s==='[data-delegate="true"]'?inputs.filter(i=>i.dataset.delegate==='true'):inputs;}}];
}));
const form={events:{},querySelectorAll(s){return s==='[data-group]'?[...sectionMap.values()]:[];},addEventListener(n,f){this.events[n]=f;}};
const box={hidden:true,innerHTML:'',querySelector(){return form;},replaceChildren(){}};selectors.set('#question-card',box);
context.checklistFixture={request_id:'form',revision:1,status:'awaiting_choices',checklist:{form_id:'new',references:[],clean_prompt:{clean_text:'Miền mở',atoms:[]},groups:groupSpecs.map(g=>({...g,status:'needs_choice',selection_mode:'multiple',min:1,max:2,label:g.group_id,question:'Chọn phần mở',why_it_matters:'Fixture',related_atom_ids:[],options:g.options.map(([id,ai])=>({option_id:id,is_ai_delegate:ai,label:id,description:'Fixture',reference_ids:[]}))}))}};
vm.runInContext('renderChecklist(checklistFixture)',context);
assert.match(vm.runInContext('choiceProblem(checklistFixture.checklist.groups, [])',context),/“base”/);
assert.equal(vm.runInContext('choiceProblem(checklistFixture.checklist.groups, [{group_id:"base",option_ids:["ai"],custom_text:""}])',context),'');
assert.doesNotMatch(box.innerHTML,/ checked[\s>]/);assert.equal(sectionMap.get('child').field.disabled,true);
const base=sectionMap.get('base'),child=sectionMap.get('child'),grand=sectionMap.get('grandchild');
base.inputs[0].checked=true;base.inputs[0].events.change();assert.equal(child.field.disabled,false);
child.inputs[0].checked=true;child.inputs[0].events.change();assert.equal(grand.field.disabled,false);
grand.inputs[0].checked=true;grand.custom.value='Ý con';base.inputs[0].checked=false;base.inputs[0].events.change();
assert.equal(child.field.disabled,true);assert.equal(grand.field.disabled,true);assert.equal(grand.inputs[0].checked,false);assert.equal(grand.custom.value,'');
base.inputs[0].checked=true;base.inputs[1].checked=true;base.custom.value='Custom';base.inputs[2].checked=true;base.inputs[2].events.change();
assert.deepEqual(base.inputs.map(i=>i.checked),[false,false,true]);assert.equal(base.custom.value,'');
base.custom.value='Ý tự nhập';base.custom.events.input();assert.equal(base.inputs[2].checked,false);
context.savedSnapshot={checklist:context.checklistFixture.checklist,choices:{selections:[{group_id:'base',option_ids:['ai'],custom_text:''},{group_id:'child',option_ids:[],custom_text:'Vải <mới>'}],explicit_changes:[]}};
assert.match(vm.runInContext('selectionSummary(savedSnapshot)',context),/Để AI đề xuất/);
assert.match(vm.runInContext('selectionSummary(savedSnapshot)',context),/Vải &lt;mới&gt;/);
context.checklistFixture.revision=2;
context.checklistFixture.choice_restore={selections:[{group_id:'base',option_ids:['one'],custom_text:''},{group_id:'child',option_ids:[],custom_text:'Ý đã chốt'}],explicit_changes:[]};
context.checklistFixture.previous_selection_snapshot=context.savedSnapshot;
vm.runInContext('renderChecklist(checklistFixture)',context);
assert.equal(base.inputs[0].checked,true);assert.equal(base.inputs[2].checked,false);
assert.equal(child.field.disabled,false);assert.equal(child.custom.value,'Ý đã chốt');
assert.match(box.innerHTML,/Đối chiếu lựa chọn trước/);
context.checklistFixture.status='generating';context.checklistFixture.choices=context.checklistFixture.choice_restore;
vm.runInContext('renderChecklist(checklistFixture)',context);
assert.equal(box.hidden,false);assert.match(box.innerHTML,/Lựa chọn đã chốt để đối chiếu/);assert.match(box.innerHTML,/Ý đã chốt/);
(async()=>{
  await copyButton.events.click();
  await copyButton.events.click();
  assert.deepEqual(copies,[job.cards[0].image_prompt,job.cards[0].image_prompt]);
  assert.equal(panel.hidden,true);assert.equal(copyButton.textContent,'Copy prompt');
  assert.equal(status.textContent,'Đã copy · dán vào Gemini');
  await copyButton.events.click();assert.equal(panel.hidden,true);assert.equal(copies.length,3);
  selectors.set('#request-error',{hidden:true});
  job.artifacts=[];job.pending_manual={step_id:"step"};
  vm.runInContext(`chooseImageCandidate = async (_job, candidate) => { activeJob = {image_target_ids:[candidate.candidate_id]}; };`,context);
  await copyButton.events.click();
  assert.equal(status.textContent,'Đã copy · đang nhận ảnh cho phương án này');
  assert.equal(selectors.get('#request-error').hidden,true);
  console.log('Passed: specialist cards, repeated exact copy, revision selection, missing reference details, no defaults, recursive dependencies, AI/custom exclusivity.');
})().catch(e=>{console.error(e);process.exitCode=1;});
