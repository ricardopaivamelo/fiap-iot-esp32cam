"""Tela de coleta com preview ao vivo do ESP32-CAM: http://localhost:8000.

O servidor é o único cliente do /capture da placa: o preview busca /frame, e /save grava
exatamente o último frame exibido (o que você vê é o que entra no dataset).
"""

import argparse
import json
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from collect import DEFAULT_HOST, fetch_frame, save_frame

SCENES = ("garrafa", "caderno", "caneca", "misto", "vazio")
STATE: dict = {"last_frame": None, "host": DEFAULT_HOST, "out_dir": Path("dataset")}
_lock = threading.Lock()


def dataset_stats(out_dir: Path) -> dict[str, int]:
    return {s: len(list((out_dir / s).glob(f"{s}_*.jpg"))) for s in SCENES}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *args) -> None:
        pass

    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, payload: dict) -> None:
        self._send(status, json.dumps(payload).encode(), "application/json")

    def do_GET(self) -> None:
        path = urlparse(self.path).path
        if path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/frame":
            with _lock:
                frame = fetch_frame(STATE["host"], timeout=3.0)
                if frame is not None:
                    STATE["last_frame"] = frame
            if frame is None:
                self._json(503, {"error": "placa não respondeu ao /capture"})
            else:
                self._send(200, frame, "image/jpeg")
        elif path == "/stats":
            self._json(200, dataset_stats(STATE["out_dir"]))
        else:
            self._json(404, {"error": "rota inexistente"})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path != "/save":
            self._json(404, {"error": "rota inexistente"})
            return
        scene = parse_qs(url.query).get("scene", [""])[0]
        if scene not in SCENES:
            self._json(400, {"error": f"cena inválida: {scene!r}"})
            return
        with _lock:
            frame = STATE["last_frame"]
            if frame is None:
                self._json(409, {"error": "nenhum frame exibido ainda"})
                return
            saved = save_frame(frame, scene, STATE["out_dir"])
        self._json(200, {"file": saved.name, "stats": dataset_stats(STATE["out_dir"])})


PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Coleta ESP32-CAM</title>
<style>
:root{--bg:#121514;--panel:#1b1f1d;--fg:#e6e9e5;--muted:#9aa39c;--line:#2c322e;--rec:#e5484d;--ok:#3fb27f;color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px;display:grid;grid-template-columns:minmax(0,2fr) minmax(260px,1fr);gap:20px}
@media(max-width:800px){main{grid-template-columns:1fr}}
.cam{position:relative;background:#000;border-radius:8px;overflow:hidden;aspect-ratio:4/3}
.cam img{width:100%;height:100%;object-fit:contain;display:block}
.badge{position:absolute;top:10px;left:10px;padding:3px 9px;border-radius:4px;font:600 12px ui-monospace,monospace;background:#000a}
.flash{position:absolute;inset:0;background:#fff;opacity:0;pointer-events:none;transition:opacity .25s}
.flash.on{opacity:.55;transition:none}
aside{display:grid;gap:14px;align-content:start}
h1{font-size:1.1rem;margin:0}
.scenes{display:grid;gap:6px}
.scenes label{display:flex;justify-content:space-between;padding:8px 10px;border:1px solid var(--line);border-radius:6px;cursor:pointer}
.scenes input{margin-right:8px}
.scenes label:has(input:checked){border-color:var(--fg)}
.n{font:600 13px ui-monospace,monospace;color:var(--muted)}
button{font:inherit;padding:10px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--fg);cursor:pointer}
button.rec{background:var(--rec);border-color:var(--rec);color:#fff;font-weight:600}
button:disabled{opacity:.5;cursor:default}
.row{display:flex;gap:8px}.row>*{flex:1}
#log{font:12px ui-monospace,monospace;color:var(--muted);min-height:3em}
small{color:var(--muted)}
</style></head><body><main>
<section><div class="cam"><img id="cam" alt="preview da câmera"><div class="flash" id="flash"></div><span class="badge" id="badge">conectando…</span></div>
<small>Atalhos: <b>Espaço</b> captura 1 · <b>R</b> inicia/para rajada · <b>1–5</b> troca a cena</small></section>
<aside><h1>Coleta ESP32-CAM</h1>
<div class="scenes" id="scenes"></div>
<div class="row"><label>Rajada <input id="burstN" type="number" value="10" min="1" max="100" style="width:4em"></label>
<label>intervalo (s) <input id="burstI" type="number" value="1" min="0.3" step="0.1" style="width:4em"></label></div>
<div class="row"><button id="one">Capturar 1</button><button id="burst" class="rec">● Rajada</button></div>
<div id="log"></div>
<small>Cada foto salva é o frame que está na tela. Meta: ~50 por objeto, ~30 em <i>misto</i>, ~20 em <i>vazio</i>.</small>
</aside></main>
<script>
const SCENES=["garrafa","caderno","caneca","misto","vazio"];
const cam=document.getElementById('cam'),badge=document.getElementById('badge'),log=document.getElementById('log');
const box=document.getElementById('scenes');
SCENES.forEach((s,i)=>{box.insertAdjacentHTML('beforeend',`<label><span><input type="radio" name="scene" value="${s}" ${i?'':'checked'}>${i+1}. ${s}</span><span class="n" id="n-${s}">0</span></label>`)});
const scene=()=>document.querySelector('input[name=scene]:checked').value;
function stats(s){for(const k in s)document.getElementById('n-'+k).textContent=s[k]}
fetch('/stats').then(r=>r.json()).then(stats);
let fps=0,frames=0;setInterval(()=>{fps=frames;frames=0},1000);
function loop(){const t=performance.now();const img=new Image();
 img.onload=()=>{cam.src=img.src;frames++;badge.textContent=bursting?`● GRAVANDO ${scene()} · ${fps} fps`:`ao vivo · ${fps} fps`;badge.style.color=bursting?'var(--rec)':'var(--ok)';setTimeout(loop,0)};
 img.onerror=()=>{badge.textContent='sem sinal da placa';badge.style.color='var(--rec)';setTimeout(loop,1000)};
 img.src='/frame?t='+t}
loop();
async function save(){const r=await fetch('/save?scene='+scene(),{method:'POST'});const j=await r.json();
 if(!r.ok){log.textContent='Erro: '+j.error;return false}
 const f=document.getElementById('flash');f.classList.add('on');requestAnimationFrame(()=>requestAnimationFrame(()=>f.classList.remove('on')));
 stats(j.stats);log.textContent='Salvo '+j.file;return true}
let bursting=false;
async function burst(){if(bursting){bursting=false;return}
 bursting=true;const b=document.getElementById('burst');b.textContent='■ Parar';
 const n=+document.getElementById('burstN').value,iv=+document.getElementById('burstI').value*1000;
 for(let i=0;i<n&&bursting;i++){if(!await save())break;log.textContent+=` (${i+1}/${n})`;await new Promise(r=>setTimeout(r,iv))}
 bursting=false;b.textContent='● Rajada'}
document.getElementById('one').onclick=save;document.getElementById('burst').onclick=burst;
document.addEventListener('keydown',e=>{if(e.target.tagName==='INPUT'&&e.target.type==='number')return;
 if(e.code==='Space'){e.preventDefault();save()}else if(e.key==='r'||e.key==='R')burst();
 else if(e.key>='1'&&e.key<='5')document.querySelectorAll('input[name=scene]')[+e.key-1].checked=true});
</script></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--out", type=Path, default=Path("dataset"))
    args = parser.parse_args()
    STATE.update(host=args.host, out_dir=args.out)
    print(f"Coleta em http://localhost:{args.port}  (placa: http://{args.host})")
    ThreadingHTTPServer(("127.0.0.1", args.port), Handler).serve_forever()


if __name__ == "__main__":
    main()
