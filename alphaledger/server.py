"""Zero-dependency local web UI (`alphaledger serve`)."""

from __future__ import annotations

import io
import json
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Optional

import pandas as pd

from . import audit, licensing, metrics as m, report

PAGE = """<!doctype html><html lang="en"><head><meta charset="utf-8">
<title>AlphaLedger</title><style>
:root{--bg:#0d1117;--panel:#111827;--line:#1f2937;--fg:#e5e7eb;--muted:#9ca3af;--green:#34d399}
body{margin:0;background:var(--bg);color:var(--fg);font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Inter,sans-serif}
.wrap{max-width:760px;margin:0 auto;padding:56px 22px}
.brand{color:var(--muted);font-size:12px;letter-spacing:.16em;text-transform:uppercase}
h1{font-size:30px;margin:10px 0 8px;letter-spacing:-.02em}
p.sub{color:var(--muted);margin:0 0 28px}
.drop{border:1.5px dashed var(--line);border-radius:14px;padding:38px;text-align:center;background:var(--panel);cursor:pointer}
.drop.on{border-color:var(--green)}
.row{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-top:16px}
input[type=file]{display:none}
input[type=text],input[type=number]{width:100%;background:var(--panel);border:1px solid var(--line);
color:var(--fg);border-radius:9px;padding:10px 12px;font-size:13px}
label{display:block;font-size:12px;color:var(--muted);margin-bottom:6px}
.checks{display:flex;gap:18px;margin-top:16px;font-size:13px;color:var(--muted)}
.checks label{display:flex;gap:7px;align-items:center;color:var(--fg);font-size:13px}
button{margin-top:22px;width:100%;background:var(--green);color:#062b1e;border:0;border-radius:10px;
padding:13px;font-size:15px;font-weight:600;cursor:pointer}
button:disabled{opacity:.5;cursor:default}
.msg{margin-top:14px;font-size:13px;color:var(--muted);white-space:pre-wrap}
.badge{display:inline-block;margin-top:10px;font-size:11px;letter-spacing:.08em;text-transform:uppercase;
border:1px solid var(--line);border-radius:999px;padding:3px 9px;color:var(--muted)}
</style></head><body><div class="wrap">
<div class="brand">AlphaLedger</div>
<h1>Audit a strategy in one click</h1>
<p class="sub">Drop a CSV with a date column and either returns or equity. Everything runs on this machine.</p>
<span class="badge" id="lic"></span>
<div class="drop" id="drop"><b>Drop CSV here</b><br><span style="color:#9ca3af">or click to choose a file — date + return / equity columns</span>
<div id="fname" style="margin-top:10px;color:#9ca3af;font-size:12px"></div></div>
<div class="row">
  <div><label>Strategy name</label><input type="text" id="name" placeholder="e.g. BTC momentum 4h"></div>
  <div><label>Benchmark CSV (optional)</label><input type="text" id="bench" placeholder="/path/to/benchmark.csv"></div>
</div>
<div class="checks">
  <label><input type="checkbox" id="wf"> Walk-forward audit (Pro)</label>
  <label><input type="checkbox" id="mc"> Monte Carlo (Pro)</label>
</div>
<button id="go" disabled>Build report</button>
<div class="msg" id="msg"></div>
<input type="file" id="file" accept=".csv,.tsv,.txt">
</div>
<script>
const drop=document.getElementById('drop'), file=document.getElementById('file'),
 fname=document.getElementById('fname'), go=document.getElementById('go'),
 msg=document.getElementById('msg'), nameEl=document.getElementById('name'),
 benchEl=document.getElementById('bench'), wfEl=document.getElementById('wf'), mcEl=document.getElementById('mc');
let text=null;
fetch('/api/license').then(r=>r.json()).then(d=>{document.getElementById('lic').textContent=d.describe});
drop.onclick=()=>file.click();
['dragover','dragenter'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.add('on')}));
['dragleave','drop'].forEach(e=>drop.addEventListener(e,ev=>{ev.preventDefault();drop.classList.remove('on')}));
drop.addEventListener('drop',ev=>{if(ev.dataTransfer.files[0])read(ev.dataTransfer.files[0])});
file.onchange=()=>{if(file.files[0])read(file.files[0])};
function read(f){const r=new FileReader();r.onload=()=>{text=r.result;fname.textContent=f.name+' · '+(text.length/1024).toFixed(1)+' KB';go.disabled=false;};r.readAsText(f);}
go.onclick=async()=>{go.disabled=true;msg.textContent='Running…';
 const body={csv:text,name:nameEl.value||'Strategy',benchmark_path:benchEl.value.trim(),
  walkforward:wfEl.checked,montecarlo:mcEl.checked};
 try{const res=await fetch('/api/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});
  const data=await res.json();
  if(!res.ok){msg.textContent=data.error||'failed';go.disabled=false;return;}
  const blob=new URL.createObjectURL(new Blob([data.html],{type:'text/html'}));
  window.open(blob,'_blank');msg.textContent='Report ready — opened in a new tab.';go.disabled=false;
 }catch(e){msg.textContent=String(e);go.disabled=false;}};
</script></body></html>"""


def _parse_csv_text(text: str) -> pd.Series:
    df = pd.read_csv(io.StringIO(text), sep=None, engine="python")
    from .data import _extract

    return _extract(df, None, None)


class Handler(BaseHTTPRequestHandler):
    server_version = "AlphaLedger/0.1"

    def log_message(self, fmt, *args):  # keep the console quiet
        return

    def _send(self, code: int, body: bytes, ctype: str = "text/html; charset=utf-8") -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        if self.path in {"/", "/index.html"}:
            self._send(200, PAGE.encode())
        elif self.path == "/api/license":
            lic = licensing.get_license()
            payload = json.dumps(
                {"describe": lic.describe(), "pro": lic.is_pro, "tier": lic.tier}
            ).encode()
            self._send(200, payload, "application/json")
        else:
            self._send(404, b"not found", "text/plain")

    def do_POST(self):  # noqa: N802
        if self.path != "/api/report":
            self._send(404, b"not found", "text/plain")
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length).decode())
            series = _parse_csv_text(payload["csv"])
            r = m.prepare_returns(series)
            name = payload.get("name") or "Strategy"

            bench = None
            if payload.get("benchmark_path"):
                bench = m.prepare_returns(
                    __import__("pandas").read_csv(payload["benchmark_path"]).iloc[:, -1]
                )
                bench = bench.reindex(r.index).dropna()
                r = r.reindex(bench.index)

            wf = mc = None
            if payload.get("walkforward"):
                licensing.require_pro("walk_forward")
                wf = audit.walk_forward(r, folds=4)
            if payload.get("montecarlo"):
                licensing.require_pro("monte_carlo")
                mc = audit.monte_carlo(r, runs=2000)

            html = report.build_report(r, name=name, benchmark=bench, walkforward=wf, montecarlo=mc)
            self._send(200, json.dumps({"html": html}).encode(), "application/json")
        except licensing.LicenseError as exc:
            self._send(403, json.dumps({"error": str(exc)}).encode(), "application/json")
        except Exception as exc:  # surface the message to the UI
            self._send(400, json.dumps({"error": f"{type(exc).__name__}: {exc}"}).encode(), "application/json")


def serve(port: int = 8765, open_browser: bool = True, host: str = "127.0.0.1") -> None:
    httpd = ThreadingHTTPServer((host, port), Handler)
    url = f"http://{host}:{port}/"
    print(f"AlphaLedger web UI -> {url}  (Ctrl+C to stop)")
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nstopped")
    finally:
        httpd.server_close()
