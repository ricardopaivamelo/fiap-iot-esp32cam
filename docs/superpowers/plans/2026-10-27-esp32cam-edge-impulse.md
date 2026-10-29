# ESP32-CAM + Edge Impulse — Detecção de Objetos FOMO (FIAP IoT) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Treinar no Edge Impulse um detector FOMO com dados capturados pelo próprio ESP32-CAM, rodar a inferência embarcada na placa (offline, sem WiFi), provar o funcionamento com vídeo e entregar um repositório que documenta o processo inteiro e permite ao professor gravar o modelo na placa dele.

**Architecture:** Coleta v1 via firmware VisionGuard (`GET /capture`) + `collector_ui.py`; coleta v2 pelo próprio firmware de inferência (quadros `#FRAME` da serial) + `viewer.py`. Treino e export no Studio. O firmware emite pela serial o JPEG do quadro e as detecções em JSON; o `viewer.py` (stdlib + pyserial) desenha os centróides no navegador. A demo funciona em qualquer lugar só com o cabo USB.

**Tech Stack:** Edge Impulse Studio + `edge-impulse-uploader`, Python 3.11 (venv), `requests`, `pyserial`, `pytest`, `arduino-cli` + core `esp32:esp32@2.0.17`, `esptool` 5.6.0.

**Spec:** Enunciado FIAP IoT (verbatim):

> Usando a plataforma Edge Impulse, utilizar uma das duas trilhas de treinamento: Áudio / **Imagem**. Realize o treinamento de um modelo. O modelo será exportado para ESP32 e implantado em: ESP32 com microfone INMP441 (para inferência de áudio), ou **ESP32CAM (para inferência de classificação de objeto)**.

Contexto (Ricardo, 2026-10-27): o professor provavelmente vai testar o modelo **na ESP32-CAM dele, em sala**, com os objetos treinados.

Registro detalhado do que já foi feito: `docs/processo.md`. Retomada de sessão: `HANDOFF.md`.

## Status (2026-10-28)

- Tasks 1–5 concluídas. Modelo **v1** na placa: RGB 96×96, FOMO MobileNetV2 0.35, 100 epochs, **int8** — F1 teste **0,89**; inferência 741 ms, ciclo ~0,88 s. As 3 classes detectadas ao vivo.
- Otimização de latência encerrada: arena de 154 KB não cabe na RAM interna (maior bloco 110 KB); ~1,1 quadro/s aceito (Ricardo).
- **Novo problema:** o dataset v1 tem a mão em todas as fotos de objeto → viés. **Decisão (Ricardo, 2026-10-28):** recoletar com os objetos apoiados na mesa e retreinar (Task 6). Isso substitui a decisão anterior de "não retreinar".
- **2026-10-29:** Task 6 Steps 1–8 concluídos — dataset v2 (285 amostras), modelo v2 int8 com **F1 teste 0,92**. Falta o Step 9 (export, gravação, comparação ao vivo).
- **2026-10-29:** Task 6 concluída — v2 gravado na placa (740 ms, igual ao v1), teste ao vivo OK, Version `v2` no EI. Prints 09–11 salvos. Próximo: Task 7.

## Global Constraints

