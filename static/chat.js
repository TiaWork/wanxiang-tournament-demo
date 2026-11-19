let state=null;
let view='list';
const app=document.getElementById('chat-app');
function esc(value){return String(value??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]))}
async function load(){state=await (await fetch('/api/state')).json();render()}
function latest(){return state.messages.find(m=>m.uid===state.current_uid)||state.messages[0]}
function render(){if(view==='list')renderList();if(view==='system')renderSystem();if(view==='group')renderGroup()}
function renderList(){
  const message=latest(),u=state.current_user;
  app.innerHTML=`<div class="chat-list">
    <button class="chat-item" data-view="system"><div class="chat-avatar system">喇叭</div><div class="chat-item-main"><div class="chat-name">系统消息</div><p>${esc(message.title)}：${esc(message.content)}</p></div><div class="chat-side"><time>${esc(message.time)}</time>${state.unread?`<span class="chat-unread">${state.unread}</span>`:''}</div></button>
    <button class="chat-item" data-view="group"><div class="chat-avatar group">小队</div><div class="chat-item-main"><div class="chat-name">万象棋小队·第 ${state.group.id} 群（${state.group.members.length} 人）</div><p>${esc(u.leader)}：今日 ${state.group.session} 场房间号 ${state.group.room}，请提前进房</p></div><div class="chat-side"><time>今天</time><span class="chat-unread">3</span></div></button>
    <button class="chat-item" data-view="group"><div class="chat-avatar leader">领队</div><div class="chat-item-main"><div class="chat-name">${esc(u.leader)}</div><p>UID ${esc(u.leader_uid)} · 已自动为你创建小队群，有问题随时找我</p></div><div class="chat-side"><time>昨天</time></div></button>
    <button class="chat-item" data-view="group"><div class="chat-avatar ops">运营</div><div class="chat-item-main"><div class="chat-name">运营-临温</div><p>我是运营，已加入你的赛事小队群，有问题随时找我</p></div><div class="chat-side"><time>周一</time></div></button>
  </div>`;
}
function renderSystem(){
  const messages=state.messages.filter(m=>m.uid===state.current_uid);
  app.innerHTML=`<div class="chat-subheader"><button data-view="list">‹</button><b>系统消息</b><span>站内信</span></div><div class="chat-system-list">${messages.map(m=>`<article class="chat-message-card"><div class="chat-message-title"><b>${esc(m.title)}</b><time>${esc(m.time)}</time></div><p>${esc(m.content)}</p><span>${m.read?'已读':'未读'}</span></article>`).join('')}</div>`;
  fetch('/api/messages/read',{method:'POST'}).then(load);
}
function renderGroup(){
  const u=state.current_user;
  app.innerHTML=`<div class="chat-subheader"><button data-view="list">‹</button><b>万象棋小队·第 ${state.group.id} 群</b><span>⋯</span></div><div class="group-chat"><div class="group-auto-note">绑定领队后系统自动创建小队群<br><b>${esc(u.leader)}（UID ${esc(u.leader_uid)}）</b>已成为群主，运营-临温已入群协助</div><div class="group-message"><div class="group-avatar">领队</div><div><small>${esc(u.leader)}</small><div class="group-bubble">各位好，我是本组领队。每天的场次和房间号我都会在这里提醒，有问题随时@我。</div></div></div><div class="group-message"><div class="group-avatar">领队</div><div><small>${esc(u.leader)}</small><div class="group-bubble room">【开赛提醒】今天 ${state.group.session} 场<br>房间号 <b>${state.group.room}</b><br>请提前 10 分钟进房，今日须完成全部 ${state.event.daily_matches} 局</div></div></div><div class="group-message mine"><div class="group-avatar">我</div><div><small>张小花</small><div class="group-bubble">收到，已复制房间号</div></div></div><div class="group-auto-note">领队已同步今日分组与房间号，点点站内信未读用户可在这里再次提醒</div><div id="group-custom"></div></div><form id="group-send" class="group-input"><input placeholder="输入消息…"><button type="submit">发送</button></form>`;
  document.getElementById('group-send').addEventListener('submit',event=>{event.preventDefault();const input=event.target.querySelector('input');if(!input.value.trim())return;document.getElementById('group-custom').insertAdjacentHTML('beforeend',`<div class="group-message mine"><div class="group-avatar">我</div><div><small>张小花</small><div class="group-bubble">${esc(input.value)}</div></div></div>`);input.value='';const custom=document.getElementById('group-custom');custom.scrollIntoView(false)});
}
document.addEventListener('click',event=>{const btn=event.target.closest('[data-view]');if(btn){view=btn.dataset.view;render()}});
load();
