#!/usr/bin/env python3
"""Small authenticated control/status server for the wardriving appliance."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import secrets
import socket
import subprocess
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

CONFIG = Path(os.environ.get("WARDRIVE_WEB_CONFIG", "/etc/wardrive/web.env"))
CAPTURE_DIR = Path(os.environ.get("WARDRIVE_CAPTURE_DIR", "/var/lib/wardrive/captures"))
ALLOWED_UNITS = (
    "wardrive-kismet.service", "gpsd.service", "gpsd.socket", "wardrive-web.service"
)
CSRF_TOKEN = secrets.token_urlsafe(24)


def read_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key] = value
    return values


def verify_password(password: str, encoded: str) -> bool:
    try:
        iterations_s, salt_hex, expected = encoded.split("$", 2)
        actual = hashlib.pbkdf2_hmac(
            "sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations_s)
        ).hex()
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


def unit_status(unit: str) -> dict[str, str | bool]:
    if unit not in ALLOWED_UNITS:
        raise ValueError("unit not allowed")
    result = subprocess.run(
        ["systemctl", "show", unit, "--property=ActiveState,SubState", "--value"],
        capture_output=True, text=True, timeout=3, check=False,
    )
    lines = result.stdout.strip().splitlines()
    active, sub = (lines + ["unknown", "unknown"])[:2]
    return {"active": active == "active", "state": active, "substate": sub}


def gps_status() -> dict[str, object]:
    try:
        with socket.create_connection(("127.0.0.1", 2947), timeout=1.5) as sock:
            sock.sendall(b'?WATCH={"enable":true,"json":true};\n')
            sock.settimeout(1.5)
            deadline = time.monotonic() + 1.5
            pending = b""
            while time.monotonic() < deadline:
                pending += sock.recv(4096)
                while b"\n" in pending:
                    line, pending = pending.split(b"\n", 1)
                    message = json.loads(line)
                    if message.get("class") == "TPV":
                        mode = int(message.get("mode", 0))
                        return {
                            "connected": True, "fix": mode >= 2, "mode": mode,
                            "lat": message.get("lat"), "lon": message.get("lon"),
                            "alt": message.get("alt"), "speed": message.get("speed"),
                            "satellites": message.get("satellites"),
                        }
        return {"connected": True, "fix": False, "mode": 0}
    except (OSError, ValueError, json.JSONDecodeError):
        return {"connected": False, "fix": False, "mode": 0}


def capture_status() -> dict[str, object]:
    CAPTURE_DIR.mkdir(parents=True, exist_ok=True)
    files = [p for p in CAPTURE_DIR.glob("*.wiglecsv") if p.is_file()]
    pending = [p for p in files if not Path(str(p) + ".uploaded").exists()]
    newest = max(files, key=lambda p: p.stat().st_mtime, default=None)
    return {
        "wigle_files": len(files), "pending_uploads": len(pending),
        "newest": newest.name if newest else None,
    }


def status_payload() -> dict[str, object]:
    services = {}
    for unit in ALLOWED_UNITS:
        try:
            services[unit] = unit_status(unit)
        except (OSError, subprocess.TimeoutExpired):
            services[unit] = {"active": False, "state": "unknown", "substate": "unknown"}
    upload = subprocess.run(
        ["systemctl", "show", "wardrive-upload.service",
         "--property=ActiveState,SubState,Result", "--value"],
        capture_output=True, text=True, timeout=3, check=False,
    ).stdout.strip().splitlines()
    services["wardrive-upload.service"] = {
        "active": (upload + [""])[0] == "active",
        "state": (upload + ["unknown"])[0],
        "substate": (upload + ["", "unknown"])[1],
        "result": (upload + ["", "", "unknown"])[2],
    }
    return {"services": services, "gps": gps_status(), "captures": capture_status()}


HTML = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>Wardrive Control</title>
<style>
:root{color-scheme:dark;--bg:#0b1020;--card:#151d32;--ok:#30d17d;--bad:#ff5f69;--muted:#91a0bc}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%;background:var(--bg)}
body{margin:0;min-width:280px;min-height:100dvh;font:16px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:#f4f7ff}
main{width:100%;max-width:920px;margin:auto;padding:max(24px,env(safe-area-inset-top)) max(24px,env(safe-area-inset-right)) max(24px,env(safe-area-inset-bottom)) max(24px,env(safe-area-inset-left))}
h1{margin:0 0 4px;font-size:clamp(1.75rem,7vw,2.35rem);line-height:1.15}h2{font-size:1.2rem;margin:0 0 14px}.sub{color:var(--muted);margin:0 0 24px}
.grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,250px),1fr));gap:14px}
.card{min-width:0;background:var(--card);border:1px solid #28334f;border-radius:14px;padding:18px}
.row{display:flex;justify-content:space-between;align-items:center;gap:16px;margin:11px 0}.row>span:last-child{text-align:right;overflow-wrap:anywhere}
.dot{width:11px;height:11px;border-radius:50%;background:var(--bad);display:inline-block}.dot.ok{background:var(--ok);box-shadow:0 0 9px var(--ok)}
.actions{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-top:16px}
button{min-height:48px;border:0;border-radius:10px;padding:12px 16px;font:inherit;font-weight:750;cursor:pointer;touch-action:manipulation;background:#5c7cfa;color:white;-webkit-tap-highlight-color:transparent}
button:active{transform:translateY(1px);filter:brightness(.9)}button:focus-visible{outline:3px solid #fff;outline-offset:2px}button:disabled{cursor:wait;opacity:.6}
button.stop{background:#d9485f}button.upload{width:100%;margin-top:16px;background:#26a269}small,.muted{color:var(--muted);overflow-wrap:anywhere}#message{min-height:24px;margin-top:16px;color:var(--muted)}
@media(max-width:600px){
 main{padding:max(18px,env(safe-area-inset-top)) max(14px,env(safe-area-inset-right)) max(22px,env(safe-area-inset-bottom)) max(14px,env(safe-area-inset-left))}
 .sub{margin-bottom:18px}.grid{grid-template-columns:1fr;gap:12px}.card{padding:16px;border-radius:12px}
 .actions{grid-template-columns:1fr}button{width:100%;min-height:52px}.row{align-items:flex-start}
}
@media(prefers-reduced-motion:reduce){button:active{transform:none}}
</style></head><body><main><h1>Wardrive Control</h1><p class="sub">Raspberry Pi collection dashboard</p>
<div class="grid"><section class="card"><h2>Collection</h2><div id="services"></div>
<div class="actions"><button onclick="act('/api/kismet/start')">Start Kismet</button><button class="stop" onclick="act('/api/kismet/stop')">Stop Kismet</button></div></section>
<section class="card"><h2>GPS</h2><div id="gps">Loading…</div></section>
<section class="card"><h2>Captures</h2><div id="captures">Loading…</div>
<button class="upload" onclick="act('/api/upload')">Upload to WiGLE</button></section></div><div id="message" role="status" aria-live="polite"></div>
<script>
const csrf='__CSRF__';
const esc=s=>String(s??'—').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
async function refresh(){try{let r=await fetch('/api/status');let d=await r.json();
document.querySelector('#services').innerHTML=Object.entries(d.services).map(([n,v])=>`<div class=row><span>${esc(n.replace('.service',''))}</span><span><i class="dot ${v.active?'ok':''}"></i> ${esc(v.substate)}</span></div>`).join('');
let g=d.gps;document.querySelector('#gps').innerHTML=`<div class=row><span>GPSD</span><b>${g.connected?'Connected':'Offline'}</b></div><div class=row><span>Fix</span><b>${g.fix?'Yes ('+g.mode+'D)':'No'}</b></div><div><small>${g.fix?esc(g.lat)+', '+esc(g.lon):'Waiting for position'}</small></div>`;
let c=d.captures;document.querySelector('#captures').innerHTML=`<div class=row><span>WiGLE CSV files</span><b>${c.wigle_files}</b></div><div class=row><span>Pending upload</span><b>${c.pending_uploads}</b></div><small>Newest: ${esc(c.newest)}</small>`;
}catch(e){document.querySelector('#message').textContent='Status unavailable: '+e}}
async function act(path){let m=document.querySelector('#message'),buttons=document.querySelectorAll('button');buttons.forEach(b=>b.disabled=true);m.textContent='Working…';try{let r=await fetch(path,{method:'POST',headers:{'X-CSRF-Token':csrf}}),d=await r.json();m.textContent=d.message||d.error;if(r.ok)setTimeout(refresh,700)}catch(e){m.textContent='Request failed: '+e}finally{buttons.forEach(b=>b.disabled=false)}}
refresh();setInterval(refresh,5000);
</script></main></body></html>"""