- Trilha: **Imagem → detecção de objetos com FOMO**. Classes: `garrafa`, `caderno`, `caneca`. Fotos vazias sem box (classe implícita `background`).
- Plataforma de treino: **Edge Impulse** (obrigatório). Projeto `fiap-iot-esp32cam` (id 1149980).
- Alvo: **ESP32-CAM** clone AI-Thinker (ESP32-D0WD-V3, ~4 MB PSRAM, OV2640), FTDI FT232R na **COM3**.
- Export: **Arduino library, Quantized (int8)**, EON ligado. float32 descartado (4,9 s/inferência e F1 de teste menor).
- Impulse: 96×96, **Squash**, RGB, FOMO MobileNetV2 0.35. O firmware faz o mesmo squash (sem crop central).
- Firmware **offline**, saída só pela serial a **460800 baud**; `ei_printf` redirecionado ao `Serial` (não reverter: com o buffer de TX, `printf` mistura as linhas).
- Build: `esp32:esp32:esp32cam:PartitionScheme=huge_app`, core `esp32:esp32@2.0.17`, `build_opt.h` com `-DEI_MAX_OVERFLOW_BUFFER_COUNT=200`.
- Gravação: jumper IO0↔GND + RST para gravar; tirar o jumper + RST para rodar. O `viewer.py` ocupa a COM3: parar antes de gravar.
- Projeto em `C:\Users\ricar\dev\fiap-iot-esp32cam\`. **Nunca** commitar na home-repo. Fora do git: `.env`, `backup/` (senha WiFi), `dataset*/`, `build*/`, `*.zip`, vídeos.
- Commits em PT-BR, formato convencional.

## Decisões em aberto

- **D2 — Entregável:** default = repositório GitHub com README-relatório + prints + link do vídeo + `.bin` para gravar. Mensagem ao professor pendente (inclui: objetos na mão ou na mesa? mesmos objetos ou parecidos? modelo da placa dele?).
- **D4 — Prazo** da entrega.
- **D5 — Visibilidade do repo:** default **público**.
- **D6 — Vídeo:** default YouTube **não listado**, link no README.
- **D7 — Dataset no repo:** default **não**; projeto Edge Impulse público.
- **D8 — Dataset v2:** default = **substituir** o v1 (desativar as amostras v1 no Studio, sem apagar) depois de salvar uma *Version* do projeto v1. Alternativa: somar v1 + v2 (mais dados, mas mantém o viés da mão).
- **D9 — Método da recoleta:** default = **pelo `viewer.py`** com o firmware de inferência (Task 6 Steps 1–4). Alternativa: regravar o VisionGuard e usar `collector_ui.py` (fluxo já provado, fotos 640×480, mas exige WiFi e duas regravações).

## Review Focus

1. **Pré-processamento diferente do treino** → coberto (squash no firmware + `test_scale_box_squash`).
2. **Linha de serial corrompida** → coberto (testes de parse); atenção a qualquer novo `printf` fora do `Serial`.
3. **Viés de coleta** (mão, um único fundo, uma única luz) → métrica de teste alta e modelo ruim fora da cena. Task 6 ataca a mão; Task 7 mede fora da cena.
4. **IO0 ainda jumpeado após gravar** → placa parada em `waiting for download`.
5. **Resolução da coleta v2 (320×240) diferente da v1 (640×480)** → irrelevante para o modelo (tudo vira 96×96), mas não misturar as duas sem decidir D8.

---

### Task 1: Setup do projeto + backup do firmware atual — ✅ concluída
### Task 2: Coleta v1 (`collect.py` + `collector_ui.py`) — ✅ concluída
### Task 3: Projeto no Edge Impulse + upload + boxes manuais — ✅ concluída
### Task 4: Impulse + treino — ✅ concluída (prints `docs/img/03`–`08`)
### Task 5: Firmware de inferência + visualizador — ✅ concluída (int8 na placa; otimização encerrada)

Pendente desta task: screenshot do viewer → feito na Task 7 com o modelo final.

### Task 6: Recoleta sem a mão + retreino (v2)

**Files:**
- Modify: `viewer.py` (rota de gravação de quadro)
- Test: `tests/test_viewer.py`
- Create (fora do git): `dataset-v2/<cena>/<cena>_NNNN.jpg`

**Interfaces:**
- Consumes: `collect.save_frame(frame: bytes, label: str, out_dir: Path) -> Path` e `collect.next_index`.
- Produces: `POST /save?scene=<cena>` no viewer → grava o último `#FRAME` recebido em `dataset-v2/<cena>/`; responde `{"saved": "<caminho>", "stats": {cena: n}}`; 503 sem quadro; 400 para cena fora de `garrafa|caderno|caneca|misto|vazio`. CLI: `--out dataset-v2`.

