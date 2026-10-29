import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
import resultados_validacao as rv  # noqa: E402


def _b(label, conf=0.9):
    return {"label": label, "conf": conf, "x": 40, "y": 40, "w": 8, "h": 8}


@pytest.mark.parametrize("scene, boxes, acerto", [
    ("caneca", [_b("caneca")], True),
    ("caneca", [_b("caneca"), _b("caneca", 0.6)], True),  # FOMO pode dar 2 centróides no mesmo objeto
    ("caneca", [_b("caneca"), _b("garrafa")], False),  # classe certa + falso positivo
    ("caneca", [_b("garrafa")], False),
    ("caneca", [], False),
    ("misto", [_b("caneca"), _b("garrafa"), _b("caderno")], True),
    ("misto", [_b("caneca"), _b("garrafa")], False),
    ("vazio", [], True),
    ("vazio", [_b("caneca", 0.55)], False),
])
def test_avaliar(scene, boxes, acerto):
    assert rv.avaliar(scene, boxes) is acerto


@pytest.mark.parametrize("scene, acertos, total, esperado", [
    ("caneca", 8, 10, "✅"), ("caneca", 7, 10, "❌"), ("garrafa", 4, 5, "✅"),
    ("vazio", 5, 5, "✅"), ("vazio", 4, 5, "❌"), ("misto", 1, 5, "—"),
])
def test_meta(scene, acertos, total, esperado):
    assert rv.meta(scene, acertos, total) == esperado


@pytest.mark.parametrize("boxes, acerto", [
    ([_b("caneca"), _b("caderno")], True),
    ([_b("caneca"), _b("caderno"), _b("garrafa")], False),  # garrafa não estava na cena
    ([_b("caneca")], False),
])
def test_avaliar_misto_com_gabarito(boxes, acerto):
    assert rv.avaliar("misto", boxes, esperado=["caneca", "caderno"]) is acerto


def test_coletar_usa_gabarito_do_misto(tmp_path):
    (tmp_path / "misto").mkdir()
    (tmp_path / "misto" / "misto_0000.json").write_text(
        json.dumps({"scene": "misto", "seq": 1, "det": {"boxes": [_b("caneca"), _b("caderno")]}}), encoding="utf-8")
    (tmp_path / "gabarito.json").write_text(json.dumps({"misto_0000": ["caneca", "caderno"]}), encoding="utf-8")
    [t] = rv.coletar(tmp_path)["misto"]
    assert (t["acerto"], t["esperado"]) == (True, "caderno, caneca")


def test_coletar_le_tentativas_em_ordem(tmp_path):
    (tmp_path / "caneca").mkdir()
    for i, boxes in enumerate([[_b("caneca", 0.97)], [_b("garrafa", 0.6)]]):
        (tmp_path / "caneca" / f"caneca_{i:04d}.json").write_text(
            json.dumps({"scene": "caneca", "seq": i + 1, "det": {"boxes": boxes}}), encoding="utf-8")
    t = rv.coletar(tmp_path)
    assert [(x["arquivo"], x["acerto"]) for x in t["caneca"]] == [("caneca_0000", True), ("caneca_0001", False)]
    assert t["caneca"][0]["rotulos"] == "caneca 97%"
    assert t["vazio"] == []
