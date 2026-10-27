# ESP32-CAM + Edge Impulse — Classificação de Objetos (FIAP IoT) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treinar no Edge Impulse um classificador de imagens com dados capturados pelo próprio ESP32-CAM, exportar como biblioteca Arduino e rodar a inferência embarcada na placa, com predições visíveis na serial.

**Architecture:** A coleta reaproveita o firmware VisionGuard já gravado (endpoint `GET /capture` em `http://192.168.1.6`): um script Python puxa JPEGs via WiFi e salva em `dataset/<label>/`. Assim o modelo treina com imagens do mesmo sensor/óptica da inferência. O upload pro Edge Impulse é feito via `edge-impulse-uploader`, o treino e o export via Studio (browser), e o deploy usa o exemplo `esp32_camera` da biblioteca exportada, compilado com `arduino-cli`.

**Tech Stack:** Edge Impulse Studio + `edge-impulse-cli` (Node 24.11.1 já instalado), Python 3.11 (venv próprio), `requests`, `pytest`, `arduino-cli` + core `esp32:esp32`, `esptool` 5.6.0.

**Spec:** Enunciado FIAP IoT (abaixo, verbatim):

> Usando a plataforma Edge Impulse, utilizar uma das duas trilhas de treinamento: Áudio / **Imagem**. Realize o treinamento de um modelo. O modelo será exportado para ESP32 e implantado em: ESP32 com microfone INMP441 (para inferência de áudio), ou **ESP32CAM (para inferência de classificação de objeto)**.

## Global Constraints

