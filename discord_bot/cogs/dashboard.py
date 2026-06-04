"""Веб-дашборд: керування ботом з браузера (aiohttp, у процесі бота).

Вмикається лише якщо задано DASHBOARD_PASSWORD. За замовчуванням слухає 127.0.0.1.
Авторизація — пароль + сесійна кука. Для доступу ззовні — через тунель/HTTPS.

Можливості: статус, зараз грає (обкладинка + прогрес із перемоткою), транспорт
(пауза/скіп/стоп), гучність, loop, autoplay, аудіофільтр, повне керування чергою
(грати зараз / видалити / вгору-вниз / перемішати / очистити), додавання треків.
"""
import hmac
import logging
import random
import secrets

from aiohttp import web
from discord.ext import commands

from discord_bot import config
from discord_bot.cogs.music import AUDIO_FILTERS, _youtube_id
from discord_bot.settings import settings

log = logging.getLogger("bot.dashboard")

COOKIE = "dash_session"

LOGIN_HTML = """<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot — вхід</title><style>
:root{color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;height:100vh;display:flex;align-items:center;justify-content:center;
font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:#e6e9ef;
background:radial-gradient(1200px 600px at 70% -10%,#1b2740 0,#0b0e14 55%)}
form{background:rgba(22,27,39,.85);backdrop-filter:blur(12px);padding:36px 32px;
border-radius:18px;width:320px;text-align:center;border:1px solid #232a3a;
box-shadow:0 30px 80px -20px #000}
h1{font-size:20px;margin:0 0 6px;font-weight:800}
.sub{color:#8b95a7;font-size:13px;margin:0 0 20px}
input{width:100%;padding:12px 14px;border-radius:11px;border:1px solid #2a3142;
background:#0b0e14;color:#e6e9ef;margin-bottom:14px;font-size:15px;outline:none}
input:focus{border-color:#00d4ff;box-shadow:0 0 0 3px rgba(0,212,255,.15)}
button{width:100%;padding:12px;border:0;border-radius:11px;cursor:pointer;font-size:15px;
font-weight:800;color:#03121a;background:linear-gradient(135deg,#00d4ff,#7c5cff)}
button:hover{filter:brightness(1.07)}
.err{color:#ff6b6b;font-size:13px;min-height:18px;margin-bottom:6px}
</style></head><body><form method="post" action="/login">
<h1>🎮 Bot Dashboard</h1><p class="sub">Керування музикою з браузера</p>
<input type="password" name="password" placeholder="Пароль" autofocus>
<div class="err">__ERR__</div><button>Увійти</button></form></body></html>"""

