# ESP32-CAM + Edge Impulse — Detecção de Objetos FOMO (FIAP IoT) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treinar no Edge Impulse um detector FOMO com dados capturados pelo próprio ESP32-CAM, rodar a inferência embarcada na placa (offline, sem WiFi), provar o funcionamento com vídeo e entregar um repositório que documenta o processo inteiro e permite ao professor gravar o modelo na placa dele.

**Architecture:** A coleta reaproveitou o firmware VisionGuard (`GET /capture`) via `collector_ui.py`. Treino e export no Studio. O firmware de inferência parte do exemplo `esp32_camera` da biblioteca exportada e, a cada ciclo, emite pela serial o JPEG do quadro e as detecções em JSON; um visualizador local (`viewer.py`, stdlib + pyserial) desenha os centróides sobre o quadro no navegador. Assim a demo funciona em qualquer lugar só com o cabo USB — inclusive na placa do professor — e serve de tela para o vídeo.

**Tech Stack:** Edge Impulse Studio + `edge-impulse-uploader`, Python 3.11 (venv), `requests`, `pyserial`, `pytest`, `arduino-cli` + core `esp32:esp32@2.0.17`, `esptool` 5.6.0.

**Spec:** Enunciado FIAP IoT (abaixo, verbatim):

> Usando a plataforma Edge Impulse, utilizar uma das duas trilhas de treinamento: Áudio / **Imagem**. Realize o treinamento de um modelo. O modelo será exportado para ESP32 e implantado em: ESP32 com microfone INMP441 (para inferência de áudio), ou **ESP32CAM (para inferência de classificação de objeto)**.

Contexto adicional (Ricardo, 2026-10-27): o professor provavelmente vai testar o modelo **na ESP32-CAM dele, em sala**, com os objetos treinados.

## Status (2026-10-27)

Tasks 1–4 concluídas (ver ledger). Modelo escolhido: **RGB 96×96, FOMO MobileNetV2 0.35, 100 epochs, float32** — F1 validação 0.805, **F1 teste 0.85** (P 0.78 / R 0.93); estimativa ESP-EYE: 2726 ms, RAM 415 KB, Flash 113 KB. int8 ficou em F1 0.74.

**Decisão (Ricardo):** não retreinar para robustez agora. A prova de funcionamento é o vídeo na placa do Ricardo, na mesma cena do treino; as limitações fora dessa cena são medidas e documentadas, não escondidas.

## Global Constraints

- Trilha: **Imagem → detecção de objetos com FOMO**. Classes: `garrafa`, `caderno`, `caneca`. Fotos vazias sem box (classe implícita `background`).
- Plataforma de treino: **Edge Impulse** (obrigatório).
- Alvo: **ESP32-CAM** clone AI-Thinker (ESP32-D0WD-V3, ~4 MB PSRAM, OV2640), FTDI FT232R na **COM3**.
- Export: **Arduino library**, **Unoptimized (float32)**, EON Compiler ligado. Fallback: int8 se a alocação falhar na placa.
- Pré-processamento no firmware **idêntico ao do treino**: quadro inteiro redimensionado por **squash** para 96×96 RGB (sem crop central).
- Firmware **offline**: nenhuma dependência de WiFi; saída só pela serial a **460800 baud**.
- Build: `esp32:esp32:esp32cam:PartitionScheme=huge_app`, core `esp32:esp32@2.0.17` (salvo se o README da lib exigir outra).
- Gravação: jumper IO0↔GND + RST para gravar; tirar o jumper + RST para rodar.
- Projeto em `C:\Users\ricar\dev\fiap-iot-esp32cam\`. **Nunca** commitar na home-repo. Fora do git: `.env`, `backup/` (senha WiFi), `dataset/`, `build/`, `*.zip`, vídeos.
- Commits em PT-BR, formato convencional.

## Decisões em aberto

- **D2 — Entregável:** default = repositório GitHub com README-relatório + prints + link do vídeo + `.bin` para gravar. Mensagem ao professor enviada/pendente.
- **D4 — Prazo** da entrega.
- **D5 — Visibilidade do repo:** público, ou privado com o professor como colaborador. Default: **público** (sem segredos no repo; backup e `.env` ficam fora).
- **D6 — Vídeo:** default = YouTube **não listado**, link no README (vídeo não entra no git).
- **D7 — Dataset no repo:** default = **não**; reprodutibilidade via projeto Edge Impulse público (Dashboard → *Make public*).

## Review Focus

1. **Pré-processamento diferente do treino** (o exemplo do EI faz crop central; o treino usou squash) → detecções deslocadas e piores na placa. Teste do mapeamento de coordenadas no viewer + verificação na Task 5 de que o firmware usa squash.
2. **Linha de serial truncada/corrompida** (base64 cortado, JSON incompleto, lixo do boot ROM) → o viewer não pode cair; ignora a linha e segue. Testes dedicados na Task 5.
3. **PSRAM / alocação** com float32 (415 KB) → `Failed to allocate` em runtime; fallback int8 documentado.
4. **IO0 ainda jumpeado após gravar** → placa parada em `waiting for download`; checklist na Task 5.
5. **Cena fora do treino** (outra luz, outro fundo, sem mão, outra placa) → desempenho cai; medido sem meta na Task 6 e documentado como limitação na Task 7.

---

### Task 1: Setup do projeto + backup do firmware atual — ✅ concluída

### Task 2: Coleta (`collect.py` + `collector_ui.py`) + dataset — ✅ concluída

### Task 3: Projeto no Edge Impulse + upload + boxes manuais — ✅ concluída

### Task 4: Impulse + treino — ✅ concluída (prints `docs/img/03`–`07`)

### Task 5: Firmware de inferência + visualizador

**Files:**
- Create: `firmware/esp32_camera/esp32_camera.ino` (a partir do exemplo `examples/esp32/esp32_camera` da lib exportada)
- Create: `viewer.py`
- Test: `tests/test_viewer.py`
- Modify: `requirements.txt` (+ `pyserial`)

**Interfaces:**
- Consumes: zip `ei-fiap-iot-esp32cam-arduino-*.zip` (Studio → Deployment).
- Produces (protocolo serial, uma mensagem por linha, 460800 baud):
  - `#FRAME <base64 do JPEG QVGA 320×240>`
  - `#DET {"dsp":<ms>,"nn":<ms>,"boxes":[{"label":"caneca","conf":0.83,"x":40,"y":32,"w":8,"h":8}]}`. Coordenadas no espaço do modelo, 96×96.
  - Qualquer outra linha = log textual (prints originais do exemplo mantidos).
