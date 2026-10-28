"""Confere no Edge Impulse: amostras sem box (exceto vazio), labels distintos e split. Nunca imprime a chave."""

from collections import Counter
from pathlib import Path

import requests

key = next(l.split("=", 1)[1].strip() for l in Path(".env").read_text().splitlines() if l.startswith("EI_API_KEY="))
H = {"x-api-key": key}
API = "https://studio.edgeimpulse.com/v1/api"

proj = requests.get(f"{API}/projects", headers=H, timeout=30).json()["projects"][0]
pid = proj["id"]
print("projeto:", proj["name"], pid)

labels = Counter()
missing = []
for cat in ("training", "testing"):
    offset, n = 0, 0
    while True:
        r = requests.get(f"{API}/{pid}/raw-data", headers=H, timeout=30,
                         params={"category": cat, "limit": 100, "offset": offset}).json()
        samples = r.get("samples", [])
        if not samples:
            break
        for s in samples:
            n += 1
            boxes = s.get("boundingBoxes") or []
            for b in boxes:
                labels[b["label"]] += 1
                if b["label"] == "vazio": print("BOX vazio em", cat, s["filename"], s["id"])
            if not boxes and not s["filename"].startswith("vazio"):
                missing.append(f"{cat}:{s['filename']}")
        offset += len(samples)
    print(f"{cat}: {n} amostras")

print("boxes por label:", dict(labels))
print("objetos sem box:", len(missing), missing[:30])

