"""Visualizador da inferência FOMO do ESP32-CAM via serial: http://localhost:8001.

O firmware emite, a cada ciclo, `#FRAME <base64 do JPEG>` e `#DET <json>`; o resto da serial é log.
Funciona só com o cabo USB (sem WiFi), então serve tanto na placa do Ricardo quanto na do professor.
Também é a tela da coleta v2 e da validação: `POST /save?scene=&seq=` grava o quadro exibido e, ao lado,
um `.json` com as detecções desse mesmo quadro. `--log` grava a serial (sem `#FRAME`) em arquivo.
"""

import argparse
import base64
import binascii
import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from collect import JPEG_EOI, JPEG_SOI, save_frame
from collector_ui import SCENES, dataset_stats

MODEL_SIZE = 96
LOG_LINES = 20
RECENT_FRAMES = 5  # quadros guardados por seq: a página pode estar exibindo um anterior ao último recebido
STATE: dict = {}
_lock = threading.Lock()


def reset_state() -> None:
    with _lock:
        STATE.update(frame=None, det=None, seq=0, log=deque(maxlen=LOG_LINES), last_rx=None,
                     recent={}, pending=None, out_dir=Path("dataset-v2"), log_file=None)


reset_state()


def parse_line(line: str) -> tuple[str, object]:
    """Classifica uma linha da serial; qualquer mensagem malformada vira log em vez de exceção."""
    if line.startswith("#FRAME "):
        try:
            jpeg = base64.b64decode(line[7:], validate=True)
        except (binascii.Error, ValueError):
            return "log", line
        if jpeg.startswith(JPEG_SOI) and jpeg.endswith(JPEG_EOI):
            return "frame", jpeg
        return "log", line
    if line.startswith("#DET "):
        try:
            det = json.loads(line[5:])
        except json.JSONDecodeError:
            return "log", line
        if isinstance(det, dict) and isinstance(det.get("boxes"), list):
            return "det", det
        return "log", line
    return "log", line


def scale_box(box: dict, frame_w: int, frame_h: int, model_size: int = MODEL_SIZE) -> dict:
    """Leva a box do espaço 96x96 do modelo para pixels do quadro; squash = escalas X e Y independentes."""
    sx, sy = frame_w / model_size, frame_h / model_size
    return {**box, "x": box["x"] * sx, "y": box["y"] * sy, "w": box["w"] * sx, "h": box["h"] * sy}


def handle_line(line: str) -> None:
    kind, payload = parse_line(line)
    with _lock:
        STATE["last_rx"] = time.monotonic()
        if kind != "frame" and line and STATE["log_file"]:
            with open(STATE["log_file"], "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%H:%M:%S')} {line}\n")
        if kind == "frame":
            # o firmware manda o quadro antes da inferência; ele só é publicado junto com o #DET dele
            STATE["pending"] = payload
        elif kind == "det":
            STATE["det"] = payload
            if STATE["pending"] is not None:
                STATE["frame"], STATE["pending"] = STATE["pending"], None
                STATE["seq"] += 1
                STATE["recent"][STATE["seq"]] = (STATE["frame"], payload)
                STATE["recent"].pop(STATE["seq"] - RECENT_FRAMES, None)
        elif line:
            STATE["log"].append(line)


