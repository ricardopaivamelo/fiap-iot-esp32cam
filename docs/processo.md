# Registro do processo — Detecção de objetos FOMO no ESP32-CAM (FIAP IoT)

Base do relatório final. Cada etapa registra **o que** foi feito, **como**, **por quê** e o
**resultado**, com a evidência correspondente (prints em `docs/img/`, commits, logs).
Ordem cronológica; as decisões que mudaram o rumo estão marcadas com **Decisão**.

> Enunciado: *Usando a plataforma Edge Impulse, utilizar uma das duas trilhas de treinamento:
> Áudio / Imagem. Realize o treinamento de um modelo. O modelo será exportado para ESP32 e
> implantado em: ESP32 com microfone INMP441 (para inferência de áudio), ou ESP32CAM (para
> inferência de classificação de objeto).*

---

## Resumo

| Item | Valor |
|---|---|
| Trilha | Imagem — **detecção de objetos (FOMO)** |
| Classes | `garrafa`, `caderno`, `caneca` (+ `background` implícito) |
| Dataset v1 | 201 fotos 640×480 tiradas pelo próprio ESP32-CAM; 165 treino / 36 teste |
| Modelo | RGB 96×96 (squash) → FOMO MobileNetV2 0.35, 100 epochs, LR 0.001, **int8** |
| Qualidade (teste) | **F1 0,89** (precisão 0,87 / recall 0,91) |
| Na placa | inferência **741 ms**, DSP 9 ms, captura 111 ms, ciclo **~0,88 s** (~1,1 quadro/s) |
| Implantação | firmware offline (sem WiFi); quadro + detecções pela serial → `viewer.py` no navegador |

---

## Etapa 0 — Hardware e ambiente

**O que.** Preparar a placa, as ferramentas e um backup do firmware que já estava nela.

**Como.**
- ESP32-CAM clone AI-Thinker (ESP32-D0WD-V3, OV2640, ~4 MB de PSRAM) + adaptador USB-serial
  FT232R na COM3 (TX→U0R, RX→U0T, 5V, GND). Diagrama: `docs/wiring/ligacao-esp32cam.html`.
- Modo de gravação: jumper **IO0↔GND** + RST. Modo de execução: tirar o jumper + RST.
  (A placa não tem auto-reset: o nível de IO0 no reset decide entre gravar e rodar.)
- `arduino-cli` com o core `esp32:esp32@2.0.17`; `esptool` 5.6.0; `edge-impulse-cli` 1.40.0;
  Python 3.11 em venv (`requests`, `pyserial`, `pytest`).
- Backup integral da flash (4 MB) com `esptool read-flash` → `backup/visionguard-flash.bin`
  (fora do git: contém a senha do WiFi).

**Por quê.** A placa rodava o projeto VisionGuard, cujo endpoint `/capture` seria usado na coleta;
o backup permite restaurá-lo ao fim do trabalho.

**Problema resolvido.** O `edge-impulse-cli` falha ao compilar o módulo nativo `@serialport` no
Node 24; instalado com `--ignore-scripts`, já que o `edge-impulse-uploader` só usa HTTP.

**Evidência.** commit `7f8c84e`.

---

## Etapa 1 — Escolha da trilha e da tarefa

**Decisão 1 — trilha Imagem.** Já havia ESP32-CAM disponível; o INMP441 não.

**Decisão 2 — detecção de objetos (FOMO) em vez de classificação.** O professor exigiu marcação
manual de *bounding boxes*, o que só existe em detecção. O FOMO (*Faster Objects, More Objects*)
é o detector do Edge Impulse feito para microcontroladores: em vez de caixas, ele prevê o
**centróide** de cada objeto numa grade de 12×12 células sobre a entrada 96×96, o que o deixa
leve o bastante para o ESP32.

**Classes.** `garrafa`, `caderno`, `caneca` — objetos de tamanhos, formas e cores diferentes.
Duas cenas extras sem classe própria: `misto` (vários objetos na mesma foto) e `vazio`
(só o fundo, para o modelo aprender o que **não** é objeto).

---

## Etapa 2 — Coleta do dataset

**O que.** Fotografar os objetos **com a própria câmera da placa**.

**Como.**
- O firmware VisionGuard expõe `GET /capture` (JPEG 640×480) pelo WiFi.
- `collect.py`: cliente CLI que baixa quadros, valida o JPEG (marcadores SOI/EOI), numera
  sem sobrescrever (`<cena>_NNNN.jpg`) e desiste após 10 falhas seguidas.