DASH_HTML = r"""<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot Dashboard</title><style>
:root{color-scheme:dark;--bg:#0b0e14;--card:#151b27;--card2:#1b2230;--line:#262e40;
--muted:#8b95a7;--txt:#e6e9ef;--accent:#00d4ff;--accent2:#7c5cff;--danger:#ff5d6c}
*{box-sizing:border-box}
body{margin:0;font-family:'Segoe UI',system-ui,-apple-system,sans-serif;color:var(--txt);
background:radial-gradient(1100px 520px at 80% -120px,#17223a 0,var(--bg) 60%);
min-height:100vh;padding:20px}
.wrap{max-width:920px;margin:0 auto}
.top{display:flex;align-items:center;gap:12px;margin-bottom:20px}
.dot{width:11px;height:11px;border-radius:50%;background:#444;box-shadow:0 0 0 4px rgba(0,0,0,.25);
transition:.3s}
.dot.on{background:#22c55e;box-shadow:0 0 14px #22c55e}
.brand{font-weight:800;font-size:19px;letter-spacing:.2px}
.meta{color:var(--muted);font-size:13px}
.logout{margin-left:auto;background:var(--danger);color:#1a0408;border:0;border-radius:10px;
padding:9px 14px;font-weight:800;cursor:pointer}
.logout:hover{filter:brightness(1.08)}
.card{background:linear-gradient(180deg,var(--card),#121826);border:1px solid var(--line);
border-radius:18px;padding:18px;margin:14px 0;box-shadow:0 24px 60px -34px #000}
.gname{font-weight:800;font-size:15px;color:#cdd5e3;margin-bottom:12px;display:flex;
align-items:center;gap:8px}
.gname .tag{font-size:11px;font-weight:700;color:var(--muted);background:#0c1320;
border:1px solid var(--line);padding:3px 8px;border-radius:999px}
.now{display:flex;gap:16px}
.art{width:120px;height:90px;border-radius:12px;object-fit:cover;background:#0c1118;
border:1px solid var(--line);flex:none}
.art.ph{display:flex;align-items:center;justify-content:center;font-size:34px;color:#2f3a52}
.np{flex:1;min-width:0}
.title{font-weight:800;font-size:17px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.badges{display:flex;gap:6px;flex-wrap:wrap;margin-top:7px}
.badge{font-size:11px;font-weight:700;padding:3px 9px;border-radius:999px;background:#0c1320;
border:1px solid var(--line);color:#9fb0c8}
.badge.act{color:#03121a;background:linear-gradient(135deg,var(--accent),var(--accent2));border:0}
.bar{height:8px;background:#0c1320;border-radius:6px;margin:12px 0 4px;cursor:pointer;
position:relative;overflow:hidden;border:1px solid var(--line)}
.fill{height:100%;width:0;background:linear-gradient(90deg,var(--accent),var(--accent2));
border-radius:6px;transition:width .25s linear}
.times{display:flex;justify-content:space-between;font-size:12px;color:var(--muted)}
.ctrl{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:14px}
.btn{background:var(--card2);color:var(--txt);border:1px solid var(--line);border-radius:11px;
min-width:42px;height:42px;padding:0 12px;font-size:17px;cursor:pointer;display:inline-flex;
align-items:center;justify-content:center;gap:6px;transition:.15s}
.btn:hover{background:#27324a;border-color:#33405c}
.btn.pp{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#03121a;border:0;
width:50px;height:50px;font-size:20px}
.btn.on{border-color:var(--accent);color:var(--accent);box-shadow:0 0 0 2px rgba(0,212,255,.15) inset}
.btn.danger:hover{background:#3a1820;border-color:var(--danger);color:var(--danger)}
.btn.sm{height:34px;min-width:34px;font-size:14px;padding:0 9px;border-radius:9px}
.vol{display:flex;align-items:center;gap:9px;margin-left:auto;color:var(--muted);font-size:13px}
input[type=range]{-webkit-appearance:none;appearance:none;height:6px;width:130px;border-radius:6px;
background:#0c1320;outline:none;border:1px solid var(--line)}
input[type=range]::-webkit-slider-thumb{-webkit-appearance:none;width:16px;height:16px;border-radius:50%;
background:var(--accent);cursor:pointer;box-shadow:0 0 8px rgba(0,212,255,.6)}
select{background:var(--card2);color:var(--txt);border:1px solid var(--line);border-radius:10px;
height:38px;padding:0 10px;font-size:13px;cursor:pointer}
.addrow{display:flex;gap:8px;margin-top:12px}
.addrow input.q{flex:1;min-width:0;padding:11px 13px;border-radius:11px;border:1px solid var(--line);
background:#0b0e14;color:var(--txt);font-size:14px;outline:none}
.addrow input.q:focus{border-color:var(--accent)}
.addrow .btn{background:linear-gradient(135deg,var(--accent),var(--accent2));color:#03121a;border:0;font-weight:800;font-size:14px}
.qhead{display:flex;align-items:center;gap:8px;margin:16px 0 8px;color:#cdd5e3;font-weight:800;font-size:14px}
.qhead .qn{color:var(--muted);font-weight:600}
.qhead .qbtns{margin-left:auto;display:flex;gap:6px}
.qlist{display:flex;flex-direction:column;gap:6px;max-height:340px;overflow:auto}
.qrow{display:flex;align-items:center;gap:10px;background:#0e1422;border:1px solid var(--line);
border-radius:11px;padding:8px 10px}
.qrow .idx{color:var(--muted);font-size:12px;width:22px;text-align:right;flex:none;font-variant-numeric:tabular-nums}
.qrow .qt{flex:1;min-width:0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;font-size:14px}
.qrow .qd{color:var(--muted);font-size:12px;flex:none}
.qrow .qa{display:flex;gap:4px;flex:none}
.empty{color:var(--muted);text-align:center;padding:26px;font-size:14px}
.foot{text-align:center;color:#56607a;font-size:12px;margin:22px 0 8px}
.libtarget{margin-bottom:12px;color:var(--muted);font-size:13px;display:flex;align-items:center;gap:8px;flex-wrap:wrap}
.libgrid{display:grid;grid-template-columns:1fr 1fr;gap:20px}
.favuser{margin-bottom:12px}
.favhead{display:flex;align-items:center;gap:8px;font-weight:700;font-size:13px;color:#cdd5e3;margin:8px 0 5px}
.favhead .btn{margin-left:auto}
.btn:disabled{opacity:.4;cursor:not-allowed}
@media(max-width:560px){.now{flex-direction:column}.art{width:100%;height:150px}.vol{margin-left:0}
 .libgrid{grid-template-columns:1fr}}
</style></head><body>
<div class="wrap">
 <div class="top"><span id="dot" class="dot"></span>
  <div><div class="brand" id="brand">Bot Dashboard</div><div class="meta" id="meta">під'єднання…</div></div>
  <button class="logout" onclick="logout()">Вийти</button></div>
 <div id="players"></div>
 <div id="library"></div>
 <div class="foot">оновлюється автоматично • керування у процесі бота</div>
</div>
<script>
let FILTERS=[];           // список назв фільтрів
let last={};              // gid -> {pos,dur,playing,paused,ts}
function esc(t){let d=document.createElement('div');d.textContent=t==null?'':t;return d.innerHTML;}
function fmt(s){s=Math.max(0,s|0);let h=(s/3600)|0,m=((s%3600)/60)|0,ss=s%60;
 let mm=(h?String(m).padStart(2,'0'):m)+':'+String(ss).padStart(2,'0');return h?h+':'+mm:mm;}
async function api(path,opts){const r=await fetch(path,opts);if(r.status===401){location.reload();}return r;}
async function ctl(action,gid,value){await api('/api/control',{method:'POST',
 headers:{'Content-Type':'application/json'},body:JSON.stringify({action,guild_id:gid,value})});refresh();}
async function logout(){await api('/logout',{method:'POST'});location.reload();}
function seekClick(ev,gid,dur){if(!dur)return;const r=ev.currentTarget.getBoundingClientRect();
 const f=Math.min(1,Math.max(0,(ev.clientX-r.left)/r.width));ctl('seek',gid,Math.floor(f*dur));}
function addFrom(gid){const el=document.getElementById('q_'+gid);const v=el.value.trim();
 if(v){ctl('play',gid,v);el.value='';}}

function card(p){
 const loops={off:'🔁',song:'🔂',queue:'🔁'};
 const filtOpts=FILTERS.map(f=>`<option value="${f}"${f===p.filter?' selected':''}>${f}</option>`).join('');
 let q='';
 if(p.queue.length){
  q=p.queue.map((t,i)=>`<div class="qrow"><span class="idx">${i+1}</span>
    <span class="qt">${esc(t.title)}</span>
    <span class="qd">${t.duration?fmt(t.duration):''}</span>
    <span class="qa">
     <button class="btn sm" title="Грати зараз" onclick="ctl('jump','${p.guild_id}',${i})">▶</button>
     <button class="btn sm" title="Вгору" onclick="ctl('move_up','${p.guild_id}',${i})">↑</button>
     <button class="btn sm" title="Вниз" onclick="ctl('move_down','${p.guild_id}',${i})">↓</button>
     <button class="btn sm danger" title="Видалити" onclick="ctl('remove','${p.guild_id}',${i})">✕</button>
    </span></div>`).join('');
  if(p.queue_len>p.queue.length)q+=`<div class="empty">…ще ${p.queue_len-p.queue.length} треків</div>`;
 }else{q='<div class="empty">Черга порожня</div>';}

 const art=p.thumbnail?`<img class="art" src="${p.thumbnail}" onerror="this.classList.add('ph');this.removeAttribute('src');this.textContent='🎵'">`
   :`<div class="art ph">🎵</div>`;
 const title=p.current?esc(p.current):'<span class="meta">нічого не грає</span>';
 return `<div class="card">
  <div class="gname">🎧 ${esc(p.guild)} <span class="tag">${p.queue_len} у черзі</span></div>
  <div class="now">${art}
   <div class="np">
    <div class="title">${title}</div>
    <div class="badges">
     ${p.filter&&p.filter!=='off'?`<span class="badge act">🎚️ ${p.filter}</span>`:''}
     ${p.loop!=='off'?`<span class="badge act">${loops[p.loop]} ${p.loop==='song'?'трек':'черга'}</span>`:''}
     ${p.autoplay?'<span class="badge act">📻 autoplay</span>':''}
     <span class="badge">🔊 ${p.volume}%</span>
    </div>
    <div class="bar" onclick="seekClick(event,'${p.guild_id}',${p.duration})"><div class="fill" id="fill_${p.guild_id}"></div></div>
    <div class="times"><span id="pos_${p.guild_id}">${fmt(p.position)}</span><span>${p.duration?fmt(p.duration):'—'}</span></div>
   </div></div>

  <div class="ctrl">
   <button class="btn pp" onclick="ctl('${p.paused?'resume':'pause'}','${p.guild_id}')">${p.paused?'▶':'⏸'}</button>
   <button class="btn" title="Скіп" onclick="ctl('skip','${p.guild_id}')">⏭</button>
   <button class="btn danger" title="Стоп" onclick="ctl('stop','${p.guild_id}')">⏹</button>
   <button class="btn ${p.loop!=='off'?'on':''}" title="Повтор" onclick="ctl('loop','${p.guild_id}')">${loops[p.loop]}</button>
   <button class="btn" title="Перемішати" onclick="ctl('shuffle','${p.guild_id}')">🔀</button>
   <button class="btn ${p.autoplay?'on':''}" title="Автоплей" onclick="ctl('autoplay','${p.guild_id}')">📻</button>
   <select title="Аудіофільтр" onchange="ctl('filter','${p.guild_id}',this.value)">${filtOpts}</select>
   <div class="vol">🔊<input type="range" min="0" max="100" value="${p.volume}"
     onchange="ctl('volume','${p.guild_id}',this.value)"></div>
  </div>

  <div class="addrow">
   <input class="q" id="q_${p.guild_id}" placeholder="Назва або URL — додати в чергу…"
     onkeydown="if(event.key==='Enter')addFrom('${p.guild_id}')">
   <button class="btn" onclick="addFrom('${p.guild_id}')">➕ Додати</button>
  </div>

  <div class="qhead">📋 Черга <span class="qn">(${p.queue_len})</span>
   <span class="qbtns">
    <button class="btn sm" onclick="ctl('shuffle','${p.guild_id}')">🔀 Перемішати</button>
    <button class="btn sm danger" onclick="ctl('clear','${p.guild_id}')">🧹 Очистити</button>
   </span></div>
  <div class="qlist">${q}</div>
 </div>`;
}

// --- бібліотека: плейлисти та обране ---
function target(){const el=document.getElementById('target');return el?el.value:null;}
async function lib(payload){await api('/api/control',{method:'POST',
 headers:{'Content-Type':'application/json'},body:JSON.stringify(payload)});refresh();}
function plLoad(uid,btn){const g=target();if(!g)return;
 lib({action:'pl_load',guild_id:g,user_id:uid,name:decodeURIComponent(btn.dataset.name)});}
function plDelete(uid,btn){const name=decodeURIComponent(btn.dataset.name);
 if(!confirm('Видалити плейлист «'+name+'»?'))return;lib({action:'pl_delete',user_id:uid,name});}
function favPlay(uid,idx){const g=target();if(!g)return;lib({action:'fav_play',guild_id:g,user_id:uid,value:idx});}
function favRemove(uid,idx){lib({action:'fav_remove',user_id:uid,value:idx});}

function libCard(s){
 const players=s.players||[],pls=s.playlists||[],favs=s.favorites||[];
 const noTarget=players.length===0;
 const head=noTarget
  ? `<div class="meta" style="margin-bottom:12px">⚠️ Бот не в голосовому каналі — завантаження в чергу недоступне (приєднай бота та постав трек).</div>`
  : `<div class="libtarget">Завантажувати в чергу: <select id="target">${players.map(p=>`<option value="${p.guild_id}">${esc(p.guild)}</option>`).join('')}</select></div>`;
 const dis=noTarget?'disabled':'';
 const plRows=pls.length?pls.map(p=>`<div class="qrow">
   <span class="qt">📂 ${esc(p.name)} <span class="qd">· ${p.count} тр. · ${esc(p.user)}</span></span>
   <span class="qa">
    <button class="btn sm" ${dis} title="У чергу" data-name="${encodeURIComponent(p.name)}" onclick="plLoad('${p.user_id}',this)">▶</button>
    <button class="btn sm danger" title="Видалити" data-name="${encodeURIComponent(p.name)}" onclick="plDelete('${p.user_id}',this)">🗑</button>
   </span></div>`).join(''):'<div class="empty">Немає збережених плейлистів</div>';
 const favBlocks=favs.length?favs.map(f=>`<div class="favuser">
   <div class="favhead">⭐ ${esc(f.user)} <span class="qd">(${f.count})</span>
    <button class="btn sm" ${dis} onclick="favPlay('${f.user_id}','')">▶ Грати все</button></div>
   ${f.tracks.map((t,i)=>`<div class="qrow"><span class="idx">${i+1}</span>
     <span class="qt">${esc(t.title)}</span>
     <span class="qa">
      <button class="btn sm" ${dis} title="У чергу" onclick="favPlay('${f.user_id}',${i})">▶</button>
      <button class="btn sm danger" title="Прибрати" onclick="favRemove('${f.user_id}',${i})">🗑</button>
     </span></div>`).join('')}</div>`).join(''):'<div class="empty">Ні в кого немає обраного</div>';
 return `<div class="card"><div class="gname">🗂️ Бібліотека</div>${head}
  <div class="libgrid">
   <div><div class="qhead">📂 Плейлисти <span class="qn">(${pls.length})</span></div><div class="qlist">${plRows}</div></div>
   <div><div class="qhead">⭐ Обране <span class="qn">(${favs.length})</span></div><div class="qlist">${favBlocks}</div></div>
  </div></div>`;
}

async function refresh(){
 let r=await api('/api/status');if(!r||!r.ok)return;let s=await r.json();
 FILTERS=s.filters||[];
 document.getElementById('dot').className='dot'+(s.online?' on':'');
 document.getElementById('brand').textContent=s.user||'Bot Dashboard';
 document.getElementById('meta').textContent=(s.online?'онлайн':'офлайн')+' • '+s.guild_count+' серв.';
 const box=document.getElementById('players');
 if(!s.players.length){box.innerHTML='<div class="card empty">Бот зараз не грає на жодному сервері.<br>Приєднай його до голосового каналу та постав трек.</div>';last={};}
 else{
  box.innerHTML=s.players.map(card).join('');
  last={};
  for(const p of s.players)last[p.guild_id]={pos:p.position,dur:p.duration,playing:p.playing,paused:p.paused,ts:Date.now()};
 }
 // бібліотека — рендеримо завжди; зберігаємо вибір цільового сервера
 const savedTarget=(document.getElementById('target')||{}).value;
 document.getElementById('library').innerHTML=libCard(s);
 const tsel=document.getElementById('target');
 if(tsel&&savedTarget&&[...tsel.options].some(o=>o.value===savedTarget))tsel.value=savedTarget;
}
// плавний локальний тік прогресу між опитуваннями
function tick(){
 for(const gid in last){const st=last[gid];if(!st.dur)continue;
  let pos=st.pos;if(st.playing&&!st.paused)pos+=Math.floor((Date.now()-st.ts)/1000);
  pos=Math.min(pos,st.dur);
  const fill=document.getElementById('fill_'+gid),pe=document.getElementById('pos_'+gid);
  if(fill)fill.style.width=(100*pos/st.dur)+'%';
  if(pe)pe.textContent=fmt(pos);}
}
refresh();setInterval(refresh,2500);setInterval(tick,1000);
</script></body></html>"""