def read_serial(port: str, baud: int) -> None:
    """Lê a serial para sempre; se a porta cair (cabo, RST), tenta reabrir a cada 2 s."""
    import serial

    while True:
        try:
            ser = serial.Serial()
            ser.port, ser.baudrate, ser.timeout = port, baud, 1
            # DTR/RTS em nível baixo: em placas com auto-reset (ESP32-CAM-MB) evita segurar a placa em boot
            ser.dtr = ser.rts = False
            ser.open()
            handle_line(f"[viewer] conectado em {port} @ {baud}")
            while True:
                raw = ser.readline()
                if raw:
                    handle_line(raw.decode("utf-8", errors="replace").strip())
        except serial.SerialException as e:
            handle_line(f"[viewer] serial indisponível: {e}")
            time.sleep(2)


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
        with _lock:
            frame, det, seq = STATE["frame"], STATE["det"], STATE["seq"]
            log, last_rx = list(STATE["log"]), STATE["last_rx"]
        if path == "/":
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")
        elif path == "/frame":
            if frame is None:
                self._json(503, {"error": "nenhum quadro recebido da placa ainda"})
            else:
                self._send(200, frame, "image/jpeg")
        elif path == "/det":
            age = None if last_rx is None else time.monotonic() - last_rx
            self._json(200, {"det": det, "seq": seq, "log": log, "age": age})
        elif path == "/stats":
            self._json(200, dataset_stats(STATE["out_dir"]))
        else:
            self._json(404, {"error": "rota inexistente"})

    def do_POST(self) -> None:
        url = urlparse(self.path)
        if url.path != "/save":
            self._json(404, {"error": "rota inexistente"})
            return
        query = parse_qs(url.query)
        scene = query.get("scene", [""])[0]
        seq = query.get("seq", [""])[0]
        if scene not in SCENES or not seq.isdigit():
            self._json(400, {"error": f"parâmetros inválidos: scene={scene!r} seq={seq!r}"})
            return
        with _lock:
            # pop: cada quadro só pode ser gravado uma vez (tecla repetida antes do próximo quadro gerava cópias)
            entry = STATE["recent"].pop(int(seq), None)
            if entry is None:
                self._json(409, {"error": f"quadro {seq} já gravado ou descartado; espere o próximo quadro"})
                return
            frame, det = entry
            saved = save_frame(frame, scene, STATE["out_dir"])
            # detecções deste mesmo quadro: cada tecla vira uma tentativa registrada na validação
            saved.with_suffix(".json").write_text(json.dumps({"scene": scene, "seq": int(seq), "det": det}),
                                                  encoding="utf-8")
            stats = dataset_stats(STATE["out_dir"])
        self._json(200, {"file": saved.name, "stats": stats})


