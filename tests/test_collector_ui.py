import json
import threading
import urllib.request
from http.server import ThreadingHTTPServer
from unittest.mock import patch

import pytest

import collect
import collector_ui

JPEG = b"\xff\xd8" + b"\x00" * 64 + b"\xff\xd9"


def test_save_frame_numera_em_sequencia(tmp_path):
    p1 = collect.save_frame(JPEG, "caneca", tmp_path)
    p2 = collect.save_frame(JPEG, "caneca", tmp_path)
    assert (p1.name, p2.name) == ("caneca_0000.jpg", "caneca_0001.jpg")
    assert p2.read_bytes() == JPEG


def test_dataset_stats_conta_por_cena(tmp_path):
    collect.save_frame(JPEG, "garrafa", tmp_path)
    collect.save_frame(JPEG, "garrafa", tmp_path)
    collect.save_frame(JPEG, "vazio", tmp_path)
    stats = collector_ui.dataset_stats(tmp_path)
    assert stats == {"garrafa": 2, "caderno": 0, "caneca": 0, "misto": 0, "vazio": 1}


@pytest.fixture
def server(tmp_path):
    collector_ui.STATE.update(last_frame=None, host="h", out_dir=tmp_path)
    srv = ThreadingHTTPServer(("127.0.0.1", 0), collector_ui.Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}", tmp_path
    srv.shutdown()


def _post(url):
    req = urllib.request.Request(url, method="POST")
    try:
        with urllib.request.urlopen(req) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read())


def test_save_sem_frame_retorna_409(server):
    base, _ = server
    status, body = _post(f"{base}/save?scene=caneca")
    assert status == 409
    assert "frame" in body["error"]


def test_save_cena_invalida_retorna_400(server):
    base, _ = server
    collector_ui.STATE["last_frame"] = JPEG
    status, _ = _post(f"{base}/save?scene=../../etc")
    assert status == 400


@patch("collector_ui.fetch_frame", return_value=JPEG)
def test_frame_e_save_gravam_o_frame_exibido(_fetch, server):
    base, out = server
    with urllib.request.urlopen(f"{base}/frame") as r:
        assert r.headers["Content-Type"] == "image/jpeg"
        assert r.read() == JPEG
    status, body = _post(f"{base}/save?scene=caneca")
    assert status == 200
    assert body["file"] == "caneca_0000.jpg"
    assert body["stats"]["caneca"] == 1
    assert (out / "caneca" / "caneca_0000.jpg").read_bytes() == JPEG


@patch("collector_ui.fetch_frame", return_value=None)
def test_frame_indisponivel_retorna_503(_fetch, server):
    base, _ = server
    with pytest.raises(urllib.error.HTTPError) as exc:
        urllib.request.urlopen(f"{base}/frame")
    assert exc.value.code == 503
