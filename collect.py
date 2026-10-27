"""Coleta imagens do ESP32-CAM (firmware VisionGuard, GET /capture) para o dataset do Edge Impulse."""

import argparse
import re
import time
from pathlib import Path

import requests

DEFAULT_HOST = "192.168.1.6"
MAX_CONSECUTIVE_FAILURES = 10
JPEG_SOI = b"\xff\xd8"
JPEG_EOI = b"\xff\xd9"


def next_index(folder: Path, label: str) -> int:
    """Próximo índice livre em `<label>_NNNN.jpg`, para retomar uma coleta sem sobrescrever."""
    if not folder.is_dir():
        return 0
    pattern = re.compile(rf"^{re.escape(label)}_(\d+)\.jpg$")
    indices = [int(m.group(1)) for f in folder.iterdir() if (m := pattern.match(f.name))]
    return max(indices) + 1 if indices else 0


def fetch_frame(host: str, timeout: float = 5.0) -> bytes | None:
    """Baixa um frame; devolve None se a requisição falhar ou o corpo não for um JPEG completo."""
    try:
        resp = requests.get(f"http://{host}/capture", timeout=timeout)
    except requests.RequestException:
        return None
    body = resp.content
    if resp.status_code != 200 or not (body.startswith(JPEG_SOI) and body.endswith(JPEG_EOI)):
        return None
    return body


def save_frame(frame: bytes, label: str, out_dir: Path = Path("dataset")) -> Path:
    """Grava o frame como o próximo `<label>_NNNN.jpg` em `out_dir/<label>/`."""
    folder = out_dir / label
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{label}_{next_index(folder, label):04d}.jpg"
    path.write_bytes(frame)
    return path


def collect(host: str, label: str, count: int, interval: float, out_dir: Path = Path("dataset")) -> int:
    """Salva `count` frames válidos em `out_dir/<label>/`; desiste após falhas seguidas. Retorna quantos salvou."""
    saved = failures = 0
    while saved < count:
        frame = fetch_frame(host)
        if frame is None:
            failures += 1
            if failures >= MAX_CONSECUTIVE_FAILURES:
                print(f"[ERRO] {failures} falhas seguidas em http://{host}/capture — confira WiFi/IP da placa.")
                break
            continue
        failures = 0
        save_frame(frame, label, out_dir)
        saved += 1
        print(f"{label} {saved}/{count}")
        if saved < count:
            time.sleep(interval)
    return saved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--label", required=True)
    parser.add_argument("--count", type=int, required=True)
    parser.add_argument("--interval", type=float, default=1.0)
    parser.add_argument("--host", default=DEFAULT_HOST)
    parser.add_argument("--out", type=Path, default=Path("dataset"))
    args = parser.parse_args()
    saved = collect(args.host, args.label, args.count, args.interval, args.out)
    raise SystemExit(0 if saved == args.count else 1)


if __name__ == "__main__":
    main()
