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
| Dataset v1 | 201 fotos 640×480 tiradas pelo próprio ESP32-CAM; 165 treino / 36 teste (objeto na mão) |
| Dataset v2 | 285 fotos 320×240 do quadro de inferência; 227 treino / 58 teste (mão fora das boxes) |
| Modelo | RGB 96×96 (squash) → FOMO MobileNetV2 0.35, 100 epochs, LR 0.001, **int8** |
| Qualidade (teste) | v1 **F1 0,89** (P 0,87 / R 0,91) → v2 **F1 0,92** (P 0,90 / R 0,95) |
| Na placa | **v2** gravado: inferência **740 ms**, DSP 9 ms, captura 110 ms, ciclo **~0,88 s** (~1,1 quadro/s), igual ao v1 |
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

## Etapa 8 — Dataset v2 (sem a mão no objeto), rotulagem e retreino

**Preservação do v1 (Decisão 8).** Antes de mexer no projeto, o estado v1 foi congelado no Edge Impulse
como **Version 1 `v1-mao`** (dados, boxes, impulse e modelo, F1 0,89). As 201 amostras v1 foram
**desativadas** (não apagadas) via API — o v2 substitui o v1 em vez de somar, porque misturar manteria
o atalho "mão = objeto".

**Coleta pelo visualizador (Decisão 9).** Em vez de regravar o firmware VisionGuard (WiFi), a coleta
usou o próprio firmware de inferência: o `viewer.py` ganhou `POST /save?scene=&seq=`, que grava em
`dataset-v2/<cena>/` exatamente o quadro exibido (teclas 1–5). Consequência deliberada: as fotos v2 são
**320×240 (QVGA)**, a mesma câmera, resolução e compressão JPEG que o modelo vê na inferência — o v1
treinava em 640×480 e inferia em 320×240 (*domain shift*). Para o modelo não há perda: tudo é reduzido
a 96×96.

**Problemas encontrados na coleta e correções.**
| Problema | Causa | Correção |
|---|---|---|
| Cliques gravando na cena errada | a lista de detecções acima dos botões mudava de altura a cada quadro e deslocava os botões (*layout shift*) | botões fixos no topo; detecções movidas para baixo da câmera (`95a7519`) |
| 128 de 328 fotos eram **cópias idênticas** | tecla repetida antes do próximo quadro (~0,9 s) gravava o mesmo quadro de novo | `/save` passou a consumir o quadro (409 na repetição), com teste (`532ee14`); cópias apagadas no EI e retiradas do dataset local (risco evitado: a mesma foto em treino e teste infla o F1) |
| Upload de 100 arquivos falhando sem mensagem | limite de 8191 caracteres da linha de comando do `cmd.exe` | upload em lotes de 30 com caminhos relativos |
| Fotos movidas de pasta na revisão mantinham o nome antigo | revisão manual no Explorer | renomeadas no EI como `v2-<pasta>_movida-<nome>` |

**Dataset v2 final.** 289 fotos únicas coletadas; 285 ativas no EI após a revisão (**227 treino / 58
teste**, split automático 80/20): caderno 60, caneca 63, garrafa 62, misto 60, vazio 40 (inclui fotos da
**mão vazia**, sem objeto — exemplos negativos difíceis contra o viés).

**A mão voltou em parte das fotos.** Na rotulagem descobriu-se que o caderno (que não para em pé) e
algumas fotos de garrafa/caneca foram fotografados **segurados**. Decisão (Ricardo): manter, com a
regra **mão sempre fora da box**. Justificativa técnica: no FOMO o rótulo é por célula da grade 12×12;
toda célula fora de uma box é treinada como *background*, então a mão fora da box vira exemplo de "isto
não é objeto" — o oposto do viés do v1. Amostras em que a mão **cobre** o objeto (impossível marcar sem
ela) foram desativadas: caderno 0102/0103, garrafa 0036/0037.

**Rotulagem (boxes).**
- Ricardo marcou parte dos mistos e cadernos no Studio com **sugestões do YOLOv5** (pré-treinado no
  COCO), revisando cada box. Os labels COCO sugeridos (`vase`, `cup`, `bottle`, `tv`, `mobile phone`,
  `refrigerator`, `clock`, `cell phone`) foram corrigidos em lote pela API para as 3 classes (12 boxes).
- As demais (todos os cadernos, canecas e garrafas sem box e 19 mistos) foram marcadas **pela API**
  (`POST /raw-data/{id}/bounding-boxes`, mesmo formato que o Studio grava), com revisão visual de cada
  foto por agentes de IA e conferência final por folhas de contato; o EI registra a autoria de cada box
  (`lastUpdatedBy`: `user` × `projectApiKey`).
- Conferência (`tools/check_labels.py`): **caneca 123, caderno 108, garrafa 104 boxes; 0 objetos sem
  box; 0 boxes `vazio`.** Folhas de conferência por cena em `docs/img/rotulagem-v2/`
  (`tools/folhas_rotulagem.py <cena>` regenera a partir do estado do EI).