- [x] **Step 1: Testes que falham** em `tests/test_viewer.py`:
  - `test_http_save_grava_ultimo_frame`: com um `#FRAME` recebido, `POST /save?scene=caneca` cria `caneca_0000.jpg` com os mesmos bytes e devolve `stats["caneca"] == 1`.
  - `test_http_save_503_sem_frame` e `test_http_save_cena_invalida_400`.
- [x] **Step 2:** pytest → FAIL. **Step 3:** implementar (reusar `save_frame`; botões por cena e contadores na página). **Step 4:** pytest → 30 passando. Commit `feat: gravar quadros da serial no viewer para a coleta v2`. *(Feito com `seq` + 409, `ee8afb7`; depois: botões fixos `95a7519` e quadro gravado uma só vez `532ee14` — 34 testes.)*
- [x] **Step 5 (Ricardo, antes de coletar):** Studio → Dashboard → **Versioning → criar versão "v1-mao"** (preserva o resultado 0,89 para o relatório). *(Version 1, 2026-10-28.)*
- [x] **Step 6 — Coleta (Ricardo).** *(289 fotos únicas 320×240 após remover 128 cópias; detalhes em `docs/processo.md`, Etapa 8.)* Objetos **apoiados na mesa, sem a mão no quadro**; mesma mesa/luz em que a demo e o vídeo vão acontecer. Variar posição no quadro (centro, bordas, cantos), distância (perto/longe), rotação do objeto e posição da câmera. Metas:

  | Cena | Fotos | Observação |
  |---|---|---|
  | garrafa / caderno / caneca | ~60 cada | caderno aberto e fechado |
  | misto | ~40 | 2 e 3 objetos, às vezes encostados |
  | vazio | ~30 | mesa vazia, inclusive com outros objetos que **não** são classe (estojo, celular) |

- [x] **Step 7:** upload `edge-impulse-uploader --category split` (via `%APPDATA%\npm\edge-impulse-uploader.cmd`) aplicando D8. Boxes manuais (Ricardo). Conferência pela API (`tools/check_labels.py`, rodado da raiz do projeto): 0 objetos sem box, 0 boxes `vazio`. *(285 ativas, 227/58; boxes caneca 123 / caderno 108 / garrafa 104; 0 sem box. Ruling (Ricardo): boxes assistidas — sugestões YOLOv5 revisadas + marcação via API com revisão visual; mão sempre fora da box. Folhas em `docs/img/rotulagem-v2/`.)*
- [x] **Step 8:** retreinar com o mesmo impulse (RGB, 100 epochs, LR 0.001, augmentation). **Model testing int8.** Critério para substituir o v1: F1 teste ≥ 0,80 **e** melhora visível ao vivo sem a mão. Se não atingir, manter o v1 e registrar a comparação. *(Validação int8 0,94; **teste int8 0,92** (P 0,90 / R 0,95), float32 0,95. Falta a parte "melhora ao vivo" → Step 9.)*
- [x] **Step 9:** export int8 → instalar a lib → compilar → gravar → conferir no viewer. Prints `docs/img/09-dataset-v2.png`, `10-treino-v2.png`, `11-model-testing-v2.png` (Ricardo, no Studio). ~~Atualizar `docs/processo.md` (Etapa 8)~~ *(feito)*. Comparar ao vivo com o v1 e registrar. Criar Version `v2` no EI. *(2026-10-29: lib 1.0.3 exportada pela API, build 483937 B, gravado; na placa NN 740 ms / ciclo 876 ms, igual ao v1; teste ao vivo bem-sucedido segundo o Ricardo, sem números por cena (viewer não grava histórico) → números ficam para a Task 7; Version 2 `v2` criada. Prints 09, 10 (int8), 10b (float32) e 11 salvos; teste A/B v1×v2 com prints em `docs/img/ao-vivo/`.)*