- Produces (Python, `viewer.py`):
  - `parse_line(line: str) -> tuple[str, object]`: `("frame", bytes)` | `("det", dict)` | `("log", str)`. Linha malformada → `("log", line)`, nunca exceção.
  - `scale_box(box: dict, frame_w: int, frame_h: int, model_size: int = 96) -> dict`: devolve `x, y, w, h` em pixels do quadro (squash: escala X e Y independentes).
  - Servidor em `http://localhost:8001`: `GET /` (página), `GET /frame` (último JPEG; 503 sem frame), `GET /det` (última detecção + últimas 20 linhas de log).
  - CLI: `python viewer.py --port COM3 [--baud 460800] [--http 8001]`.

- [ ] **Step 1 (Ricardo):** Studio → Deployment → **Arduino library** → **Unoptimized (float32)**, EON ligado → Build. Zip na raiz do projeto.
- [ ] **Step 2:** `arduino-cli config set library.enable_unsafe_install true`; `arduino-cli lib install --zip-path <zip>`. Ler o README/`library.properties` da lib e conferir a versão do core. Copiar o exemplo para `firmware/esp32_camera/`.
- [ ] **Step 3: Testes que falham** em `tests/test_viewer.py`:
  - `test_parse_frame_decodifica_jpeg`: `"#FRAME " + base64(b"\xff\xd8...\xff\xd9")` → `("frame", bytes)` igual ao original.
  - `test_parse_det_json`: linha `#DET {...}` válida → `("det", dict)` com `boxes[0]["label"] == "caneca"`.
  - `test_parse_frame_truncado_vira_log`: base64 cortado ou bytes sem SOI/EOI → `("log", ...)` (Review Focus 2).
  - `test_parse_det_json_quebrado_vira_log`: `#DET {"boxes":[` → `("log", ...)`.
  - `test_parse_lixo_do_boot`: `"ets Jun  8 2016 00:22:57"` → `("log", ...)`.
  - `test_scale_box_squash`: box `x=48,y=48,w=8,h=8` com quadro 320×240 → `x=160, y=120, w≈26.7, h=20` (Review Focus 1).
  - `test_http_frame_503_sem_frame` e `test_http_det_devolve_estado`: handler respondendo como em `test_collector_ui.py`.
- [ ] **Step 4:** `.venv\Scripts\python -m pytest tests -v`. Esperado: FAIL (`ModuleNotFoundError: viewer`).
- [ ] **Step 5:** Implementar `viewer.py`. Thread de leitura serial alimenta o estado protegido por lock. A página faz polling de `/frame` e `/det` e desenha no `<canvas>` um círculo por centróide com rótulo e confiança, mais latência e um selo "sem sinal" quando a serial para. Padrão de servidor igual ao `collector_ui.py`.
- [ ] **Step 6:** pytest. Esperado: 14 anteriores + 8 novos passando.
- [ ] **Step 7:** Adaptar o `.ino`:
  1. `#define CAMERA_MODEL_AI_THINKER` (os outros comentados).
  2. `Serial.begin(460800)`.
  3. Trocar o crop+interpolate por **resize squash** do quadro inteiro para 96×96. Usar o resize da própria SDK (`ei::image::processing`); conferir o nome exato no header da lib exportada (Review Focus 1).
  4. Antes de `esp_camera_fb_return`, emitir `#FRAME` com o JPEG original (`base64::encode` de `base64.h` do core).
  5. Depois de `run_classifier`, emitir `#DET` com os boxes de `result.bounding_boxes` com `value > 0` e os tempos `result.timing.dsp` / `.classification`.