**Retreino.** Mesmo impulse e mesmos hiperparâmetros do v1 (RGB 96×96 squash, FOMO MobileNetV2 0.35,
100 epochs, LR 0.001, augmentation `all`, validação 20%) — muda só o dataset, para a comparação medir
o efeito dele. Features regeneradas e treino disparados pela API (jobs 55602216 e 55602238, ~6 min).

| Métrica (F1 *non-background*) | v1 int8 | **v2 int8** | v2 float32 |
|---|---|---|---|
| Validação (20% do treino) | — | 0,94 (P 0,92 / R 0,97) | 0,96 (P 0,94 / R 0,98) |
| **Teste — Model testing (58 amostras)** | 0,89 (P 0,87 / R 0,91) | **0,92 (P 0,90 / R 0,95)**, 54/58 corretas | 0,95 (P 0,91 / R 0,98), 55/58 |

Validação int8 por classe: caderno 0,97, caneca 0,96, garrafa 0,88. Critério do plano (F1 teste ≥ 0,80)
atingido. Ressalva: o teste vem da mesma sessão de coleta (mesma mesa/luz/objetos); a prova de que o
viés foi removido é o **teste ao vivo** na placa (Etapa 9).

---

## Etapa 9 — Implantação do v2 e teste ao vivo

**Export e build (pela API).** Biblioteca Arduino **int8, EON** gerada pela API (job 55602965,
`ei-fiap-iot-esp32cam-arduino-1.0.3-int8.zip`: int8, entrada 96×96, 3 labels), instalada no lugar da
1.0.2 (v1) e compilada com o mesmo firmware (`PartitionScheme=huge_app`): **483.937 bytes**.
Gravação na COM3 em 6,3 s, `Hash of data verified`.

**Na placa (viewer, 2026-10-29).**

| | v1 int8 | **v2 int8** |
|---|---|---|
| Inferência (NN) | 741 ms | **740 ms** |
| DSP / captura | 9 / 111 ms | 9 / 110 ms |
| Ciclo | ~0,88 s | **~0,876 s** (~1,1 quadro/s) |

A latência é a mesma porque a arquitetura não mudou (FOMO MobileNetV2 0.35, 96×96): o custo da
inferência depende da arquitetura e não dos pesos. **O ganho de qualidade do v2 não custou desempenho.**
Mesa vazia: 0 boxes nos quadros conferidos.

**Teste ao vivo.** Roteiro: cada objeto sozinho na mesa, os três juntos, mesa vazia e mão vazia na frente
da câmera (o caso que expunha o viés do v1, Etapa 7). Resultado relatado pelo Ricardo: **testes bem-sucedidos**
(≈370 ciclos). Limitação do registro: o viewer mostra só o quadro atual, então esta sessão não gravou
detecções por cena (labels, confiança, contagem). A validação com números e roteiro fixo fica para a
Task 7 (`docs/resultados.md`, `serial-log.txt`, vídeo).

**Prints do viewer** (`docs/img/ao-vivo/`). O modelo de cada print é identificado pelo log: o
firmware v1 imprimia `[alloc] 153937 B -> PSRAM` a cada ciclo; o v2 não imprime.

| Print | Modelo | Cena | Detecções |
|---|---|---|---|
| `v1-caderno-na-mao.png` (28/10) | v1 | caderno segurado na mão | caderno 84% |
| `v1-caneca-garrafa-mesa.png` (28/10, durante a coleta v2) | v1 | caneca + garrafa na mesa | caneca 92%, garrafa 98% |
| `v2-caneca-sobre-caderno.png` (29/10) | v2 | caneca sobre o caderno (sobreposição) | caderno 86%, caneca 87% |
| `v2-caneca-caderno.png` (29/10) | v2 | caneca + caderno | caneca 98%, caderno 97% |
| `v2-garrafa-caderno.png` (29/10) | v2 | garrafa + caderno | garrafa 100%, caderno 100% |

Leitura honesta: o v2 detecta as duas classes de cada par com confiança de 86% a 100%, inclusive
com a caneca apoiada sobre o caderno. Mas o v1 também detectava objetos na mesa (2º print), então
estes prints **não isolam** a melhora do v2. Ela está no caso da mão vazia, que não tem print, e nos
números do Model testing (0,89 → 0,92). Para o relatório, o print da mão vazia (v1 × v2) fica
pendente para a Task 7. Nos prints a captura variou de 157 a 203 ms (ciclo de 924 a 969 ms) com o
navegador aberto, contra 110 ms medidos pela API do viewer; a inferência ficou fixa em 741 ms.

**Decisão:** o v2 substitui o v1 (critérios do plano: F1 teste ≥ 0,80 e melhora ao vivo). O estado foi
congelado no EI como **Version 2 (`v2`)**, ao lado da Version 1 (`v1-mao`), sem publicar o projeto.

---

## Próximas etapas (resumo; detalhes no plano)

1. Prints do Studio para o relatório: `09-dataset-v2`, `10-treino-v2`, `11-model-testing-v2`.
2. Validação ao vivo com roteiro fixo e registro em `docs/resultados.md`.
3. Vídeo da placa funcionando (take único).
4. Pacote de entrega: `.bin` único gravável na placa do professor, guia de gravação, README-relatório.
