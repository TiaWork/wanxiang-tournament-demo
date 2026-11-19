let state=null;
let activeTab='schedule';
let selectedFile=null;
let uploading=false;
const app=document.getElementById('c-app');
const modal=document.getElementById('c-modal');
const modalBody=document.getElementById('c-modal-body');

function esc(value){return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
function toast(text){const el=document.getElementById('c-toast');el.textContent=text;el.hidden=false;clearTimeout(el.timer);el.timer=setTimeout(()=>el.hidden=true,2400)}
async function request(url,options={}){const response=await fetch(url,options);const data=await response.json();if(!response.ok)throw new Error(data.error||'操作失败');return data}
async function refresh(silent=false){try{state=await request('/api/state');render();if(!silent&&activeTab==='messages')await markRead()}catch(error){if(!silent)toast(error.message)}}
function user(){return state.current_user}
function stats(){return state.stats[user().uid]}
function currentMatches(){return state.matches.filter(m=>m.group_id===state.group.id&&m.round<=state.event.daily_matches).sort((a,b)=>a.round-b.round)}
function openModal(html){modalBody.innerHTML=html;modal.hidden=false}
function closeModal(){modal.hidden=true;selectedFile=null}

function render(){
  document.getElementById('c-event-date').textContent=`${state.event.stage} · ${state.event.date_range}`;
  document.querySelector('.event-kicker').textContent=`${state.event.game} · ${state.event.season}`;
  document.getElementById('c-unread').hidden=state.unread===0;
  const view=state.event.c_view;
  document.querySelector('.c-tabs').hidden=['signup','stage_signup','before_stage','ended'].includes(view);
  if(view==='signup'){renderSignupPage(false);return}
  if(view==='stage_signup'){renderSignupPage(true);return}
  if(view==='before_stage'||view==='ended'){app.innerHTML=`<section class="c-card c-empty"><div class="empty-icon">♟</div><h3>${view==='before_stage'?'当前赛段尚未开始':'当前赛段已结束'}</h3><p class="c-muted">赛段时间：${state.event.start_date} 至 ${state.event.end_date}<br>业务日期：${state.event.demo_date}。可在 运营切换业务日期查看对应页面。</p></section>`;return}
  document.querySelectorAll('.c-tabs button').forEach(btn=>btn.classList.toggle('on',btn.dataset.tab===activeTab));
  if(activeTab==='schedule')renderSchedule();
  if(activeTab==='upload')renderUpload();
  if(activeTab==='ranking')renderRanking();
  if(activeTab==='messages')renderMessages();
}

function renderSchedule(){
  const s=stats(),e=state.event,u=user();
  const progress=Math.min(100,Math.round(s.valid_days/e.min_valid_days*100));
  const matches=currentMatches();
  let advanceText=`${e.stage}进行中`;
  if(u.advance_official)advanceText='已正式晋级';
  else if(s.expected_advance)advanceText='预计晋级 · 待发布';
  else if(state.event.advancement_published)advanceText='未进入本次晋级名单';
  app.innerHTML=`
    <section class="c-card">
      <h3 class="c-card-title">我的海选进度 <small>UID ${esc(u.uid)} · 系统读取</small></h3>
      <div class="c-stat-grid"><div class="c-stat"><b>${s.valid_days}/${e.min_valid_days}</b><span>有效参赛日</span></div><div class="c-stat"><b>${s.total_score}</b><span>当前总积分</span></div><div class="c-stat"><b>${s.rank}</b><span>当前积分排名</span></div></div>
      <div class="c-progress"><div class="c-progress-bar" style="width:${progress}%"></div></div>
      <div class="c-muted">取最好 ${e.best_days} 天累计 · 晋级线 ${e.min_score} 分 · 名额 ${e.advance_quota} 人</div>
      <div style="margin-top:10px"><span class="c-tag ${u.advance_official?'advance':s.expected_advance?'pending':''}">${advanceText}</span></div>
    </section>
    <section class="c-card">
      <h3 class="c-card-title">今日开黑房间 <small>${esc(state.group.date)} ${esc(state.group.session)} · 第 ${state.group.id} 组</small></h3>
      <div class="c-room"><div class="c-room-label">万象棋官方房间 · 四位房号</div><div class="c-room-number">${esc(state.group.room)}</div><button class="c-copy" data-action="copy-room">复制房间号</button></div>
      <p class="c-muted" style="margin-top:9px">请提前 10 分钟进房。房号如临时变更，点点消息与小队群会同步提醒。</p>
    </section>
    <section class="c-card">
      <h3 class="c-card-title">今日完赛进度 <small>${s.played}/${e.daily_matches} 局 · ${s.confirmed} 局已确认</small></h3>
      ${matches.map(m=>matchRow(m)).join('')}
      <p class="c-muted" style="margin-top:10px">完成全部 ${e.daily_matches} 局且赛果确认后，当日积分才生效；未打满则当天 0 分且不计有效参赛日。</p>
      <button class="c-secondary c-block-btn" data-action="go-upload">查看 / 上传本局战绩</button>
    </section>
    <section class="c-card">
      <h3 class="c-card-title">明日参赛确认 <small>确认后无需重复填写资料</small></h3>
      <div class="c-session-grid">${e.sessions.map(session=>`<button class="c-session ${u.next_session===session?'on':''}" data-action="confirm-session" data-session="${session}">${e.next_date}<br>${session} 场 ${u.next_session===session?'✓':''}</button>`).join('')}</div>
      <p class="c-muted" style="margin-top:9px">当前选择：${esc(u.next_session)} 场。点击另一场次即可更换，最新安排会同步更新。</p>
    </section>
    <section class="c-card">
      <h3 class="c-card-title">我的第 ${state.group.id} 组 <small>${esc(u.leader)}（UID ${esc(u.leader_uid||'—')}） · 点点小队群已创建</small></h3>
      <div class="c-member-row">${state.group.members.map(uid=>{const member=state.users.find(x=>x.uid===uid);return `<div class="c-member"><div class="c-avatar">${esc(member.nickname.slice(0,1))}</div>${esc(member.nickname)}</div>`}).join('')}</div>
    </section>
    ${u.advance_official?`<section class="c-card c-advance"><h3 class="c-card-title">正式晋级</h3><p class="c-muted">晋级名单已由运营发布。下一阶段资料与赛程将通过点点消息通知，请保持关注。</p></section>`:''}
    <button class="c-secondary c-block-btn" data-action="signup">查看 / 修改报名资料</button>`;
}

function matchRow(match){
  const result=match.results.find(r=>r.uid===user().uid);
  const status=match.status==='confirmed'?'<span class="c-tag confirmed">已确认</span>':match.status==='pending'?'<span class="c-tag pending">确认中</span>':'<span class="c-tag">等待上传</span>';
  const detail=match.status==='not_uploaded'?'小组第一上传结算截图':`第 ${result.rank} 名 · 待结算 ${result.points} 分`;
  return `<div class="c-match"><div class="c-match-round">第 ${match.round} 局</div><div class="c-match-info"><b>${detail}</b><span>${match.date} ${match.session} · 第 ${match.group_id} 组</span></div>${status}</div>`;
}

function renderUpload(){
  const matches=currentMatches();
  const target=matches.find(m=>m.status!=='confirmed')||matches[matches.length-1];
  app.innerHTML=`
    <section class="c-card">
      <h3 class="c-card-title">上传第 ${target.round} 局战绩 <small>仅小组第一上传</small></h3>
      <p class="c-muted" style="margin-bottom:12px">${target.date} ${target.session} · 第 ${target.group_id} 组 · 支持 JPG / PNG，最大 5MB</p>
      <label class="c-upload-zone" for="c-file"><strong>＋</strong><span id="c-file-label">选择游戏结算截图</span><input id="c-file" type="file" accept=".png,.jpg,.jpeg"><img id="c-preview" class="c-upload-preview" hidden></label>
      <p class="c-muted" style="margin-top:9px">提交后系统自动识别战绩，赛果确认后积分生效。</p>
      <button class="c-primary c-block-btn" data-action="upload" data-match="${target.id}" ${uploading||target.status==='confirmed'?'disabled':''}>${uploading?'正在上传…':target.status==='pending'?'重新上传战绩':target.status==='confirmed'?'本局战绩已确认':'上传战绩'}</button>
    </section>
    ${target.status!=='not_uploaded'?`<section class="c-card"><h3 class="c-card-title">本局战绩 <small>${target.status==='pending'?'确认中':'已确认'}</small></h3>${target.results.map(r=>`<div class="c-history-row"><span>第 ${r.rank} 名 · ${esc(r.nickname)}</span><span>${target.status==='confirmed'?`+${r.points} 已加分`:`待结算 ${r.points} 分`}</span></div>`).join('')}<p class="c-muted" style="margin-top:10px">${target.status==='pending'?'赛果正在确认中，确认后计入当日成绩。':'本局战绩已确认；当日全部局次确认后统一结算积分。'}</p></section>`:''}
    <section class="c-card"><h3 class="c-card-title">我的上传记录</h3>${matches.map(m=>{const result=m.results.find(r=>r.uid===user().uid);return `<div class="c-history-row"><span>第 ${m.round} 局 · ${m.date} ${m.session}</span><span>${m.status==='confirmed'?`已确认 · +${result?result.points:0} 分`:m.status==='pending'?'识别完成 · 确认中':'尚未上传'}</span></div>`}).join('')}</section>`;
}

function renderRanking(){
  if(!state.event.ranking_published){
    app.innerHTML=`<section class="c-card c-empty"><div class="empty-icon">♜</div><h3>榜单尚未发布</h3><p class="c-muted">运营晋级管理确认榜单后，这里才会对外展示。<br>榜单发布与正式晋级发布是两个独立动作。</p></section>`;return;
  }
  app.innerHTML=`<section class="c-card"><h3 class="c-card-title">海选积分榜单 <small>由 运营确认发布</small></h3><p class="c-muted" style="margin-bottom:8px">按总积分自动排序，榜单排名不等于正式晋级结果。</p>${state.ranking.map((uid,index)=>{const u=state.users.find(x=>x.uid===uid),s=state.stats[uid];return `<div class="c-rank-row ${uid===user().uid?'me':''}"><div class="c-rank-no ${index<3?'top':''}">${index+1}</div><div class="c-rank-name">${esc(u.nickname)}${uid===user().uid?'（我）':''}<small>有效日 ${s.valid_days} · 计入 ${s.counted_days} 天</small></div><div class="c-rank-score">${s.total_score} 分</div></div>`}).join('')}</section>`;
}

function renderMessages(){
  const messages=state.messages.filter(m=>m.uid===user().uid);
  app.innerHTML=`<section class="c-card"><h3 class="c-card-title">点点赛事消息 <small>${messages.length} 条</small></h3>${messages.length?messages.map(m=>`<div class="c-message"><div class="c-message-icon">赛</div><div class="c-message-body"><div class="c-message-title">${esc(m.title)}<time>${esc(m.time)}</time></div><p>${esc(m.content)}</p></div></div>`).join(''):'<div class="c-empty">暂无赛事消息</div>'}</section>`;
}

function showRules(){
  const e=state.event;
  openModal(`<h2>赛事规则</h2><p class="modal-desc">以下为当前赛段规则，如有调整以最新公告为准。</p><div class="c-rules"><h4>有效参赛日</h4>每天选择一个场次，完成全部 ${e.daily_matches} 局且赛果均确认后，计为 1 个有效参赛日。未打满当天要求局数，当天 0 分且不计有效天数。<h4>积分累计</h4>至少完成 ${e.min_valid_days} 个有效参赛日，取成绩最好的 ${e.best_days} 天累计。单局积分依次为 ${e.points.join(' / ')} 分。<h4>榜单与晋级</h4>总积分达到 ${e.min_score} 分后，按积分排名最多晋级 ${e.advance_quota} 人。榜单与晋级名单分别发布，预计晋级不等于正式晋级。<h4>战绩识别与确认</h4>提交结算截图后，系统自动识别本场名次。赛果确认后积分生效，如对结果有疑问可联系领队反馈。</div>`);
}

function signupFieldsHtml(stageMode){
  const u=user(),e=state.event;
  const values=stageMode?(u.stage_signup_values?.[e.stage_id]||{}):u;
  const keys=stageMode&&e.stage_registration_fields.length?e.stage_registration_fields:e.registration_fields;
  const definitions={wechat:['微信号','请输入微信号'],phone:['手机号','请输入手机号'],game_nick:['游戏昵称（微信 / Q 区）','请输入游戏昵称'],game_id:['游戏 ID（编号）','请输入游戏内昵称下方编号']};
  let html='';
  if(keys.includes('contact')){
    const contactType=values.contact_type||u.contact_type||'微信';
    const contactValue=values.contact_value||u.contact_value||u.wechat||'';
    html+=`<div class="c-field"><label>联系方式（微信 / QQ 二选一） *</label><div class="c-form-2"><select name="contact_type" id="c-contact-type"><option ${contactType==='微信'?'selected':''}>微信</option><option ${contactType==='QQ'?'selected':''}>QQ</option></select><input name="contact_value" id="c-contact-value" value="${esc(contactValue)}" placeholder="请输入微信号" required></div><p class="c-muted">只需填写当前选择的一种账号，切换类型后请重新填写。</p></div>`;
  }
  html+=keys.filter(key=>definitions[key]).map(key=>`<div class="c-field"><label>${definitions[key][0]}</label><input name="${key}" value="${esc(values[key]||u[key]||'')}" placeholder="${definitions[key][1]}" required></div>`).join('');
  if(keys.includes('channel'))html+=`<div class="c-field"><label>游戏账号渠道</label><select name="channel"><option ${(values.channel||u.channel)==='微信'?'selected':''}>微信</option><option ${(values.channel||u.channel)==='QQ'?'selected':''}>QQ</option></select></div>`;
  const custom=stageMode?e.stage_custom_fields:e.custom_fields;
  html+=custom.map(field=>`<div class="c-field"><label>${esc(field.label)}${field.required?' *':'（选填）'}</label>${field.type==='select'?`<select name="${field.id}" ${field.required?'required':''}><option value="">请选择</option>${field.options.map(option=>`<option ${values[field.id]===option?'selected':''}>${esc(option)}</option>`).join('')}</select>`:`<input name="${field.id}" value="${esc(values[field.id]||'')}" placeholder="请输入${esc(field.label)}" ${field.required?'required':''}>`}</div>`).join('');
  if(keys.includes('wechat_qr')||keys.includes('game_shot'))html+='<p class="c-muted">图片资料在本地 Demo 中以示例文件模拟上传。</p><div class="c-form-2"><div class="c-field"><label>微信二维码</label><input value="已上传示例二维码.png" readonly></div><div class="c-field"><label>游戏主页截图</label><input value="已上传游戏主页.png" readonly></div></div>';
  return html;
}
function bindSignupForm(stageMode){
  const contactType=document.getElementById('c-contact-type');
  if(contactType)contactType.addEventListener('change',()=>{const input=document.getElementById('c-contact-value');input.value='';input.placeholder=contactType.value==='QQ'?'请输入 QQ 号':'请输入微信号'});
  document.getElementById('c-signup-form').addEventListener('submit',async event=>{event.preventDefault();const data=Object.fromEntries(new FormData(event.target).entries());try{state=await request(stageMode?'/api/stage/signup':'/api/signup',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});closeModal();activeTab='schedule';render();toast(stageMode?'赛段报名已完成，赛程已开放':'报名资料已保存，运营可查看')}catch(error){toast(error.message)}});
}
function renderSignupPage(stageMode){
  const e=state.event;
  app.innerHTML=`<section class="c-card"><h3 class="c-card-title">${stageMode?`${esc(e.stage)}赛段报名`:'S2 点点棋王杯报名信息'} <small>UID ${esc(user().uid)} · 系统读取</small></h3><p class="c-muted" style="margin-bottom:14px">${stageMode?'本赛段要求重新报名，字段由该赛段独立配置。':'当前为赛事报名期，仅开放报名页。资料仅首次收集，后续赛段按配置决定是否需要再次报名。'}</p><form id="c-signup-form" class="c-form">${signupFieldsHtml(stageMode)}<button class="c-primary c-block-btn" type="submit">${stageMode?'提交赛段报名':'确认报名并保存'}</button></form></section>`;
  bindSignupForm(stageMode);
}
function showSignup(){
  const e=state.event;
  openModal(`<h2>S2 点点棋王杯报名信息</h2><p class="modal-desc">UID ${esc(user().uid)} 由系统读取。${e.signup_open?'当前可编辑报名资料。':'赛事报名已截止，资料仅供查看。'}</p><form id="c-signup-form" class="c-form">${signupFieldsHtml(false)}${e.signup_open?'<button class="c-primary c-block-btn" type="submit">确认报名并保存</button>':'<p class="c-muted">如需修改请联系运营，当前不可自行提交。</p>'}</form>`);
  if(e.signup_open)bindSignupForm(false);
}