- Trilha: **Imagem → detecção de objetos com FOMO** (decisão do Ricardo em 2026-10-27: o professor exige bounding boxes desenhadas manualmente, o que só existe em detecção). Classes: `garrafa`, `caderno`, `caneca`. Sem classe `fundo`: as fotos vazias entram sem box.
- Coleta: tela local `collector_ui.py` (http://localhost:8000) com preview ao vivo. Cenas: `garrafa` ~50, `caderno` ~50, `caneca` ~50, `misto` ~30 (2–3 objetos juntos), `vazio` ~20.
- Labeling: boxes **manuais** no *Labeling queue* do Studio (AI-assisted labeling desligado).
- Plataforma de treino: **Edge Impulse** (obrigatório).
- Alvo de deploy: **ESP32-CAM** clone AI-Thinker (ESP32 + ~4 MB PSRAM, OV2640), FTDI FT232R na **COM3**.
- Export: **Arduino library** do EI, modelo **quantizado int8**.
- Board no arduino-cli: `esp32:esp32:esp32cam` com **PSRAM habilitada**; exemplo com `CAMERA_MODEL_AI_THINKER`.
- Core ESP32: usar a versão que o README da biblioteca exportada indicar; sem indicação, fixar **`esp32:esp32@2.0.17`**.
- Gravação: IO0→GND + RST para entrar em download; **remover IO0→GND + RST** para rodar.
- Projeto em `C:\Users\ricar\dev\fiap-iot-esp32cam\` (repo git próprio). **Nunca** commitar na home-repo; `.env` (API key do EI) no `.gitignore`.
- Commits em PT-BR, formato convencional.

## Decisões em aberto (Ricardo responde antes da Task 2)

- **D1 — Classes:** quais objetos? Default proposto: 2 objetos de mesa bem diferentes (ex.: `caneca`, `tesoura`) + `fundo` (cena sem objeto). 3 classes no total.
- **D2 — Entregável:** o que o professor espera (vídeo, relatório PDF, link do projeto EI público, repo)? Default: README com prints do EI + vídeo curto da serial classificando.
- **D3 — Backup do VisionGuard:** fazer `read-flash` antes de sobrescrever? Default: **sim** (4 MB, 1 min).
- **D4 — Prazo** da entrega.

## Review Focus

1. **Iluminação/ângulo diferentes do treino** → modelo deve continuar acertando; mitigação: coletar em ≥2 condições de luz e ≥3 ângulos por classe (Task 2), validar ao vivo em condição nova (Task 6).
2. **Cena sem objeto** → deve sair `fundo`, não um objeto com confiança alta; mitigação: classe `fundo` obrigatória com o mesmo volume das outras.
3. **PSRAM desabilitada no build** → `ei_camera_init` / alocação do buffer falha em runtime; verificação explícita na Task 5 (log `PSRAM` + primeira inferência).
4. **IO0 ainda jumpeado após gravar** → placa fica em `waiting for download`, parece "travada"; checklist explícito na Task 5.
5. **WiFi caiu / IP mudou durante coleta** → script não pode salvar arquivo vazio/corrompido nem abortar a coleta inteira; teste dedicado na Task 2.

---

### Task 1: Setup do projeto + backup do firmware atual

**Files:**
- Create: `C:\Users\ricar\dev\fiap-iot-esp32cam\.gitignore` (`.venv/`, `.env`, `backup/`, `dataset/`, `build/`, `*.zip`)
- Create: `C:\Users\ricar\dev\fiap-iot-esp32cam\requirements.txt` (`requests`, `pytest`, `esptool==5.6.0`)
- Create: `C:\Users\ricar\dev\fiap-iot-esp32cam\README.md` (esqueleto: objetivo, hardware, como rodar)

**Interfaces:**
- Produces: venv em `.venv\`, `backup\visionguard-4MB.bin`, `arduino-cli` no PATH com core ESP32.

- [ ] **Step 1:** `git init` no diretório do projeto; criar `.gitignore`, `requirements.txt`, `README.md`.
- [ ] **Step 2:** `python -m venv .venv` e `.venv\Scripts\python -m pip install -r requirements.txt`. Esperado: install sem erro.
- [ ] **Step 3 (D3):** Ricardo liga IO0→GND e aperta RST. Rodar `.venv\Scripts\python -m esptool --port COM3 chip-id`. Esperado: `Chip is ESP32-D0WD...` + MAC.
- [ ] **Step 4:** `.venv\Scripts\python -m esptool --port COM3 read-flash 0 0x400000 backup\visionguard-4MB.bin`. Esperado: arquivo de 4.194.304 bytes. Ricardo remove IO0→GND e aperta RST (VisionGuard volta; precisa dele na Task 2).
- [ ] **Step 5:** Instalar arduino-cli (`winget install ArduinoSA.CLI`), `arduino-cli core update-index --additional-urls https://espressif.github.io/arduino-esp32/package_esp32_index.json`, `arduino-cli core install esp32:esp32@2.0.17 --additional-urls <mesma URL>`. Esperado: `arduino-cli board listall esp32cam` lista `esp32:esp32:esp32cam`.
- [ ] **Step 6:** `npm install -g edge-impulse-cli`. Esperado: `edge-impulse-uploader --version` responde. (Se falhar build nativo no Node 24, fallback: upload por drag-and-drop no Studio na Task 3.)
- [ ] **Step 7:** Commit `chore: setup do projeto ESP32-CAM + Edge Impulse`.

### Task 2: Script de coleta via `/capture` + dataset

**Files:**
- Create: `collect.py`
- Test: `tests/test_collect.py`

**Interfaces:**
- Consumes: firmware VisionGuard em `http://192.168.1.6` (`GET /capture` → `image/jpeg`).
- Produces: `dataset/<label>/<label>_<NNNN>.jpg`; CLI `python collect.py --label <nome> --count <n> [--interval 1.0] [--host 192.168.1.6]`.

- [ ] **Step 1: Testes que falham** em `tests/test_collect.py` (HTTP mockado com `unittest.mock.patch("collect.requests.get")`):
  - `test_next_index_continua_numeracao`: com `caneca_0000.jpg` e `caneca_0007.jpg` em `tmp_path/caneca`, `next_index(tmp_path/"caneca", "caneca") == 8`; pasta vazia → `0`.
  - `test_fetch_frame_rejeita_nao_jpeg`: resposta 200 com bytes `b"<html>"` → `fetch_frame(...)` retorna `None`.
  - `test_fetch_frame_aceita_jpeg`: corpo começando com `b"\xff\xd8"` e terminando com `b"\xff\xd9"` → retorna os bytes.
  - `test_fetch_frame_timeout_retorna_none`: `requests.get` levanta `requests.Timeout` → `None` (Review Focus 5).
  - `test_collect_pula_falhas_e_atinge_count`: mock alterna `None`/JPEG válido; `collect(..., count=3)` grava exatamente 3 arquivos e não grava nenhum vazio.
- [ ] **Step 2:** `.venv\Scripts\python -m pytest tests -v`. Esperado: FAIL (`ModuleNotFoundError: collect`).
- [ ] **Step 3:** Implementar em `collect.py`:
  - `next_index(folder: Path, label: str) -> int`
  - `fetch_frame(host: str, timeout: float = 5.0) -> bytes | None` — valida SOI `FFD8` e EOI `FFD9`.
  - `collect(host: str, label: str, count: int, interval: float, out_dir: Path = Path("dataset")) -> int` — retorna nº salvo; desiste após 10 falhas seguidas com mensagem clara.
  - `main()` com argparse; imprime progresso `caneca 12/80`.
- [ ] **Step 4:** pytest de novo. Esperado: 5 passed.
- [ ] **Step 5 (smoke real):** `python collect.py --label teste --count 2`. Esperado: 2 JPEGs abríveis em `dataset/teste/`; apagar a pasta depois.
- [ ] **Step 6:** Commit `feat: script de coleta de imagens via endpoint /capture`.
- [ ] **Step 7 (coleta, com Ricardo posicionando objetos):** para cada classe de D1, **80 imagens**, intervalo 1.0 s, girando o objeto/variando distância; metade com luz do dia, metade com luz artificial. `fundo` = mesma mesa sem objeto. Conferir por amostragem visual que não há frames borrados/pretos (apagar e recoletar se houver).

### Task 3: Projeto no Edge Impulse + upload

**Files:**
- Create: `.env` (`EI_API_KEY=ei_...`, **não commitado**)

**Interfaces:**
- Consumes: `dataset/<label>/*.jpg` da Task 2.
- Produces: projeto EI `fiap-iot-esp32cam` com dados rotulados, split ~80/20.

- [ ] **Step 1:** Ricardo cria o projeto no Studio, define *Labeling method = Bounding boxes (object detection)* e copia a API key (Dashboard → Keys) para `.env`.
- [ ] **Step 2:** Por cena, **sem `--label`**: `edge-impulse-uploader --api-key $env:EI_API_KEY --category split dataset\<cena>\*.jpg`. Esperado: `Files uploaded successful` com a contagem da cena.
- [ ] **Step 3 (manual, Ricardo):** Labeling queue: desenhar uma box por objeto visível (`garrafa`/`caderno`/`caneca`); fotos de `vazio` ficam sem box. Print em `docs/img/01-labeling.png`.
- [ ] **Step 4:** Data acquisition: conferir split Training/Test ≈ 80/20 e zero imagens com objeto sem box. Print em `docs/img/02-dataset.png`.

### Task 4: Impulse + treino

**Interfaces:**
- Produces: modelo int8 com métricas registradas em `docs/img/`.

- [ ] **Step 1 — Impulse design:** Image data **96×96**, resize *Fit shortest axis*; processing block **Image** (color depth **Grayscale**; RGB só se o F1 ficar abaixo da meta); learning block **Object Detection (Images)**.
- [ ] **Step 2 — Features:** Generate features. Print `docs/img/03-features.png`.
- [ ] **Step 3 — Treino:** **FOMO (MobileNetV2 0.35)**, 60 epochs, learning rate 0.001. Target device: **Espressif ESP-EYE (ESP32 240MHz)**.
- [ ] **Step 4 — Critério de aceite:** **F1 de validação ≥ 0.80** por classe e estimativa on-device int8 com **RAM < 250 KB e Flash < 1 MB**. Abaixo disso: primeiro mais fotos da classe com F1 mais baixo, depois RGB. Print `docs/img/04-training.png`.
- [ ] **Step 5 — Model testing:** Classify all no test set. Esperado: F1 de teste ≥ 0.75. Print `docs/img/05-test.png`.

### Task 5: Export e deploy no ESP32-CAM

**Files:**
- Create: `firmware/esp32_camera/esp32_camera.ino` (cópia do exemplo da lib, com `#define CAMERA_MODEL_AI_THINKER` e os outros modelos comentados)
- Create: `build.ps1` (compile + upload, parametrizado por porta)

**Interfaces:**
- Consumes: zip `ei-fiap-iot-esp32cam-arduino-*.zip` exportado do Studio.

- [ ] **Step 1:** Studio → Deployment → **Arduino library**, otimização **Quantized (int8)**, compilador EON ligado. Baixar o zip para a raiz do projeto (ignorado no git). Ler o README do zip e ajustar a versão do core se ele exigir outra (Global Constraints).
- [ ] **Step 2:** `arduino-cli lib install --zip-path <zip>` (precisa `arduino-cli config set library.enable_unsafe_install true`). Copiar `examples/esp32/esp32_camera` para `firmware/` e ajustar o define do modelo de câmera.
- [ ] **Step 3:** `arduino-cli compile --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app firmware\esp32_camera --output-dir build`. Esperado: compila; uso de flash < 100% da partição. (PSRAM vem habilitada no fqbn `esp32cam`; se o core usado expuser a opção, passar `PSRAM=enabled`.)
- [ ] **Step 4:** Ricardo: IO0→GND + RST. `arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32cam --input-dir build`. Esperado: `Hash of data verified`.
- [ ] **Step 5:** Ricardo: **remove IO0→GND** + RST (Review Focus 4). Abrir serial 115200 (`arduino-cli monitor -p COM3 -c baudrate=115200`). Esperado: `Camera initialized` e linhas `Predictions (DSP: x ms., Classification: y ms.)` com as 3 classes a cada ciclo. Se `Failed to allocate snapshot buffer` → PSRAM (Review Focus 3).
- [ ] **Step 6:** Commit `feat: firmware de inferência Edge Impulse para ESP32-CAM`.

### Task 6: Validação ao vivo + entregável

**Files:**
- Modify: `README.md` (resultados, prints, latência, como reproduzir)
- Create: `docs/resultados.md` (tabela de testes ao vivo)

- [ ] **Step 1:** Teste ao vivo: 10 tentativas por classe, em **iluminação diferente da coleta** (Review Focus 1), incluindo cena vazia (Review Focus 2). Registrar acerto/erro e confiança em `docs/resultados.md`. Meta: ≥ 8/10 por classe.
- [ ] **Step 2:** Capturar log da serial (`docs/serial-log.txt`) e gravar vídeo curto (celular) mostrando objeto → predição.
- [ ] **Step 3:** Atualizar README conforme D2 (métricas do EI, latência DSP/inferência, RAM/Flash, limitações).
- [ ] **Step 4:** Commit `docs: resultados e relatório do trabalho`. Se D2 pedir repo: criar GitHub privado e pushar (push automático após verde).
- [ ] **Step 5 (opcional):** restaurar VisionGuard com `esptool write-flash 0 backup\visionguard-4MB.bin` depois da entrega.