PAGE = """<!doctype html>
<html lang="pt-BR"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inferência ESP32-CAM</title>
<style>
:root{--bg:#121514;--panel:#1b1f1d;--fg:#e6e9e5;--muted:#9aa39c;--line:#2c322e;--bad:#e5484d;--ok:#3fb27f;color-scheme:dark}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 16px;display:grid;grid-template-columns:minmax(0,2fr) minmax(260px,1fr);gap:20px}
@media(max-width:800px){main{grid-template-columns:1fr}}
.cam{position:relative;background:#000;border-radius:8px;overflow:hidden}
canvas{width:100%;display:block}
.badge{position:absolute;top:10px;left:10px;padding:3px 9px;border-radius:4px;font:600 12px ui-monospace,monospace;background:#000a}
aside{display:grid;gap:14px;align-content:start}
h1{font-size:1.1rem;margin:0}
section{display:grid;gap:10px;align-content:start}
.det{display:grid;gap:6px;grid-template-columns:repeat(auto-fill,minmax(150px,1fr))}
.det div{display:flex;justify-content:space-between;padding:8px 10px;border:1px solid var(--line);border-radius:6px;font-weight:600}
.n{font:600 13px ui-monospace,monospace;color:var(--muted)}
pre{font:12px ui-monospace,monospace;color:var(--muted);background:var(--panel);padding:10px;border-radius:6px;white-space:pre-wrap;margin:0;max-height:260px;overflow:auto}
small{color:var(--muted)}
.cenas{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.cenas button{font:600 14px system-ui;padding:9px 10px;border-radius:6px;border:1px solid var(--line);background:var(--panel);color:var(--fg);cursor:pointer;display:flex;justify-content:space-between}
.cenas button:hover{border-color:var(--ok)}.cenas button:disabled{opacity:.5;cursor:wait}
#saved{min-height:3em}
</style></head><body><main>
<section><div class="cam"><canvas id="cv" width="320" height="240"></canvas><span class="badge" id="badge">aguardando placa…</span></div>
<small><label><input type="checkbox" id="ov"> marcar detecções na imagem</label> — círculo = centróide do FOMO (grade 12×12 sobre a entrada 96×96).</small>
<h1>Inferência ESP32-CAM</h1>
<div class="det" id="det"><small>nenhuma detecção ainda</small></div>
<div class="n" id="timing"></div></section>
<aside><h1>Coleta v2</h1>
<div class="cenas" id="cenas"></div>
<small id="saved">Teclas 1–5 gravam o quadro exibido (as marcações do modelo não entram na foto).</small>
<pre id="log"></pre></aside></main>
<script>
const COLORS={garrafa:'#3fb27f',caderno:'#4c9aff',caneca:'#f5a524'};
const cv=document.getElementById('cv'),ctx=cv.getContext('2d'),badge=document.getElementById('badge');
const img=new Image();let seq=-1,det=null;
img.onload=()=>{cv.width=img.naturalWidth;cv.height=img.naturalHeight;draw()};
const ov=document.getElementById('ov');ov.onchange=draw;
function draw(){ctx.drawImage(img,0,0);if(!det||!ov.checked)return;
 const sx=cv.width/96,sy=cv.height/96;
 for(const b of det.boxes){const c=COLORS[b.label]||'#fff',cx=(b.x+b.w/2)*sx,cy=(b.y+b.h/2)*sy;
  ctx.lineWidth=3;ctx.strokeStyle=c;ctx.beginPath();ctx.arc(cx,cy,Math.max(b.w*sx,14),0,2*Math.PI);ctx.stroke();
  const t=`${b.label} ${Math.round(b.conf*100)}%`;ctx.font='600 14px system-ui';const w=ctx.measureText(t).width;
  ctx.fillStyle=c;ctx.fillRect(cx-w/2-4,cy-Math.max(b.w*sx,14)-24,w+8,20);ctx.fillStyle='#000';ctx.fillText(t,cx-w/2,cy-Math.max(b.w*sx,14)-9)}}
async function tick(){try{const r=await fetch('/det');const j=await r.json();
  document.getElementById('log').textContent=j.log.join('\\n');
  const stale=j.age===null||j.age>6;badge.textContent=stale?'sem sinal da placa':'ao vivo';badge.style.color=stale?'var(--bad)':'var(--ok)';
  if(j.seq!==seq&&j.seq>0){seq=j.seq;det=j.det;img.src='/frame?s='+seq;
   const box=document.getElementById('det');
   box.innerHTML=det&&det.boxes.length?det.boxes.map(b=>`<div style="border-color:${COLORS[b.label]||'#fff'}"><span>${b.label}</span><span class="n">${Math.round(b.conf*100)}%</span></div>`).join(''):'<small>nenhum objeto (background)</small>';
   if(det)document.getElementById('timing').textContent=`captura ${det.cap??'?'} ms · DSP ${det.dsp} ms · inferência ${det.nn} ms · ciclo ${det.loop??'?'} ms`}
 }catch(e){badge.textContent='viewer fora do ar';badge.style.color='var(--bad)'}setTimeout(tick,300)}
tick();
const SCENES=['garrafa','caderno','caneca','misto','vazio'],cenas=document.getElementById('cenas'),saved=document.getElementById('saved');
let busy=false;
function renderStats(st){cenas.innerHTML=SCENES.map((s,i)=>`<button data-s="${s}"><span>${i+1} · ${s}</span><span class="n">${st[s]??0}</span></button>`).join('');
 cenas.querySelectorAll('button').forEach(b=>b.onclick=()=>save(b.dataset.s))}
async function save(scene){if(busy||seq<1)return;busy=true;cenas.querySelectorAll('button').forEach(b=>b.disabled=true);
 try{const r=await fetch(`/save?scene=${scene}&seq=${seq}`,{method:'POST'});const j=await r.json();
  if(r.ok){renderStats(j.stats);saved.textContent=`gravado: ${j.file}`;saved.style.color='var(--ok)'}
  else{saved.textContent=j.error;saved.style.color='var(--bad)'}}
 catch(e){saved.textContent='falha ao gravar';saved.style.color='var(--bad)'}
 busy=false;cenas.querySelectorAll('button').forEach(b=>b.disabled=false)}
document.addEventListener('keydown',e=>{const i=parseInt(e.key,10);if(i>=1&&i<=SCENES.length)save(SCENES[i-1])});
fetch('/stats').then(r=>r.json()).then(renderStats);
</script></body></html>
"""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM3")
    parser.add_argument("--baud", type=int, default=460800)
    parser.add_argument("--http", type=int, default=8001)
    parser.add_argument("--out", type=Path, default=Path("dataset-v2"), help="pasta da coleta v2")
    parser.add_argument("--log", type=Path, help="grava a serial (sem #FRAME) neste arquivo")
    args = parser.parse_args()
    STATE["out_dir"], STATE["log_file"] = args.out, args.log
    threading.Thread(target=read_serial, args=(args.port, args.baud), daemon=True).start()
    print(f"Viewer em http://localhost:{args.http}  (serial {args.port} @ {args.baud})")
    ThreadingHTTPServer(("127.0.0.1", args.http), Handler).serve_forever()


if __name__ == "__main__":
    main()