- `collector_ui.py`: tela local (http://localhost:8000) com **preview ao vivo** e um botão por
  cena; o botão grava **exatamente o quadro exibido** ("o que você vê é o que entra no dataset").
- 14 testes automatizados (`tests/test_collect.py`, `tests/test_collector_ui.py`).

**Por quê.** Treinar com imagens do mesmo sensor, lente e compressão JPEG que farão a inferência
elimina a diferença de domínio entre câmera de celular e OV2640.

**Resultado.** 201 fotos: garrafa 50, caderno 50, caneca 50, misto 31, vazio 20.
Os objetos foram fotografados **segurados na mão**, em várias posições e distâncias.

**Evidência.** commits `05f7820`, `9cb1063`.

---

## Etapa 3 — Upload e rotulagem no Edge Impulse

**Como.**
- Projeto `fiap-iot-esp32cam` (id 1149980). Upload com
  `edge-impulse-uploader --category split` → divisão automática **165 treino / 36 teste (82/18)**.
- **Bounding boxes desenhadas manualmente** no *Labeling queue*: garrafa 75, caderno 71,
  caneca 70 objetos.
- Conferência pela API do Edge Impulse (script que lista todas as amostras e suas boxes):
  0 objetos sem box e **1 box espúria** com rótulo `vazio` em `testing/vazio_0017`, removida.

**Por quê da conferência.** Um rótulo errado no conjunto de teste distorce a métrica final; a
checagem automática é mais confiável que revisar 201 fotos no olho.

**Evidência.** `docs/img/01-labeling.png`, `docs/img/02-dataset.png`.

---

## Etapa 4 — Impulse e treino (3 iterações)

**Impulse.** Entrada 96×96, redimensionamento **Squash** (a foto inteira é comprimida, sem
cortar bordas — objetos perto da borda não somem), bloco *Image*, FOMO MobileNetV2 0.35.

| # | Configuração | F1 validação | Diagnóstico / ação |
|---|---|---|---|
| 1 | Grayscale, 60 epochs | **0,559** — caderno 0% | Caderno e capa da garrafa são manchas escuras sem textura; em tons de cinza o centro do objeto fica indistinguível do fundo. → usar cor. |
| 2a | **RGB**, 100 epochs, augmentation, int8 | 0,74 | Cor separa as classes (preto × verde-petróleo × estampa amarela). Recall (0,69) ainda baixo. |
| 2b | RGB, 100 epochs, float32 | 0,805 | Mesma rede sem quantização. |

**Model testing (conjunto de teste, nunca visto no treino):**

| Variante | F1 | Precisão | Recall |
|---|---|---|---|
| float32 | 0,85 | 0,78 | 0,93 |
| **int8** | **0,89** | 0,87 | 0,91 |

**Leitura.** A validação tem só ~33 imagens, então ±1 acerto muda vários pontos; ela indicava o
float32 como melhor, mas o teste mostrou o int8 igual ou superior. Por isso a escolha final
usa o resultado do **teste**.

**Evidência.** `docs/img/03-features-grayscale.png` (feature explorer, classes sobrepostas),
`04-treino1-grayscale-int8.png`, `05-treino2-rgb-int8.png`, `06-treino2-rgb-float32.png`,
`07-model-testing-float32.png`, `08-model-testing-int8.png`.

---

## Etapa 5 — Firmware de inferência e visualizador

**O que.** Rodar o modelo exportado (Arduino library) na placa e mostrar o resultado ao vivo.

**Como — firmware** (`firmware/esp32_camera/esp32_camera.ino`, a partir do exemplo
`esp32_camera` da biblioteca; mudanças marcadas com `FIAP`):
1. Pinagem `CAMERA_MODEL_AI_THINKER`; serial a **460800 baud**.
2. **Squash** do quadro QVGA inteiro para 96×96 (`ei::image::processing::resize_image`), no
   lugar do *crop* central do exemplo — o pré-processamento na placa precisa ser **idêntico**
   ao do treino, senão as posições e as confianças mudam.
3. A cada ciclo, emite pela serial `#FRAME <JPEG em base64>` e
   `#DET {"dsp","nn","cap","loop","boxes":[{label,conf,x,y,w,h}]}`.
4. Correção de um vazamento de memória do exemplo oficial (`snapshot_buf` não era liberado
   no caminho de erro do classificador).
5. **Offline**: nenhum uso de WiFi — funciona em qualquer lugar só com o cabo USB, inclusive
   numa placa de terceiros.

**Como — visualizador** (`viewer.py`, stdlib + pyserial): lê a serial, decodifica os quadros e
as detecções e serve http://localhost:8001, que desenha o centróide de cada objeto com rótulo,
confiança e os tempos de cada etapa. Linhas corrompidas (base64 cortado, JSON incompleto, lixo
do boot) viram log e não derrubam o programa. 13 testes (`tests/test_viewer.py`); suíte total 27.

**Problema 1 — limite de buffers.** O float32 abortava com
`Failed to allocate persistent buffer ... EI_MAX_OVERFLOW_BUFFER_COUNT` (limite 10).
Corrigido com `build_opt.h` (`-DEI_MAX_OVERFLOW_BUFFER_COUNT=200`). Commit `0d25943`.

**Problema 2 — latência.** Medido na placa:

| Variante | Arena | Inferência | Ciclo |
|---|---|---|---|
| float32 | 555 KB | **4939 ms** (Studio estimava 2726 ms) | ~5 s |
| **int8** | 155 KB | **741 ms** | ~0,88 s |

**Decisão 3 — int8.** Melhor F1 de teste (0,89 × 0,85) **e** 6,7× mais rápido. O float32 seria
melhor só se precisão superasse latência, e aqui não supera em nenhum dos dois.

**Resultado.** As três classes foram detectadas ao vivo na placa.

**Evidência.** commits `d5b4224`, `0d25943`; logs em `.superpowers/sdd/…` (locais).

---

## Etapa 6 — Tentativa de otimização (medida, sem ganho)

**Hipótese.** O core Arduino manda para a PSRAM (memória externa via SPI, lenta) toda alocação
acima de 4 KB (`CONFIG_SPIRAM_MALLOC_ALWAYSINTERNAL=4096`). Colocar a arena de 154 KB na RAM
interna poderia acelerar a inferência.

**Como.** Override das funções `ei_malloc`/`ei_calloc` (declaradas *weak* pela SDK) tentando a
RAM interna primeiro, log do heap no boot e buffer de TX da serial de 8 KB (para enviar o quadro
em paralelo à inferência).

**Resultado medido no boot:**
```
Heap interno livre: 289160 B (maior bloco 110580 B) | PSRAM livre: 4168539 B
[alloc] 153937 B -> PSRAM
#DET {"dsp":9,"nn":741,"cap":111,"loop":878,"boxes":[]}
```
Há 289 KB livres, mas o **maior bloco contíguo é 110 KB** — a RAM interna do ESP32 é dividida em
regiões físicas e nenhuma comporta 154 KB. Com entrada 96×96 a arena fica obrigatoriamente na
PSRAM: **é o limite do hardware**. O buffer de TX também não trouxe ganho mensurável.

**Efeito colateral corrigido.** Com a serial assíncrona, os `printf` da SDK (que escrevem direto
na UART) passaram a se misturar às linhas `#DET`. Corrigido redirecionando `ei_printf` para o
mesmo `Serial`. O override de memória foi removido (sem efeito).

**Decisão 4 — aceitar ~1,1 quadro/s.** A única alavanca restante relevante seria retreinar com
entrada 64×64 (arena caberia na RAM interna), com risco de perder precisão. Para a demonstração,
precisão importa mais que fluidez.

---

## Etapa 7 — Observação ao vivo: a mão como viés do dataset

**Observação (Ricardo).** Nos testes ao vivo, **a mão atrapalha**: como todas as fotos de objeto
foram tiradas com o objeto segurado, a mão aparece em quase todo exemplo positivo e nunca nos
negativos (`vazio`). O modelo pode ter aprendido "mão/braço" como parte do objeto — é um *viés de
coleta* (atalho / *shortcut learning*): a métrica de teste é alta porque o conjunto de teste tem o
mesmo viés.

**Decisão 5 — recoletar com os objetos apoiados na mesa**, sem a mão, e retreinar. Ver
`docs/superpowers/plans/2026-10-27-esp32cam-edge-impulse.md` (Task 6).

---

## Próximas etapas (resumo; detalhes no plano)

1. Recoleta sem mão, rotulagem e retreino (v2), comparando com a v1.
2. Validação ao vivo com roteiro fixo e registro em `docs/resultados.md`.
3. Vídeo da placa funcionando (take único).
4. Pacote de entrega: `.bin` único gravável na placa do professor, guia de gravação, README-relatório.