- [ ] **Step 8:** `arduino-cli compile --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app firmware\esp32_camera --output-dir build`. Esperado: compila e a flash usada fica < 100% da partição.
- [ ] **Step 9 (Ricardo):** jumper IO0↔GND + RST. `arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app --input-dir build`. Esperado: `Hash of data verified`.
- [ ] **Step 10 (Ricardo):** **tirar o jumper** + RST (Review Focus 4). `python viewer.py --port COM3`, abrir `http://localhost:8001`. Esperado: imagem da câmera atualizando a cada ~3 s e círculo com rótulo ao mostrar um objeto. `Failed to allocate` → refazer com export int8 (Review Focus 3) e ledgerar.
- [ ] **Step 11:** Screenshot do viewer em `docs/img/08-viewer.png`. Commit `feat: firmware de inferência offline e visualizador serial`.

### Task 6: Validação ao vivo + vídeo

**Files:**
- Create: `docs/resultados.md`
- Create: `docs/serial-log.txt`

- [ ] **Step 1 — Cena de treino** (mesmo lugar, luz natural, ~11h–14h, objeto na mão como na coleta): 10 tentativas por classe + 5 de `misto` + 5 de `vazio`. Registrar acerto, rótulo e confiança em `docs/resultados.md`. Meta: ≥ 8/10 por classe e 0 detecções falsas no `vazio`.
- [ ] **Step 2 — Fora da cena, sem meta** (Review Focus 5): 5 tentativas por classe com lâmpada acesa, sobre a mesa e sem a mão. Registrar em `docs/resultados.md`, numa seção "Fora da distribuição". Esse é o dado que embasa a seção de limitações.
- [ ] **Step 3 — Vídeo (2–4 min, Ricardo):**
  - Take único no celular enquadrando a placa, os objetos e a tela do viewer ao mesmo tempo. Sem corte: é o que dá credibilidade.
  - Backup em alta qualidade: gravação da tela via OBS.
  - Roteiro: hardware (5 s), cada classe, `misto`, `vazio`, fechamento mostrando a latência.
  - Upload conforme D6.
- [ ] **Step 4:** Salvar ~1 min de serial em `docs/serial-log.txt`, só as linhas de log e `#DET`, sem `#FRAME`. Commit `docs: resultados da validação ao vivo`.

### Task 7: Pacote de entrega + repositório

**Files:**
- Create: `release/fiap-esp32cam-fomo-merged.bin` (imagem única, gravável em 0x0)
- Create: `docs/gravar-na-sua-placa.md`
- Modify: `README.md` (vira o relatório)
- Create: `docs/img/09-ligacao.png` (export do diagrama de `docs/wiring/ligacao-esp32cam.html`)

- [ ] **Step 1:** Gerar o merged bin com `esptool merge-bin` a partir de `build/`: bootloader em 0x1000, partitions em 0x8000, `boot_app0` em 0xe000 e app em 0x10000. **Verificação:** gravar esse arquivo único em 0x0 na placa do Ricardo e confirmar no viewer que roda igual. Só assim fica provado que o pacote funciona para o professor.
- [ ] **Step 2:** `docs/gravar-na-sua-placa.md`, com duas rotas:
  - (a) Navegador: https://espressif.github.io/esptool-js/ (Chrome, offset 0x0).
  - (b) `esptool write-flash 0x0 release/...bin`.
  - Também: jumper IO0, rodar o `viewer.py` ou o Serial Monitor a 460800, e o requisito de placa AI-Thinker com PSRAM.
- [ ] **Step 3:** README-relatório:
  - Objetivo e enunciado.
  - Hardware e ligação.
  - Pipeline: coleta com preview → boxes manuais → treino.
  - Iterações com prints: grayscale 0.56 → RGB int8 0.74 → RGB float32 0.805 / teste 0.85, com o diagnóstico de cada uma.
  - Decisões: FOMO × classificação; float32 × int8 (precisão × latência × RAM).
  - Firmware e protocolo serial; resultados ao vivo; vídeo.
  - **Limitações** (domain shift, mão, luz, foco da lente) e o que faria para generalizar.
  - Como reproduzir.
- [ ] **Step 4:** Conferir que nenhum segredo vai pro repo: `git ls-files` sem `.env`/`backup`, e grep por `ei_` / SSID no tree. Commit `docs: relatório do trabalho e pacote de gravação`.
- [ ] **Step 5 (D5, confirmar com Ricardo antes):** `gh repo create` com a visibilidade escolhida, `git push -u origin main`. Edge Impulse: *Make public* (D7) e link no README.
- [ ] **Step 6 (opcional, depois da entrega):** restaurar o VisionGuard com `esptool write-flash 0 backup\visionguard-flash.bin`.
