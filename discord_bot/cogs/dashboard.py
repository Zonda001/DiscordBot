"""Веб-дашборд: керування ботом з браузера (aiohttp, у процесі бота).

Вмикається лише якщо задано DASHBOARD_PASSWORD. За замовчуванням слухає 127.0.0.1.
Авторизація — пароль + сесійна кука. Для доступу ззовні — через тунель/HTTPS.
"""
import hmac
import logging
import secrets

from aiohttp import web
from discord.ext import commands

from discord_bot import config

log = logging.getLogger("bot.dashboard")

COOKIE = "dash_session"

LOGIN_HTML = """<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot — вхід</title><style>
body{background:#0b0e14;color:#e6e9ef;font-family:Segoe UI,system-ui,sans-serif;
display:flex;height:100vh;margin:0;align-items:center;justify-content:center}
form{background:#161b27;padding:32px;border-radius:14px;width:300px;text-align:center}
h1{font-size:18px;margin:0 0 18px}input{width:100%;box-sizing:border-box;padding:10px;
border-radius:8px;border:1px solid #2a3142;background:#0b0e14;color:#e6e9ef;margin-bottom:12px}
button{width:100%;padding:10px;border:0;border-radius:8px;background:#00d4ff;color:#000;
font-weight:700;cursor:pointer}.err{color:#ef4444;font-size:13px;min-height:16px}
</style></head><body><form method="post" action="/login">
<h1>🎮 Bot Dashboard</h1>
<input type="password" name="password" placeholder="Пароль" autofocus>
<div class="err">__ERR__</div><button>Увійти</button></form></body></html>"""