async function markRead(){state=await request('/api/messages/read',{method:'POST'});document.getElementById('c-unread').hidden=true;renderMessages()}

document.querySelectorAll('.c-tabs button[data-tab]').forEach(btn=>btn.addEventListener('click',async()=>{activeTab=btn.dataset.tab;render();if(activeTab==='messages')await markRead()}));
document.addEventListener('click',async event=>{
  const btn=event.target.closest('[data-action]');if(!btn)return;
  const action=btn.dataset.action;
  if(action==='rules')showRules();
  if(action==='signup')showSignup();
  if(action==='close-modal')closeModal();
  if(action==='go-upload'){activeTab='upload';render()}
  if(action==='open-chat'){window.location.href='/c/chat'}
  if(action==='copy-room'){try{await navigator.clipboard.writeText(state.group.room);toast(`房间号 ${state.group.room} 已复制`)}catch{toast(`房间号：${state.group.room}`)}}
  if(action==='confirm-session'){try{state=await request('/api/confirm-session',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({session:btn.dataset.session})});render();toast(`已确认明日 ${btn.dataset.session} 场，运营已同步`)}catch(error){toast(error.message)}}
  if(action==='upload'){
    if(uploading)return;uploading=true;render();
    try{const form=new FormData();form.append('match_id',btn.dataset.match);if(selectedFile)form.append('screenshot',selectedFile);state=await request('/api/upload',{method:'POST',body:form});selectedFile=null;toast('战绩已提交，等待赛果确认')}catch(error){toast(error.message)}finally{uploading=false;render()}
  }
});
document.addEventListener('change',event=>{if(event.target.id!=='c-file')return;selectedFile=event.target.files[0]||null;if(!selectedFile)return;document.getElementById('c-file-label').textContent=selectedFile.name;const preview=document.getElementById('c-preview');preview.src=URL.createObjectURL(selectedFile);preview.hidden=false});
modal.addEventListener('click',event=>{if(event.target===modal)closeModal()});
refresh();
setInterval(()=>{if(modal.hidden&&!uploading)refresh(true)},5000);