### Task 7: Validação ao vivo + vídeo

**Files:** Create `docs/resultados.md`, `docs/serial-log.txt`, `docs/img/12-viewer.png`.

- [x] **Step 1 — Cena de treino** (mesa da coleta v2): 10 tentativas por classe + 5 `misto` + 5 `vazio`. Registrar acerto, rótulo, confiança. Meta: ≥ 8/10 por classe e 0 falsos positivos no `vazio`. *(2026-10-29: garrafa, caderno, caneca e vazio 10/10; misto trios 7/8 e pares 9/9 por classe; erros garrafa→caneca em `misto_0008`/`0013`. Tentativas em `validacao/`, avaliadas por `tools/resultados_validacao.py`.)*
- [~] **Step 2 — Fora da cena, sem meta:** *(não feito, decisão do Ricardo em 2026-10-29; limitações vêm dos erros do Step 1 e do A/B v1×v2.)* 5 tentativas por classe com outra luz/fundo e com o objeto na mão. Seção "Fora da distribuição" — base da seção de limitações.
- [~] **Step 3 — Vídeo (2–4 min, Ricardo):** *(dispensado pelo Ricardo em 2026-10-29: sem vídeo, D6 encerrada.)* take único no celular com placa, objetos e tela do viewer; backup via OBS. Roteiro: hardware → cada classe → `misto` → `vazio` → tempos. Upload conforme D6.
- [x] **Step 4:** *(2026-10-29: `docs/serial-log.txt` = 05:37, `docs/img/12-viewer.png`, `docs/resultados.md` com tempos de 2.351 ciclos e as 57 tentativas.)* ~1 min de serial sem `#FRAME` em `docs/serial-log.txt`; screenshot do viewer. Commit `docs: resultados da validação ao vivo`.

### Task 8: Pacote de entrega + repositório

**Files:** `release/fiap-esp32cam-fomo-merged.bin`, `docs/gravar-na-sua-placa.md`, `README.md` (relatório), `docs/img/13-ligacao.png`.

- [~] **Step 1:** *(2026-10-29: `release/fiap-esp32cam-fomo-v2-merged.bin` gerado de `build-v2/`, 549840 B, sha256 `100af373…`; **falta gravar em 0x0 na placa e conferir no viewer**.)* `esptool merge-bin` a partir de `build/`: bootloader 0x1000, partitions 0x8000, `boot_app0` 0xe000, app 0x10000. **Verificação:** gravar o arquivo único em 0x0 na placa do Ricardo e confirmar no viewer.
- [x] **Step 2:** `docs/gravar-na-sua-placa.md`: (a) esptool-js no Chrome, offset 0x0; (b) `esptool write-flash 0x0 …`; jumper IO0; viewer ou Serial Monitor a 460800; requisito AI-Thinker com PSRAM.
- [x] **Step 3:** README-relatório a partir de `docs/processo.md` + `docs/resultados.md`: objetivo, hardware, pipeline, iterações com prints, decisões, firmware/protocolo, resultados, vídeo, **limitações**, como reproduzir.
- [x] **Step 4:** *(2026-10-29: chave do `.env` ausente dos arquivos, do histórico e do `.bin`; nenhum `ei_<hex>` no histórico; sem `.env`/`backup` rastreados; no `.bin` só nomes de erro da SDK.)* checagem de segredos: `git ls-files` sem `.env`/`backup`; grep por `ei_` (chave) e SSID. Commit `docs: relatório do trabalho e pacote de gravação`.
- [ ] **Step 5 (confirmar D5 antes):** `gh repo create`, `git push -u origin main`; Edge Impulse *Make public* (D7).
- [ ] **Step 6 (opcional):** restaurar o VisionGuard: `esptool write-flash 0 backup\visionguard-flash.bin`.