DASH_HTML = """<!doctype html><html lang="uk"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Bot Dashboard</title><style>
body{background:#0b0e14;color:#e6e9ef;font-family:Segoe UI,system-ui,sans-serif;margin:0;padding:16px}
.top{display:flex;align-items:center;gap:10px;margin-bottom:14px}
.dot{font-size:20px}.muted{color:#8b95a7;font-size:13px}
.card{background:#161b27;border-radius:12px;padding:16px;margin:10px 0}
.title{font-weight:700;font-size:16px}.bar{height:6px;background:#2a3142;border-radius:4px;margin:8px 0}
.fill{height:6px;background:#00d4ff;border-radius:4px;width:0}
button{background:#222b3d;color:#e6e9ef;border:0;border-radius:8px;padding:8px 12px;
cursor:pointer;font-size:15px;margin-right:6px}button:hover{background:#2c3850}
.row{display:flex;align-items:center;gap:8px;flex-wrap:wrap;margin-top:8px}
input[type=range]{vertical-align:middle}
input.q{flex:1;min-width:160px;padding:8px;border-radius:8px;border:1px solid #2a3142;
background:#0b0e14;color:#e6e9ef}.logout{margin-left:auto;background:#ef4444;color:#000;font-weight:700}
ol{margin:6px 0 0 18px;color:#aeb6c4;font-size:13px}
</style></head><body>
<div class="top"><span id="dot" class="dot">●</span><b id="state">...</b>
<span id="meta" class="muted"></span>
<button class="logout" onclick="logout()">Вийти</button></div>
<div id="players"></div>
<script>
async function api(path,opts){const r=await fetch(path,opts);if(r.status===401){location.reload();}return r;}
function fmt(s){s=Math.max(0,s|0);let m=(s/60)|0,ss=s%60;return m+':'+String(ss).padStart(2,'0');}
async function ctl(action,gid,value){await api('/api/control',{method:'POST',
 headers:{'Content-Type':'application/json'},body:JSON.stringify({action,guild_id:gid,value})});refresh();}
function playFrom(gid){const el=document.getElementById('q_'+gid);if(el.value.trim())ctl('play',gid,el.value.trim());el.value='';}
async function logout(){await api('/logout',{method:'POST'});location.reload();}
async function refresh(){
 let r=await api('/api/status');if(!r||!r.ok)return;let s=await r.json();
 document.getElementById('dot').style.color=s.online?'#22c55e':'#ef4444';
 document.getElementById('state').textContent=s.online?'ОНЛАЙН':'ОФЛАЙН';
 document.getElementById('meta').textContent=(s.user||'')+' • '+s.guild_count+' серв.';
 let h='';
 if(!s.players.length){h='<div class="card muted">Бот зараз не грає на жодному сервері.</div>';}
 for(const p of s.players){
  let pct=p.duration?Math.min(100,100*p.position/p.duration):0;
  h+='<div class="card"><div class="title">'+esc(p.guild)+'</div>';
  h+='<div>'+(p.current?'▶ '+esc(p.current):'<span class="muted">—</span>')+'</div>';
  if(p.duration){h+='<div class="muted">'+fmt(p.position)+' / '+fmt(p.duration)+'</div>';}
  h+='<div class="bar"><div class="fill" style="width:'+pct+'%"></div></div>';
  h+='<div class="row">';
  h+='<button onclick="ctl(\\''+(p.paused?'resume':'pause')+'\\',\\''+p.guild_id+'\\')">'+(p.paused?'▶':'⏸')+'</button>';
  h+='<button onclick="ctl(\\'skip\\',\\''+p.guild_id+'\\')">⏭</button>';
  h+='<button onclick="ctl(\\'stop\\',\\''+p.guild_id+'\\')">⏹</button>';
  h+='<input type="range" min="0" max="100" value="'+p.volume+'" onchange="ctl(\\'volume\\',\\''+p.guild_id+'\\',this.value)"> '+p.volume+'%';
  h+='</div><div class="row"><input class="q" id="q_'+p.guild_id+'" placeholder="назва або URL..."><button onclick="playFrom(\\''+p.guild_id+'\\')">▶ Грати</button></div>';
  if(p.queue.length){h+='<ol>'+p.queue.map(t=>'<li>'+esc(t)+'</li>').join('')+(p.queue_len>p.queue.length?'<li>...ще '+(p.queue_len-p.queue.length)+'</li>':'')+'</ol>';}
  h+='</div>';
 }
 document.getElementById('players').innerHTML=h;
}
function esc(t){let d=document.createElement('div');d.textContent=t==null?'':t;return d.innerHTML;}
refresh();setInterval(refresh,2500);
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
        await self._site.start()
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

    def _status(self) -> dict:
        music = self.bot.get_cog("Музика")
        players = []
        if music:
            for gid, p in music.players.items():
                g = self.bot.get_guild(gid)
                vc = g.voice_client if g else None
                cur = p.current
                players.append(
                    {
                        "guild_id": str(gid),
                        "guild": g.name if g else str(gid),
                        "current": cur["title"] if cur else None,
                        "position": p.position() if cur else 0,
                        "duration": int((cur or {}).get("duration") or 0),
                        "paused": bool(vc and vc.is_paused()),
                        "volume": int(p.volume * 100),
                        "queue": [t["title"] for t in p.queue[:10]],
                        "queue_len": len(p.queue),
                    }
                )
        return {
            "online": self.bot.is_ready(),
            "user": str(self.bot.user) if self.bot.user else None,
            "guild_count": len(self.bot.guilds),
            "players": players,
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
        try:
            gid = int(body.get("guild_id"))
        except (TypeError, ValueError):
            return web.json_response({"error": "bad guild_id"}, status=400)

        guild = self.bot.get_guild(gid)
        vc = guild.voice_client if guild else None
        music = self.bot.get_cog("Музика")
        player = music.players.get(gid) if music else None
        if not vc or not player:
            return web.json_response({"error": "бот не в голосовому каналі"}, status=400)

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
            player.queue.clear()
            player.loop_song = player.loop_queue = False
            vc.stop()
        elif action == "volume":
            try:
                v = max(0, min(100, int(body.get("value"))))
            except (TypeError, ValueError):
                return web.json_response({"error": "bad value"}, status=400)
            player.volume = v / 100
            if vc.source:
                vc.source.volume = player.volume
        elif action == "play":
            query = str(body.get("value", "")).strip()
            if not query:
                return web.json_response({"error": "empty query"}, status=400)
            url = query if query.startswith("http") else f"ytsearch1:{query}"
            player.queue.append({"url": url, "title": query, "duration": 0})
            if not vc.is_playing() and not player.is_loading:
                player.next_event.set()
        else:
            return web.json_response({"error": "unknown action"}, status=400)

        return web.json_response({"ok": True})


async def setup(bot):
    await bot.add_cog(DashboardCog(bot))
