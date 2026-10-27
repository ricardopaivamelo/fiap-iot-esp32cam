import base64
import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer

import pytest

import viewer

JPEG = b"\xff\xd8" + b"\x00" * 64 + b"\xff\xd9"
DET = {"dsp": 12, "nn": 2700, "boxes": [{"label": "caneca", "conf": 0.83, "x": 40, "y": 32, "w": 8, "h": 8}]}


def test_parse_frame_decodifica_jpeg():
    kind, payload = viewer.parse_line("#FRAME " + base64.b64encode(JPEG).decode())
    assert kind == "frame"
    assert payload == JPEG


def test_parse_det_json():
    kind, payload = viewer.parse_line("#DET " + json.dumps(DET))
    assert kind == "det"
    assert payload["boxes"][0]["label"] == "caneca"


@pytest.mark.parametrize("line", [
    "#FRAME " + base64.b64encode(JPEG).decode()[:-12],  # base64 cortado no meio do envio
    "#FRAME " + base64.b64encode(b"nao-e-jpeg").decode(),
    "#FRAME %%%",
])
def test_parse_frame_truncado_vira_log(line):
    assert viewer.parse_line(line) == ("log", line)


@pytest.mark.parametrize("line", ['#DET {"boxes":[', '#DET [1, 2]', '#DET {"dsp": 1}'])
def test_parse_det_json_quebrado_vira_log(line):
    assert viewer.parse_line(line) == ("log", line)


def test_parse_lixo_do_boot():
    line = "ets Jun  8 2016 00:22:57"
    assert viewer.parse_line(line) == ("log", line)


def test_scale_box_squash():
    box = viewer.scale_box({"label": "caneca", "conf": 0.9, "x": 48, "y": 48, "w": 8, "h": 8}, 320, 240)
    assert (box["x"], box["y"], box["h"]) == (160, 120, 20)
    assert box["w"] == pytest.approx(26.667, abs=0.01)
    assert box["label"] == "caneca"


def test_handle_line_atualiza_estado():
    viewer.reset_state()
    viewer.handle_line("#FRAME " + base64.b64encode(JPEG).decode())
    viewer.handle_line("#DET " + json.dumps(DET))
    viewer.handle_line("Camera initialized")
    assert viewer.STATE["frame"] == JPEG
    assert viewer.STATE["det"] == DET
    assert list(viewer.STATE["log"]) == ["Camera initialized"]


@pytest.fixture
def server():
    viewer.reset_state()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), viewer.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


def test_http_frame_503_sem_frame(server):
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"{server}/frame")
    assert exc.value.code == 503


def test_http_det_devolve_estado(server):
    viewer.handle_line("#FRAME " + base64.b64encode(JPEG).decode())
    viewer.handle_line("#DET " + json.dumps(DET))
    viewer.handle_line("Predictions (DSP: 12 ms.)")
    with urllib.request.urlopen(f"{server}/frame") as r:
        assert r.headers["Content-Type"] == "image/jpeg"
        assert r.read() == JPEG
    with urllib.request.urlopen(f"{server}/det") as r:
        body = json.loads(r.read())
    assert body["det"] == DET
    assert body["log"] == ["Predictions (DSP: 12 ms.)"]
    assert body["age"] >= 0
