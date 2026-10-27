from unittest.mock import MagicMock, patch

import requests

import collect

JPEG = b"\xff\xd8" + b"\x00" * 64 + b"\xff\xd9"


def _response(body: bytes, status: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status
    resp.content = body
    return resp


def test_next_index_continua_numeracao(tmp_path):
    folder = tmp_path / "caneca"
    folder.mkdir()
    assert collect.next_index(folder, "caneca") == 0
    (folder / "caneca_0000.jpg").write_bytes(JPEG)
    (folder / "caneca_0007.jpg").write_bytes(JPEG)
    assert collect.next_index(folder, "caneca") == 8


def test_next_index_pasta_inexistente(tmp_path):
    assert collect.next_index(tmp_path / "nao_existe", "x") == 0


@patch("collect.requests.get")
def test_fetch_frame_rejeita_nao_jpeg(mock_get):
    mock_get.return_value = _response(b"<html>")
    assert collect.fetch_frame("192.168.1.6") is None


@patch("collect.requests.get")
def test_fetch_frame_rejeita_status_erro(mock_get):
    mock_get.return_value = _response(JPEG, status=500)
    assert collect.fetch_frame("192.168.1.6") is None


@patch("collect.requests.get")
def test_fetch_frame_aceita_jpeg(mock_get):
    mock_get.return_value = _response(JPEG)
    assert collect.fetch_frame("192.168.1.6") == JPEG
    assert mock_get.call_args.args[0] == "http://192.168.1.6/capture"


@patch("collect.requests.get")
def test_fetch_frame_timeout_retorna_none(mock_get):
    mock_get.side_effect = requests.Timeout()
    assert collect.fetch_frame("192.168.1.6") is None


@patch("collect.time.sleep")
@patch("collect.fetch_frame")
def test_collect_pula_falhas_e_atinge_count(mock_fetch, _sleep, tmp_path):
    mock_fetch.side_effect = [None, JPEG, None, JPEG, JPEG]
    saved = collect.collect("h", "caneca", count=3, interval=0, out_dir=tmp_path)
    files = sorted((tmp_path / "caneca").glob("*.jpg"))
    assert saved == 3
    assert [f.name for f in files] == ["caneca_0000.jpg", "caneca_0001.jpg", "caneca_0002.jpg"]
    assert all(f.stat().st_size > 0 for f in files)


@patch("collect.time.sleep")
@patch("collect.fetch_frame", return_value=None)
def test_collect_desiste_apos_falhas_seguidas(_fetch, _sleep, tmp_path):
    saved = collect.collect("h", "caneca", count=5, interval=0, out_dir=tmp_path)
    assert saved == 0
    assert _fetch.call_count == collect.MAX_CONSECUTIVE_FAILURES