class Handler(BaseHTTPRequestHandler):
    server_version = "WardriveWeb/1"

    def authenticated(self) -> bool:
        header = self.headers.get("Authorization", "")
        if not header.startswith("Basic "):
            return False
        try:
            userpass = base64.b64decode(header[6:], validate=True).decode()
            user, password = userpass.split(":", 1)
            return hmac.compare_digest(user, SETTINGS["WEB_USERNAME"]) and verify_password(
                password, SETTINGS["WEB_PASSWORD_HASH"]
            )
        except (ValueError, UnicodeDecodeError):
            return False

    def send_json(self, code: int, value: object) -> None:
        body = json.dumps(value).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def require_auth(self) -> bool:
        if self.authenticated():
            return True
        self.send_response(401)
        self.send_header("WWW-Authenticate", 'Basic realm="Wardrive Control"')
        self.send_header("Content-Length", "0")
        self.end_headers()
        return False

    def do_GET(self) -> None:
        if not self.require_auth():
            return
        path = urlparse(self.path).path
        if path == "/api/status":
            self.send_json(200, status_payload())
        elif path == "/":
            body = HTML.replace("__CSRF__", CSRF_TOKEN).encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        else:
            self.send_json(404, {"error": "not found"})

    def do_POST(self) -> None:
        if not self.require_auth():
            return
        if not hmac.compare_digest(self.headers.get("X-CSRF-Token", ""), CSRF_TOKEN):
            self.send_json(403, {"error": "invalid CSRF token"})
            return
        actions = {
            "/api/kismet/start": (["sudo", "/bin/systemctl", "start", "wardrive-kismet.service"], "Kismet started"),
            "/api/kismet/stop": (["sudo", "/bin/systemctl", "stop", "wardrive-kismet.service"], "Kismet stopped"),
            "/api/upload": (["sudo", "/bin/systemctl", "start", "wardrive-upload.service"], "WiGLE upload started"),
        }
        action = actions.get(urlparse(self.path).path)
        if not action:
            self.send_json(404, {"error": "not found"})
            return
        result = subprocess.run(action[0], capture_output=True, text=True, timeout=15, check=False)
        if result.returncode:
            self.send_json(500, {"error": result.stderr.strip() or "systemd action failed"})
        else:
            self.send_json(202, {"message": action[1]})

    def log_message(self, fmt: str, *args: object) -> None:
        print(f"{self.address_string()} - {fmt % args}", flush=True)


SETTINGS = read_env(CONFIG)
if __name__ == "__main__":
    bind = SETTINGS.get("WEB_BIND", "0.0.0.0")
    port = int(SETTINGS.get("WEB_PORT", "8080"))
    ThreadingHTTPServer((bind, port), Handler).serve_forever()
