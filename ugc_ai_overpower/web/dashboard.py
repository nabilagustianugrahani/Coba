import os, json, time, logging
from datetime import datetime, timezone
from pathlib import Path
try:
    from fastapi import FastAPI, Request, HTTPException, Depends, Form
    from fastapi.responses import JSONResponse, HTMLResponse, RedirectResponse
    from fastapi.middleware.cors import CORSMiddleware
    import uvicorn, yaml
except ImportError:
    raise ImportError("pip install fastapi uvicorn pyyaml python-multipart")

from ugc_ai_overpower.auth import verify_user, create_token, verify_token
from ugc_ai_overpower.core.logging import setup_logging
from ugc_ai_overpower.core.content_bank import ContentBank
from ugc_ai_overpower.mcp_server.tools.influencer_tools import InfluencerManager
from ugc_ai_overpower.mcp_server.tools.ai_tools import AIRouter
from ugc_ai_overpower.core.orchestrator import Orchestrator
from ugc_ai_overpower.core.psychology import PsychologyEngine
from ugc_ai_overpower.monitoring.metrics import MetricsCollector, get_metrics_collector

logger = setup_logging("dashboard")

app = FastAPI(title="Skynet UGC Empire", version="2.0.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class AppState:
    def __init__(self):
        self.bank = ContentBank()
        self.influencer_mgr = InfluencerManager()
        self.ai = AIRouter(base_url=os.getenv("ROUTER_URL", "http://localhost:20128"), api_key=os.getenv("ROUTER_KEY", ""))
        self.psychology = PsychologyEngine()
        self.orchestrator = Orchestrator(self.bank, self.ai)
        self.metrics = get_metrics_collector()
        self.start_time = time.time()

state = AppState()

HTML_LOGIN = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Skynet Login</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh;display:flex;align-items:center;justify-content:center}
.card{background:#12121a;border:1px solid #1e1e2e;border-radius:16px;padding:2.5rem;width:400px;max-width:90vw}
.logo{font-size:1.5rem;font-weight:800;background:linear-gradient(135deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;-webkit-text-fill-color:transparent;text-align:center;margin-bottom:2rem}
.form-group{margin-bottom:1.25rem}
label{display:block;margin-bottom:.5rem;color:#888;font-size:.875rem}
input{width:100%;padding:.75rem 1rem;background:#0a0a0f;border:1px solid #1e1e2e;border-radius:8px;color:#e0e0e0;font-size:1rem;outline:none}
input:focus{border-color:#7b2ff7}
button{width:100%;padding:.75rem;background:linear-gradient(135deg,#00d4ff,#7b2ff7);border:none;border-radius:8px;color:#fff;font-size:1rem;font-weight:600;cursor:pointer;transition:opacity .2s}
button:hover{opacity:.9}
.error{background:#1a0d0d;border:1px solid #3a1a1a;border-radius:8px;padding:.75rem;color:#ff6b6b;margin-bottom:1rem;display:none}
</style></head><body>
<div class="card">
<div class="logo">Skynet</div>
<form id="loginForm" onsubmit="return login(event)">
<div class="error" id="errorMsg"></div>
<div class="form-group"><label>Username</label><input type="text" id="username" placeholder="admin" required></div>
<div class="form-group"><label>Password</label><input type="password" id="password" placeholder="admin123" required></div>
<button type="submit">Sign In</button>
</form></div>
<script>
async function login(e){e.preventDefault();const u=document.getElementById('username').value;const p=document.getElementById('password').value;try{const r=await fetch('/login',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({username:u,password:p})});const d=await r.json();if(r.ok){localStorage.setItem('token',d.token);window.location.href='/'}else{document.getElementById('errorMsg').textContent=d.detail;document.getElementById('errorMsg').style.display='block'}}catch(err){document.getElementById('errorMsg').textContent='Connection error';document.getElementById('errorMsg').style.display='block'}return false}
</script></body></html>'''

HTML_DASHBOARD = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Skynet Dashboard</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh}
.navbar{background:#12121a;border-bottom:1px solid #1e1e2e;padding:1rem 2rem;display:flex;align-items:center;gap:1rem}
.logo{font-size:1.25rem;font-weight:800;background:linear-gradient(135deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.nav-links{margin-left:auto;display:flex;gap:1rem}
.nav-links a{color:#888;text-decoration:none;padding:.5rem 1rem;border-radius:8px;transition:all .2s;font-size:.875rem}
.nav-links a:hover,.nav-links a.active{background:#1e1e2e;color:#fff}
.container{max-width:1200px;margin:0 auto;padding:2rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:2rem}
.stat-card{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:1.5rem}
.stat-value{font-size:2rem;font-weight:700;color:#fff}
.stat-label{font-size:.875rem;color:#888;margin-top:.25rem}
.section{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:1.5rem;margin-bottom:1rem}
.section h3{color:#fff;margin-bottom:1rem}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:.75rem .5rem;color:#888;font-size:.75rem;text-transform:uppercase;border-bottom:1px solid #1e1e2e}
td{padding:.75rem .5rem;border-bottom:1px solid #1e1e2e;font-size:.875rem}
.status-badge{display:inline-block;padding:.125rem .5rem;border-radius:999px;font-size:.75rem;font-weight:600}
.status-pending{background:#1a1a0d;color:#facc15;border:1px solid #3a3a1a}
.status-processing{background:#0d1a2a;color:#60a5fa;border:1px solid #1a2a3a}
.status-done{background:#0d1a0d;color:#4ade80;border:1px solid #1a3a1a}
.status-failed{background:#1a0d0d;color:#ff6b6b;border:1px solid #3a1a1a}
.loading{text-align:center;padding:3rem;color:#666}
.btn{display:inline-block;padding:.25rem .75rem;border-radius:6px;border:none;font-size:.75rem;font-weight:600;cursor:pointer;transition:all .2s}
.btn-post{background:#166534;color:#4ade80}
.btn-post:hover{background:#1a7a3a}
.btn-retry{background:#5b21b6;color:#c4b5fd}
.btn-retry:hover{background:#6d28d9}
.btn-delete{background:#7f1d1d;color:#fca5a5;margin-left:.25rem}
.btn-delete:hover{background:#991b1b}
.btn-action{background:#1e1e2e;color:#e0e0e0;padding:.5rem 1rem;margin-left:.5rem}
.btn-action:hover{background:#2a2a3e}
.btn:disabled{opacity:.4;cursor:not-allowed}
.footer{text-align:center;padding:2rem;color:#444;font-size:.75rem}
.toast{position:fixed;bottom:2rem;right:2rem;padding:.75rem 1.5rem;border-radius:8px;color:#fff;font-size:.875rem;z-index:999;animation:fadeIn .3s}
.toast-success{background:#166534}
.toast-error{background:#7f1d1d}
.toast-info{background:#1e3a5f}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
</style></head><body>
<div class="navbar"><div class="logo">Skynet</div><div class="badge">v2.0.0</div>
<div class="nav-links">
<a href="/" class="active">Dashboard</a>
<a href="/queue">Queue</a>
<a href="/campaigns">Campaigns</a>
<a href="/contents">Content</a>
<a href="/analytics">Analytics</a>
<a href="#" onclick="logout()" style="color:#ff6b6b">Logout</a>
</div></div>
<div class="container">
<div class="stats" id="stats">
<div class="stat-card"><div class="stat-value" id="campaigns">-</div><div class="stat-label">Campaigns</div></div>
<div class="stat-card"><div class="stat-value" id="contents">-</div><div class="stat-label">Content</div></div>
<div class="stat-card"><div class="stat-value" id="influencers">-</div><div class="stat-label">Influencers</div></div>
<div class="stat-card"><div class="stat-value" id="uptime">-</div><div class="stat-label">Uptime</div></div>
</div>
<div class="section"><h3>Recent Campaigns <button class="refresh-btn" onclick="loadCampaigns()">Refresh</button></h3>
<table><thead><tr><th>ID</th><th>Product</th><th>Status</th><th>Content</th><th>Created</th></tr></thead>
<tbody id="campaignTable"><tr><td colspan="5" class="loading">Loading...</td></tr></tbody></table></div>
<div class="charts" style="display:grid;grid-template-columns:1fr 1fr;gap:1rem;margin-bottom:1rem">
<div class="section"><h3>Daily Activity</h3><canvas id="barChart" height="200"></canvas></div>
<div class="section"><h3>Content Distribution</h3><canvas id="pieChart" height="200"></canvas></div>
</div>
<div class="section"><h3>Content Queue
<button class="refresh-btn" onclick="loadQueue()">Refresh</button>
<button class="btn btn-action" onclick="processAll()">Process All</button>
<button class="btn btn-action" onclick="retryFailed()">Retry Failed</button>
</h3>
<div id="queueStats" style="display:grid;grid-template-columns:repeat(4,1fr);gap:.5rem;margin-bottom:1rem"></div>
<table><thead><tr><th>ID</th><th>Content</th><th>Platform</th><th>Status</th><th>Scheduled</th><th>Post URL</th><th>Actions</th></tr></thead>
<tbody id="queueTable"><tr><td colspan="7" class="loading">Loading...</td></tr></tbody></table></div>
<div class="footer">Skynet UGC Empire v2.0.0</div></div>
<script>
const TOKEN=()=>localStorage.getItem('token');
async function api(path,opts){try{const r=await fetch(path,{headers:{'Authorization':'Bearer '+TOKEN(),...(opts?.headers||{})},...(opts||{})});if(r.status===401){localStorage.removeItem('token');window.location.href='/login';return null}return await r.json()}catch(e){return null}}
function toast(msg,type){const d=document.createElement('div');d.className='toast toast-'+type;d.textContent=msg;document.body.appendChild(d);setTimeout(()=>d.remove(),4000)}
function logout(){localStorage.removeItem('token');window.location.href='/login'}
async function loadStats(){const d=await api('/api/v1/analytics/dashboard');if(d){document.getElementById('campaigns').textContent=d.total_campaigns;document.getElementById('contents').textContent=d.total_content;document.getElementById('influencers').textContent=d.influencers;document.getElementById('uptime').textContent=d.uptime_hours+'h'}}
async function loadCampaigns(){const d=await api('/api/v1/campaigns');const t=document.getElementById('campaignTable');if(d&&d.data){t.innerHTML=d.data.map(c=>'<tr><td>#'+c.id+'</td><td>'+(c.product||'-')+'</td><td><span class="status-badge status-'+c.status+'">'+c.status+'</span></td><td>'+(c.content_count||0)+'</td><td>'+(c.created_at||'-')+'</td></tr>').join('')}else{t.innerHTML='<tr><td colspan="5" class="loading">No data</td></tr>'}}
async function loadCharts(){const d=await api('/api/v1/analytics/daily');const td=await api('/api/v1/analytics/summary');if(d&&d.data){const labels=Object.keys(d.data);const vals=labels.map(l=>{let s=0;for(let k in d.data[l])s+=d.data[l][k];return s});if(window.barChart){window.barChart.destroy()}window.barChart=new Chart(document.getElementById('barChart'),{type:'bar',data:{labels,datasets:[{label:'Events',data:vals,backgroundColor:'#7b2ff7'}]},options:{responsive:true,plugins:{legend:{labels:{color:'#e0e0e0'}}},scales:{x:{ticks:{color:'#888'}},y:{ticks:{color:'#888'}}}}})}if(td&&td.data){const{total_campaigns,total_contents}=td.data;if(window.pieChart){window.pieChart.destroy()}window.pieChart=new Chart(document.getElementById('pieChart'),{type:'pie',data:{labels:['Content','Campaigns'],datasets:[{data:[total_contents,total_campaigns],backgroundColor:['#00d4ff','#7b2ff7']}]},options:{responsive:true,plugins:{legend:{labels:{color:'#e0e0e0'}}}}})}}
async function loadQueue(){const d=await api('/api/v1/queue/status');if(!d)return;const st=d.stats||{};const qs=document.getElementById('queueStats');qs.innerHTML='<div class="stat-card"><div class="stat-value">'+(st.pending||0)+'</div><div class="stat-label">Pending</div></div><div class="stat-card"><div class="stat-value">'+(st.processing||0)+'</div><div class="stat-label">Processing</div></div><div class="stat-card"><div class="stat-value">'+(st.done||0)+'</div><div class="stat-label">Done</div></div><div class="stat-card"><div class="stat-value">'+(st.failed||0)+'</div><div class="stat-label">Failed</div></div>';const t=document.getElementById('queueTable');if(d.items&&d.items.length){t.innerHTML=d.items.map(i=>{const s=i.status||'pending';return '<tr><td>#'+i.id+'</td><td>'+(i.content_id||'-')+'</td><td>'+i.platform+'</td><td><span class="status-badge status-'+s+'">'+s+'</span></td><td>'+(i.scheduled_at||'-')+'</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis">'+(i.post_url||'-')+'</td><td>'+(s==='failed'?'<button class="btn btn-retry" onclick="retryItem('+i.id+')">Retry</button><button class="btn btn-delete" onclick="deleteItem('+i.id+')">Del</button>':s==='pending'?'<button class="btn btn-post" onclick="postItem('+i.id+')">Post</button><button class="btn btn-delete" onclick="deleteItem('+i.id+')">Del</button>':'')+'</td></tr>'}).join('')}else{t.innerHTML='<tr><td colspan="7" class="loading">No items</td></tr>'}}
async function postItem(id){toast('Posting #'+id+'...','info');const r=await api('/api/v1/queue/post/'+id,{method:'POST'});if(r&&r.status==='done'){toast('# '+id+' posted!','success')}else{toast('Failed: '+(r?.error||'unknown'),'error')}loadQueue()}
async function retryItem(id){toast('Retrying #'+id+'...','info');const r=await api('/api/v1/queue/retry/'+id,{method:'POST'});if(r&&r.status==='ok'){toast('# '+id+' reset to pending','success')}else{toast('Failed','error')}loadQueue()}
async function deleteItem(id){if(!confirm('Delete queue item #'+id+'?'))return;const r=await api('/api/v1/queue/delete/'+id,{method:'DELETE'});if(r&&r.status==='ok'){toast('# '+id+' deleted','success')}else{toast('Failed','error')}loadQueue()}
async function processAll(){if(!confirm('Process ALL pending items?'))return;toast('Processing...','info');const r=await api('/api/v1/queue/process',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(r&&r.data){toast('Done: '+r.data.success+' success, '+r.data.failed+' failed','success')}else{toast('Failed','error')}loadQueue()}
async function retryFailed(){if(!confirm('Reset ALL failed items to pending?'))return;const r=await api('/api/v1/queue/retry',{method:'POST'});if(r){toast(r.reset+' items reset','success')}else{toast('Failed','error')}loadQueue()}
if(!TOKEN()){window.location.href='/login'}else{loadStats();loadCampaigns();loadCharts();loadQueue();setInterval(function(){loadStats();loadCharts();loadQueue()},10000)}
</script></body></html>'''

HTML_QUEUE = '''<!DOCTYPE html>
<html><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Skynet Queue</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0a0a0f;color:#e0e0e0;min-height:100vh}
.navbar{background:#12121a;border-bottom:1px solid #1e1e2e;padding:1rem 2rem;display:flex;align-items:center;gap:1rem}
.logo{font-size:1.25rem;font-weight:800;background:linear-gradient(135deg,#00d4ff,#7b2ff7);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
.nav-links{margin-left:auto;display:flex;gap:1rem}
.nav-links a{color:#888;text-decoration:none;padding:.5rem 1rem;border-radius:8px;transition:all .2s;font-size:.875rem}
.nav-links a:hover,.nav-links a.active{background:#1e1e2e;color:#fff}
.container{max-width:1200px;margin:0 auto;padding:2rem}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:1rem;margin-bottom:2rem}
.stat-card{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:1.5rem}
.stat-value{font-size:2rem;font-weight:700;color:#fff}
.stat-label{font-size:.875rem;color:#888;margin-top:.25rem}
.section{background:#12121a;border:1px solid #1e1e2e;border-radius:12px;padding:1.5rem;margin-bottom:1rem}
.section h3{color:#fff;margin-bottom:1rem}
table{width:100%;border-collapse:collapse}
th{text-align:left;padding:.75rem .5rem;color:#888;font-size:.75rem;text-transform:uppercase;border-bottom:1px solid #1e1e2e}
td{padding:.75rem .5rem;border-bottom:1px solid #1e1e2e;font-size:.875rem}
.status-badge{display:inline-block;padding:.125rem .5rem;border-radius:999px;font-size:.75rem;font-weight:600}
.status-pending{background:#1a1a0d;color:#facc15;border:1px solid #3a3a1a}
.status-processing{background:#0d1a2a;color:#60a5fa;border:1px solid #1a2a3a}
.status-done{background:#0d1a0d;color:#4ade80;border:1px solid #1a3a1a}
.status-failed{background:#1a0d0d;color:#ff6b6b;border:1px solid #3a1a1a}
.btn{display:inline-block;padding:.25rem .75rem;border-radius:6px;border:none;font-size:.75rem;font-weight:600;cursor:pointer;transition:all .2s}
.btn-post{background:#166534;color:#4ade80}
.btn-post:hover{background:#1a7a3a}
.btn-retry{background:#5b21b6;color:#c4b5fd}
.btn-retry:hover{background:#6d28d9}
.btn-delete{background:#7f1d1d;color:#fca5a5;margin-left:.25rem}
.btn-delete:hover{background:#991b1b}
.btn-action{background:#1e1e2e;color:#e0e0e0;padding:.5rem 1rem;margin-left:.5rem}
.btn-action:hover{background:#2a2a3e}
.btn:disabled{opacity:.4;cursor:not-allowed}
.loading{text-align:center;padding:3rem;color:#666}
.footer{text-align:center;padding:2rem;color:#444;font-size:.75rem}
.toast{position:fixed;bottom:2rem;right:2rem;padding:.75rem 1.5rem;border-radius:8px;color:#fff;font-size:.875rem;z-index:999;animation:fadeIn .3s}
.toast-success{background:#166534}
.toast-error{background:#7f1d1d}
.toast-info{background:#1e3a5f}
@keyframes fadeIn{from{opacity:0;transform:translateY(10px)}to{opacity:1;transform:translateY(0)}}
.filter-bar{display:flex;gap:.5rem;margin-bottom:1rem;flex-wrap:wrap}
.filter-bar select,.filter-bar input{background:#0a0a0f;border:1px solid #1e1e2e;border-radius:8px;color:#e0e0e0;padding:.5rem .75rem;font-size:.875rem}
.filter-bar select:focus,.filter-bar input:focus{border-color:#7b2ff7;outline:none}
</style></head><body>
<div class="navbar"><div class="logo">Skynet</div>
<div class="nav-links">
<a href="/">Dashboard</a>
<a href="/queue" class="active">Queue</a>
<a href="/campaigns">Campaigns</a>
<a href="#" onclick="logout()" style="color:#ff6b6b">Logout</a>
</div></div>
<div class="container">
<div class="stats" id="queueStats"></div>
<div class="section">
<h3>Queue Manager
<button class="btn btn-action" onclick="loadQueue()">Refresh</button>
<button class="btn btn-action" onclick="processAll()">Process All Pending</button>
<button class="btn btn-action" onclick="processParallel()">Process Parallel (3x)</button>
<button class="btn btn-action" onclick="retryFailed()">Retry All Failed</button>
</h3>
<div class="filter-bar">
<select id="filterPlatform" onchange="loadQueue()"><option value="">All Platforms</option><option value="tiktok">TikTok</option><option value="instagram">Instagram</option><option value="youtube">YouTube</option></select>
<select id="filterStatus" onchange="loadQueue()"><option value="">All Status</option><option value="pending">Pending</option><option value="processing">Processing</option><option value="done">Done</option><option value="failed">Failed</option></select>
<input type="text" id="searchInput" placeholder="Search content..." style="flex:1;min-width:200px">
</div>
<table><thead><tr><th>ID</th><th>Content ID</th><th>Platform</th><th>Status</th><th>Retries</th><th>Error</th><th>Scheduled</th><th>Actions</th></tr></thead>
<tbody id="queueBody"><tr><td colspan="8" class="loading">Loading...</td></tr></tbody></table></div>
<div class="footer">Skynet UGC Empire v2.0.0</div></div>
<script>
const TOKEN=()=>localStorage.getItem('token');
async function api(path,opts){try{const r=await fetch(path,{headers:{'Authorization':'Bearer '+TOKEN(),...(opts?.headers||{})},...(opts||{})});if(r.status===401){localStorage.removeItem('token');window.location.href='/login';return null}return await r.json()}catch(e){return null}}
function toast(msg,type){const d=document.createElement('div');d.className='toast toast-'+type;d.textContent=msg;document.body.appendChild(d);setTimeout(()=>d.remove(),4000)}
function logout(){localStorage.removeItem('token');window.location.href='/login'}
async function loadQueue(){const d=await api('/api/v1/queue/status');if(!d)return;const st=d.stats||{};document.getElementById('queueStats').innerHTML='<div class="stat-card"><div class="stat-value">'+(st.total||0)+'</div><div class="stat-label">Total</div></div><div class="stat-card"><div class="stat-value">'+(st.pending||0)+'</div><div class="stat-label">Pending</div></div><div class="stat-card"><div class="stat-value">'+(st.done||0)+'</div><div class="stat-label">Done</div></div><div class="stat-card"><div class="stat-value">'+(st.failed||0)+'</div><div class="stat-label">Failed</div></div>';const plat=document.getElementById('filterPlatform').value;const stat=document.getElementById('filterStatus').value;let items=(d.items||[]).filter(i=>!plat||i.platform===plat).filter(i=>!stat||i.status===stat);const t=document.getElementById('queueBody');if(items.length){t.innerHTML=items.map(i=>{const s=i.status||'pending';return '<tr><td>#'+i.id+'</td><td>'+(i.content_id||'-')+'</td><td>'+i.platform+'</td><td><span class="status-badge status-'+s+'">'+s+'</span></td><td>'+(i.retry_count||0)+'</td><td style="max-width:200px;overflow:hidden;text-overflow:ellipsis;color:#ff6b6b">'+(i.error||'-')+'</td><td>'+(i.scheduled_at||'-')+'</td><td>'+(s==='failed'?'<button class="btn btn-retry" onclick="retryItem('+i.id+')">Retry</button>':s==='pending'?'<button class="btn btn-post" onclick="postItem('+i.id+')">Post</button>':'')+'<button class="btn btn-delete" onclick="deleteItem('+i.id+')">Del</button></td></tr>'}).join('')}else{t.innerHTML='<tr><td colspan="8" class="loading">No items</td></tr>'}}
async function postItem(id){toast('Posting #'+id+'...','info');const r=await api('/api/v1/queue/post/'+id,{method:'POST'});if(r&&r.status==='done'){toast('# '+id+' posted!','success')}else{toast('Failed: '+(r?.error||'unknown'),'error')}loadQueue()}
async function retryItem(id){await api('/api/v1/queue/retry/'+id,{method:'POST'});loadQueue()}
async function deleteItem(id){if(!confirm('Delete #'+id+'?'))return;await api('/api/v1/queue/delete/'+id,{method:'DELETE'});loadQueue()}
async function processAll(){if(!confirm('Process ALL pending?'))return;toast('Processing...','info');const r=await api('/api/v1/queue/process',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(r&&r.data){toast(r.data.success+' success, '+r.data.failed+' failed','success')}else{toast('Failed','error')}loadQueue()}
async function processParallel(){if(!confirm('Process pending in parallel (3 workers)?'))return;toast('Parallel processing...','info');const r=await api('/api/v1/queue/process-parallel',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});if(r&&r.data){toast(r.data.success+' success, '+r.data.failed+' failed','success')}else{toast('Failed','error')}loadQueue()}
async function retryFailed(){if(!confirm('Reset ALL failed to pending?'))return;const r=await api('/api/v1/queue/retry',{method:'POST'});if(r)toast(r.reset+' items reset','success');loadQueue()}
if(!TOKEN()){window.location.href='/login'}else{loadQueue();setInterval(loadQueue,15000)}
</script></body></html>'''

@app.get("/login")
async def login_page():
    return HTMLResponse(HTML_LOGIN)

@app.post("/login")
async def login(request: Request):
    body = await request.json()
    user = verify_user(body.get("username", ""), body.get("password", ""))
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token = create_token(body["username"], user["role"])
    logger.info("Login: %s (role=%s)", body["username"], user["role"])
    return {"token": token}

async def auth_required(request: Request):
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Unauthorized")
    payload = verify_token(auth[7:])
    if not payload:
        raise HTTPException(status_code=401, detail="Invalid token")
    request.state.user = payload
    return payload

@app.get("/", response_class=HTMLResponse)
async def dashboard_page(request: Request):
    return HTMLResponse(HTML_DASHBOARD)

@app.get("/campaigns", response_class=HTMLResponse)
async def campaigns_page(request: Request):
    return HTMLResponse(HTML_DASHBOARD.replace("/campaigns", "/campaigns").replace("active", "", 1))

@app.get("/contents", response_class=HTMLResponse)
async def contents_page(request: Request):
    return HTMLResponse(HTML_DASHBOARD.replace("/contents", "/contents"))

@app.get("/analytics", response_class=HTMLResponse)
async def analytics_page(request: Request):
    return HTMLResponse(HTML_DASHBOARD.replace("/analytics", "/analytics"))

@app.get("/health")
async def health():
    return {"status":"healthy","version":"2.0.0","uptime":int(time.time()-state.start_time),"timestamp":datetime.now(timezone.utc).isoformat()}

@app.get("/api/v1/campaigns")
async def list_campaigns(_=Depends(auth_required)):
    campaigns = []
    if hasattr(state.bank, "get_all_campaigns"):
        try: campaigns = state.bank.get_all_campaigns()
        except: pass
    return {"data": campaigns, "total": len(campaigns)}

@app.post("/api/v1/campaigns")
async def create_campaign(request: Request, _=Depends(auth_required)):
    body = await request.json()
    product = body.get("product")
    if not product:
        raise HTTPException(400, "product required")
    result = state.orchestrator.run_campaign(product)
    return {"data": result, "status": "created"}

@app.get("/api/v1/influencers")
async def list_influencers(_=Depends(auth_required)):
    return {"data": state.influencer_mgr.influencers, "total": len(state.influencer_mgr.influencers)}

@app.post("/api/v1/analyze")
async def analyze(request: Request, _=Depends(auth_required)):
    body = await request.json()
    if not body.get("product"):
        raise HTTPException(400, "product required")
    result = state.ai.analyze_product(body["product"])
    return {"data": result}

@app.get("/api/v1/analytics/dashboard")
async def analytics_dashboard(_=Depends(auth_required)):
    bank_stats = {}
    if hasattr(state.bank, "get_stats"):
        try: bank_stats = state.bank.get_stats()
        except: pass
    return {
        "total_campaigns": bank_stats.get("total_campaigns", 0),
        "total_content": bank_stats.get("total_contents", 0),
        "influencers": len(state.influencer_mgr.influencers),
        "psychology_frameworks": len(state.psychology.frameworks),
        "uptime_hours": round((time.time() - state.start_time)/3600, 1),
    }

@app.get("/api/v1/analytics/daily")
async def analytics_daily(_=Depends(auth_required)):
    return {"data": state.metrics.get_daily_stats()}

@app.get("/api/v1/analytics/top-products")
async def analytics_top_products(_=Depends(auth_required)):
    return {"data": state.metrics.get_top_products()}

@app.get("/api/v1/analytics/summary")
async def analytics_summary(_=Depends(auth_required)):
    return {"data": state.metrics.get_summary()}

@app.get("/api/v1/queue/status")
async def queue_status(_=Depends(auth_required)):
    from ugc_ai_overpower.browser.content_queue import ContentQueue
    q = ContentQueue()
    stats = q.get_stats()
    items = q.list_items(limit=20)
    return {"stats": stats, "items": items}

@app.post("/api/v1/queue/process")
async def process_queue(request: Request, _=Depends(auth_required)):
    body = await request.json()
    platform = body.get("platform")
    from ugc_ai_overpower.browser.queue_processor import QueueProcessor
    processor = QueueProcessor()
    result = processor.process_all(platform)
    return {"data": result}

@app.post("/api/v1/queue/post/{item_id}")
async def post_queue_item(item_id: int, _=Depends(auth_required)):
    from ugc_ai_overpower.browser.content_queue import ContentQueue
    from ugc_ai_overpower.browser.queue_processor import QueueProcessor
    q = ContentQueue()
    items = q.list_items(status="pending", limit=100)
    target = next((i for i in items if i["id"] == item_id), None)
    if not target:
        return {"status": "error", "error": "not found"}
    processor = QueueProcessor()
    result = processor.process_one(target["platform"])
    return result

@app.post("/api/v1/queue/retry/{item_id}")
async def retry_queue_item(item_id: int, _=Depends(auth_required)):
    from ugc_ai_overpower.browser.content_queue import ContentQueue
    q = ContentQueue()
    import sqlite3
    conn = sqlite3.connect(q._db_path)
    try:
        conn.execute("UPDATE content_queue SET status='pending', error=NULL, updated_at=CURRENT_TIMESTAMP WHERE id=?", (item_id,))
        conn.commit()
        return {"status": "ok", "id": item_id}
    finally:
        conn.close()

@app.delete("/api/v1/queue/delete/{item_id}")
async def delete_queue_item(item_id: int, _=Depends(auth_required)):
    from ugc_ai_overpower.browser.content_queue import ContentQueue
    q = ContentQueue()
    import sqlite3
    conn = sqlite3.connect(q._db_path)
    try:
        conn.execute("DELETE FROM content_queue WHERE id=?", (item_id,))
        conn.commit()
        return {"status": "ok", "id": item_id}
    finally:
        conn.close()

@app.post("/api/v1/queue/process-parallel")
async def process_queue_parallel(request: Request, _=Depends(auth_required)):
    from ugc_ai_overpower.browser.queue_processor import QueueProcessor
    processor = QueueProcessor()
    result = processor.process_parallel(max_workers=3)
    return {"data": result}

@app.post("/api/v1/queue/retry")
async def retry_all_failed(_=Depends(auth_required)):
    from ugc_ai_overpower.browser.queue_processor import QueueProcessor
    processor = QueueProcessor()
    reset = processor.retry_failed()
    return {"status": "ok", "reset": reset}

@app.get("/queue", response_class=HTMLResponse)
async def queue_page(request: Request):
    return HTMLResponse(HTML_QUEUE)

def serve():
    host = os.getenv("HOST", "0.0.0.0")
    port = int(os.getenv("PORT", "8111"))
    logger.info("Dashboard starting on %s:%s", host, port)
    uvicorn.run(app, host=host, port=port, log_level="info")
