"""Gera folhas de conferência (grades 4x4) das boxes atuais no Edge Impulse, para revisão e relatório.

Uso (da raiz do projeto): python tools/folhas_rotulagem.py caderno [misto ...]
Lê só amostras ativas `v2-<cena>*`; a foto vem de `dataset-v2/<cena>/`. Nunca imprime a chave.
"""

import io
import sys
from pathlib import Path

import requests
from PIL import Image, ImageDraw

key = next(l.split("=", 1)[1].strip() for l in Path(".env").read_text().splitlines() if l.startswith("EI_API_KEY="))
H = {"x-api-key": key}
API = "https://studio.edgeimpulse.com/v1/api/1149980"
OUT = Path("docs/img/rotulagem-v2")
COLORS = {"garrafa": (63, 178, 127), "caderno": (255, 170, 0), "caneca": (76, 154, 255)}
COLS, ROWS, W, HT, BAR = 4, 4, 320, 240, 18


def samples(scene: str) -> list[dict]:
    out = []
    for cat in ("training", "testing"):
        offset = 0
        while batch := requests.get(f"{API}/raw-data", headers=H, timeout=30,
                                    params={"category": cat, "limit": 100, "offset": offset}).json().get("samples"):
            out += [s for s in batch if not s.get("isDisabled") and s["filename"].startswith(f"v2-{scene}")]
            offset += len(batch)
    return sorted(out, key=lambda s: s["filename"])


def local_photo(scene: str, filename: str) -> Path:
    # v2-<cena>_NNNN -> <cena>_NNNN.jpg; v2-<cena>_movida-<nome> -> <nome>.jpg (foto movida de pasta na revisão)
    stem = filename.removeprefix("v2-")
    stem = stem.split("_movida-", 1)[1] if "_movida-" in stem else stem
    return Path("dataset-v2") / scene / f"{stem}.jpg"


def photo(scene: str, s: dict) -> Image.Image:
    path = local_photo(scene, s["filename"])
    if path.exists():
        return Image.open(path)
    # apagada localmente depois do upload: usa a cópia do Edge Impulse
    r = requests.get(f"{API}/raw-data/{s['id']}/image", headers=H, timeout=30)
    r.raise_for_status()
    return Image.open(io.BytesIO(r.content))


def cell(scene: str, s: dict) -> Image.Image:
    im = Image.new("RGB", (W, HT + BAR), "white")
    im.paste(photo(scene, s).convert("RGB").resize((W, HT)), (0, BAR))
    d = ImageDraw.Draw(im)
    boxes = s.get("boundingBoxes") or []
    d.text((3, 3), f"{s['filename']}  [{s['category']}]  {len(boxes)} box", fill="black")
    for b in boxes:
        c = COLORS.get(b["label"], (229, 72, 77))  # vermelho = label fora das 3 classes
        x, y = b["x"], b["y"] + BAR
        d.rectangle([x, y, x + b["width"], y + b["height"]], outline=c, width=3)
        d.rectangle([x, y, x + 7 * len(b["label"]) + 6, y + 13], fill=c)
        d.text((x + 3, y + 1), b["label"], fill="black")
    return im


def main(scenes: list[str]) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    per = COLS * ROWS
    for scene in scenes:
        ss = samples(scene)
        for i in range(0, len(ss), per):
            sheet = Image.new("RGB", (COLS * W, ROWS * (HT + BAR)), "white")
            for j, s in enumerate(ss[i:i + per]):
                sheet.paste(cell(scene, s), ((j % COLS) * W, (j // COLS) * (HT + BAR)))
            path = OUT / f"{scene}_folha_{i // per + 1:02d}.png"
            sheet.save(path)
            print(path)
        print(f"{scene}: {len(ss)} amostras, {sum(1 for s in ss if s.get('boundingBoxes'))} com box")


if __name__ == "__main__":
    main(sys.argv[1:] or ["caderno"])