class DashboardCog(commands.Cog, name="Дашборд"):
    def __init__(self, bot):
        self.bot = bot
        self.sessions: set[str] = set()
        self._runner = None
        self._site = None

    async def cog_load(self):
        if not config.DASHBOARD_PASSWORD:
            log.info("Дашборд вимкнено (не задано DASHBOARD_PASSWORD).")
            return
        app = web.Application()
        app.router.add_get("/", self.index)
        app.router.add_post("/login", self.login)
        app.router.add_post("/logout", self.logout)
        app.router.add_get("/api/status", self.api_status)
        app.router.add_post("/api/control", self.api_control)
        self._runner = web.AppRunner(app)
        await self._runner.setup()
        self._site = web.TCPSite(self._runner, config.DASHBOARD_HOST, config.DASHBOARD_PORT)
        try:
            await self._site.start()
        except OSError as e:
            # Порт зайнятий (інший інстанс/сервіс) — не валимо бота, лише вимикаємо дашборд.
            log.warning(
                "Дашборд не запущено: порт %s:%d зайнятий (%s). Бот працює без дашборда.",
                config.DASHBOARD_HOST, config.DASHBOARD_PORT, e,
            )
            await self._runner.cleanup()
            self._runner = self._site = None
            return
        log.info("Дашборд: http://%s:%d", config.DASHBOARD_HOST, config.DASHBOARD_PORT)

    def cog_unload(self):
        if self._runner:
            self.bot.loop.create_task(self._runner.cleanup())

    # ---- auth ----

    def _authed(self, request) -> bool:
        return request.cookies.get(COOKIE) in self.sessions

    async def index(self, request):
        if self._authed(request):
            return web.Response(text=DASH_HTML, content_type="text/html")
        return web.Response(text=LOGIN_HTML.replace("__ERR__", ""), content_type="text/html")

    async def login(self, request):
        data = await request.post()
        password = data.get("password", "")
        if hmac.compare_digest(password, config.DASHBOARD_PASSWORD):
            token = secrets.token_urlsafe(24)
            self.sessions.add(token)
            resp = web.HTTPFound("/")
            resp.set_cookie(COOKIE, token, httponly=True, samesite="Lax")
            return resp
        return web.Response(
            text=LOGIN_HTML.replace("__ERR__", "Невірний пароль"),
            content_type="text/html",
            status=401,
        )

    async def logout(self, request):
        self.sessions.discard(request.cookies.get(COOKIE))
        resp = web.json_response({"ok": True})
        resp.del_cookie(COOKIE)
        return resp

    # ---- api ----

    def _uname(self, uid) -> str:
        try:
            u = self.bot.get_user(int(uid))
        except (TypeError, ValueError):
            u = None
        return u.display_name if u else f"ID {uid}"

    def _status(self) -> dict:
        music = self.bot.get_cog("Музика")
        players = []
        if music:
            for gid, p in music.players.items():
                g = self.bot.get_guild(gid)
                vc = g.voice_client if g else None
                cur = p.current
                thumb = None
                if cur:
                    vid = _youtube_id(cur.get("url") or "")
                    if vid:
                        thumb = f"https://i.ytimg.com/vi/{vid}/mqdefault.jpg"
                active_filter = next(
                    (k for k, v in AUDIO_FILTERS.items() if v == p.audio_filter), "off"
                )
                loop_mode = "song" if p.loop_song else "queue" if p.loop_queue else "off"
                players.append(
                    {
                        "guild_id": str(gid),
                        "guild": g.name if g else str(gid),
                        "current": cur["title"] if cur else None,
                        "thumbnail": thumb,
                        "position": p.position() if cur else 0,
                        "duration": int((cur or {}).get("duration") or 0),
                        "paused": bool(vc and vc.is_paused()),
                        "playing": bool(vc and vc.is_playing()),
                        "volume": int(p.volume * 100),
                        "loop": loop_mode,
                        "autoplay": bool(settings.get(gid, "autoplay")),
                        "filter": active_filter,
                        "queue": [
                            {"title": t["title"], "duration": int(t.get("duration") or 0)}
                            for t in p.queue[:50]
                        ],
                        "queue_len": len(p.queue),
                    }
                )
        playlists = []
        favorites = []
        if music:
            for uid, pls in getattr(music.playlists, "data", {}).items():
                uname = self._uname(uid)
                for name, tracks in pls.items():
                    playlists.append(
                        {"user_id": str(uid), "user": uname, "name": name, "count": len(tracks)}
                    )
            for uid, items in getattr(music.favorites, "data", {}).items():
                if not items:
                    continue
                favorites.append(
                    {
                        "user_id": str(uid),
                        "user": self._uname(uid),
                        "count": len(items),
                        "tracks": [{"title": t.get("title", "?")} for t in items[:50]],
                    }
                )
        return {
            "online": self.bot.is_ready(),
            "user": str(self.bot.user) if self.bot.user else None,
            "guild_count": len(self.bot.guilds),
            "filters": list(AUDIO_FILTERS.keys()),
            "players": players,
            "playlists": playlists,
            "favorites": favorites,
        }

    async def api_status(self, request):
        if not self._authed(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        return web.json_response(self._status())

    async def api_control(self, request):
        if not self._authed(request):
            return web.json_response({"error": "unauthorized"}, status=401)
        body = await request.json()
        action = body.get("action")
        music = self.bot.get_cog("Музика")
        if music is None:
            return web.json_response({"error": "музичний cog недоступний"}, status=400)

        # --- бібліотека: керування без активного плеєра ---
        if action == "pl_delete":
            ok = music.playlists.delete(str(body.get("user_id")), str(body.get("name", "")))
            return web.json_response({"ok": ok}, status=200 if ok else 404)
        if action == "fav_remove":
            try:
                i = int(body.get("value"))
            except (TypeError, ValueError):
                return web.json_response({"error": "bad index"}, status=400)
            removed = music.favorites.remove(str(body.get("user_id")), i + 1)  # store 1-based
            if not removed:
                return web.json_response({"error": "bad index"}, status=400)
            return web.json_response({"ok": True})

        try:
            gid = int(body.get("guild_id"))
        except (TypeError, ValueError):
            return web.json_response({"error": "bad guild_id"}, status=400)

        guild = self.bot.get_guild(gid)
        vc = guild.voice_client if guild else None
        player = music.players.get(gid)
        if player is None:
            return web.json_response({"error": "немає активного плеєра"}, status=400)

        # дії транспорту/завантаження потребують голосового підключення
        if action in ("pause", "resume", "skip", "stop", "seek", "jump",
                      "pl_load", "fav_play") and not vc:
            return web.json_response({"error": "бот не в голосовому каналі"}, status=400)

        q = player.queue

        def qidx():
            try:
                return int(body.get("value"))
            except (TypeError, ValueError):
                return None

        if action == "pause":
            if vc.is_playing():
                vc.pause()
                player.mark_pause()
        elif action == "resume":
            if vc.is_paused():
                vc.resume()
                player.mark_resume()
        elif action == "skip":
            vc.stop()
        elif action == "stop":
            q.clear()
            player.loop_song = player.loop_queue = False
            vc.stop()
        elif action == "volume":
            try:
                v = max(0, min(100, int(body.get("value"))))
            except (TypeError, ValueError):
                return web.json_response({"error": "bad value"}, status=400)
            player.volume = v / 100
            if vc and vc.source:
                vc.source.volume = player.volume
        elif action == "play":
            query = str(body.get("value", "")).strip()
            if not query:
                return web.json_response({"error": "empty query"}, status=400)
            url = query if query.startswith("http") else f"ytsearch1:{query}"
            q.append({"url": url, "title": query, "duration": 0})
            if vc and not vc.is_playing() and not player.is_loading:
                player.next_event.set()
        elif action == "remove":
            i = qidx()
            if i is None or not (0 <= i < len(q)):
                return web.json_response({"error": "bad index"}, status=400)
            q.pop(i)
        elif action in ("move_up", "move_down"):
            i = qidx()
            if i is None or not (0 <= i < len(q)):
                return web.json_response({"error": "bad index"}, status=400)
            j = i - 1 if action == "move_up" else i + 1
            if 0 <= j < len(q):
                q[i], q[j] = q[j], q[i]
        elif action == "jump":
            i = qidx()
            if i is None or not (0 <= i < len(q)):
                return web.json_response({"error": "bad index"}, status=400)
            track = q.pop(i)
            q.insert(0, track)
            vc.stop()  # пропустити поточний — player_loop підхопить queue[0]
        elif action == "clear":
            q.clear()
        elif action == "shuffle":
            if len(q) > 1:
                random.shuffle(q)
        elif action == "loop":
            mode = str(body.get("value", "")).strip()
            if mode not in ("off", "song", "queue"):
                # без значення — циклічно off -> song -> queue
                mode = "song" if not (player.loop_song or player.loop_queue) else (
                    "queue" if player.loop_song else "off"
                )
            player.loop_song = mode == "song"
            player.loop_queue = mode == "queue"
        elif action == "autoplay":
            val = body.get("value")
            cur = bool(settings.get(gid, "autoplay"))
            new = (not cur) if val is None else bool(val)
            settings.set(gid, "autoplay", new)
        elif action == "filter":
            name = str(body.get("value", "")).strip().lower()
            if name not in AUDIO_FILTERS:
                return web.json_response({"error": "bad filter"}, status=400)
            player.audio_filter = AUDIO_FILTERS[name]
            if player.current and vc and (vc.is_playing() or vc.is_paused()):
                player.restart_current()
        elif action == "seek":
            try:
                seconds = max(0, int(body.get("value")))
            except (TypeError, ValueError):
                return web.json_response({"error": "bad value"}, status=400)
            player.restart_current(seek=seconds)
        elif action == "pl_load":
            tracks = music.playlists.get(str(body.get("user_id")), str(body.get("name", "")))
            if not tracks:
                return web.json_response({"error": "плейлист не знайдено"}, status=404)
            for t in tracks:
                q.append({"url": t["url"], "title": t.get("title", "?"), "duration": 0})
            if not vc.is_playing() and not player.is_loading:
                player.next_event.set()
        elif action == "fav_play":
            items = music.favorites.get(str(body.get("user_id")))
            if not items:
                return web.json_response({"error": "обране порожнє"}, status=400)
            v = body.get("value")
            if v in (None, ""):
                chosen = items
            else:
                try:
                    i = int(v)
                except (TypeError, ValueError):
                    return web.json_response({"error": "bad index"}, status=400)
                if not (0 <= i < len(items)):
                    return web.json_response({"error": "bad index"}, status=400)
                chosen = [items[i]]
            for t in chosen:
                q.append({"url": t["url"], "title": t.get("title", "?"), "duration": 0})
            if not vc.is_playing() and not player.is_loading:
                player.next_event.set()
        else:
            return web.json_response({"error": "unknown action"}, status=400)

        return web.json_response({"ok": True})


async def setup(bot):
    await bot.add_cog(DashboardCog(bot))
