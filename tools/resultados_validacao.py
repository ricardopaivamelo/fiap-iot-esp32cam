"""Avalia as tentativas da validação ao vivo e imprime as tabelas em Markdown para docs/resultados.md.

Uso (da raiz do projeto): python tools/resultados_validacao.py validacao [--meta]
Cada tentativa é um par `<cena>/<cena>_NNNN.jpg` + `.json` gravado pela tecla 1–5 do viewer
(`viewer.py --out validacao`); o JSON traz as detecções daquele mesmo quadro.
"""

import json
import sys
from pathlib import Path

SCENES = ("garrafa", "caderno", "caneca", "misto", "vazio")
CLASSES = {"garrafa", "caderno", "caneca"}
META = {"garrafa": 8, "caderno": 8, "caneca": 8}  # plano, Task 7 Step 1: ≥ 8/10 por classe; vazio: 0 falsos


def avaliar(scene: str, boxes: list[dict]) -> bool:
    """Acerto = exatamente as classes da cena (objeto sozinho: só ele; misto: as três; vazio: nada)."""
    labels = {b["label"] for b in boxes}
    if scene == "vazio":
        return not labels
    if scene == "misto":
        return labels == CLASSES
    return labels == {scene}


def coletar(folder: Path) -> dict[str, list[dict]]:
    out = {}
    for scene in SCENES:
        out[scene] = []
        for path in sorted((folder / scene).glob(f"{scene}_*.json")):
            boxes = json.loads(path.read_text(encoding="utf-8"))["det"]["boxes"]
            out[scene].append({
                "arquivo": path.stem,
                "rotulos": ", ".join(f"{b['label']} {round(b['conf'] * 100)}%" for b in boxes) or "—",
                "acerto": avaliar(scene, boxes),
            })
    return out


def meta(scene: str, acertos: int, total: int) -> str:
    """Meta do plano: classe ≥ 8 em 10 (proporcional ao total); vazio sem nenhum falso positivo; misto sem meta."""
    if scene == "misto":
        return "—"
    ok = acertos == total if scene == "vazio" else acertos * 10 >= META[scene] * total
    return "✅" if ok else "❌"


def markdown(t: dict[str, list[dict]], com_meta: bool) -> str:
    linhas = ["| Cena | Tentativas | Acertos | Taxa |" + (" Meta |" if com_meta else ""),
              "|---|---|---|---|" + ("---|" if com_meta else "")]
    for scene, ts in t.items():
        if not ts:
            continue
        ok = sum(x["acerto"] for x in ts)
        linhas.append(f"| {scene} | {len(ts)} | {ok} | {ok / len(ts):.0%} |" + (f" {meta(scene, ok, len(ts))} |" if com_meta else ""))
    for scene, ts in t.items():
        if not ts:
            continue
        linhas += ["", f"**{scene}**", "", "| Tentativa | Detecções (conf.) | Acerto |", "|---|---|---|"]
        linhas += [f"| `{x['arquivo']}` | {x['rotulos']} | {'✅' if x['acerto'] else '❌'} |" for x in ts]
    return "\n".join(linhas)


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    print(markdown(coletar(Path(args[0] if args else "validacao")), "--meta" in sys.argv))
