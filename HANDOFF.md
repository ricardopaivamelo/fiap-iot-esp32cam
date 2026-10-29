# HANDOFF: retomar o projeto ou tirar dúvidas em outra sessão

**Estado em 2026-10-29: trabalho concluído e publicado.** Este arquivo é a porta de entrada. Para
detalhes, leia nesta ordem: `README.md` (o relatório), `docs/processo.md` (o que foi feito e por quê,
etapa por etapa), `docs/resultados.md` (números da validação) e o plano em
`docs/superpowers/plans/2026-10-27-esp32cam-edge-impulse.md`. **Antes de afirmar qualquer fato daqui,
confira com comando**: isto é um retrato, não estado vivo.

## Links públicos

- GitHub (público): https://github.com/ricardopaivamelo/fiap-iot-esp32cam
- Edge Impulse (público): https://studio.edgeimpulse.com/public/1149980/latest. Versões públicas:
  v1 `v1-mao` (projeto público 1151482) e **v2** (projeto público 1152222). Projeto privado: id 1149980.

## O trabalho em 10 linhas

1. Enunciado FIAP IoT: treinar um modelo no Edge Impulse (trilha de imagem) e implantá-lo na ESP32-CAM.
2. Tarefa: **detecção de objetos FOMO** (o professor exigiu bounding boxes) com 3 classes: `garrafa`,
   `caderno` e `caneca`.
3. **v1:** 201 fotos 640×480 da própria placa, objetos segurados na mão. Boxes à mão. RGB foi melhor que
   grayscale (0,56 → 0,89). int8 foi melhor que float32 em precisão e em velocidade (741 ms × 4939 ms).
4. Ao vivo, **a mão virou atalho** (*shortcut learning*): estava em todo exemplo positivo.
5. **v2:** 285 fotos 320×240 com os objetos na mesa (mão só fora das boxes), coletadas pelo `viewer.py`
   com o próprio firmware de inferência. Boxes assistidas (YOLOv5 + API) com revisão.
6. v2 int8: **F1 de teste 0,92** (o v1 tinha 0,89); validação 0,94.
7. Na placa: inferência **741 ms** (determinística), ciclo **924 ms**, ~1,1 quadro/s. Arena de 154 KB
   na PSRAM, porque é maior que o maior bloco livre de RAM interna (110 KB).
8. Teste **A/B** v1 × v2 na mesma placa e cena: o v1 inventa caneca, perde caderno e troca classes; o v2 não.
9. Validação ao vivo: **56/57 tentativas certas**. O único tipo de erro é **garrafa de ponta → caneca**.
10. Entrega: README-relatório, guia para gravar na placa do professor e `.bin` único (offset 0x0),
    verificado na placa.

## Onde achar a resposta para cada dúvida

| Dúvida | Onde |
|---|---|
| O que é FOMO, por que detecção e não classificação | `docs/processo.md` Etapa 1; README §2 |
| Por que RGB e não grayscale | `processo.md` Etapa 4 (caderno 0% em grayscale) |
| Por que int8 e não float32 | `processo.md` Etapa 5 (latência) e Etapa 9 (tabela on-device: RAM 415 → 133 KB) |
| Por que não dá para acelerar mais | `processo.md` Etapa 6 (limite físico de RAM interna) |
| O viés da mão e por que recoletar | `processo.md` Etapas 7 e 8 |
| Como as boxes do v2 foram feitas (assistidas) | `processo.md` Etapa 8 "Rotulagem"; README §3; folhas em `docs/img/rotulagem-v2/` |
| Por que a mão fora da box ajuda | `processo.md` Etapa 8 (no FOMO, célula fora da box = background) |
| Métricas (F1, precisão, recall, matriz) | `docs/resultados.md` §1; prints `docs/img/10`, `10b`, `11` |
| Desempenho na placa | `resultados.md` §2; `docs/serial-log.txt` |
| Como a validação foi feita e o critério de acerto | `resultados.md` §3; tentativas em `validacao/` |
| Comparação v1 × v2 | `resultados.md` §4; prints `docs/img/ao-vivo/ab-v1-*` e `v2-*` |
| Limitações | `resultados.md` §5; README §5 |
| Como gravar em outra placa | `docs/gravar-na-sua-placa.md` |
| Protocolo serial `#FRAME` / `#DET` | `processo.md` Etapa 5; `viewer.py` (docstring) |
| Defasagem de 1 ciclo no viewer (achada e corrigida) | `processo.md` Etapa 9 "Achado ao preparar a validação" |
| Todas as decisões tomadas pelo Claude | ledger local `.superpowers/sdd/2026-10-27-esp32cam-edge-impulse/progress.md` (linhas `Ruling:`) |

## Decisões do Ricardo (todas fechadas)

| # | Decisão |
|---|---|
| D2 | Entregável = repo GitHub com README-relatório, prints e `.bin` |
| D5 | Repo **público** |
| D6 | **Sem vídeo** |
| D7 | Edge Impulse **público** (v1 e v2) |
| D8 | v2 **substitui** o v1 (v1 congelado na Version 1, amostras desativadas, não apagadas) |
| D9 | Coleta v2 pelo `viewer.py` (sem regravar o VisionGuard) |
| — | Teste fora da distribuição (outra luz/fundo, objeto na mão) **dispensado** |
| — | VisionGuard **não** será restaurado na placa |

Em aberto: D4 (prazo) nunca foi informado. A mensagem ao professor (mão × mesa, modelo da placa dele)
não foi enviada; o guia de gravação exige AI-Thinker com PSRAM.

## Pendência

- **Revogar a chave Admin** `claude-cli-admin` do Edge Impulse (Dashboard → Keys → Revoke). Em
  2026-10-29 ela ainda respondia. Nada no repo depende dela. Depois de revogar, os scripts de
  `tools/` que usam a API (`check_labels.py`, `folhas_rotulagem.py`) só voltam a funcionar com uma
  chave nova no `.env`.

## Estado físico

- **Placa:** firmware v2 gravado a partir do `release/fiap-esp32cam-fomo-v2-merged.bin` (0x0).
- **Lib Arduino instalada:** `fiap-iot-esp32cam_inferencing` 1.0.3 (v2) em
  `C:\Users\ricar\OneDrive\Documentos\Arduino\libraries\`.
- **Fora do git (local):** `.env` (chave), `backup/visionguard-flash.bin` (**senha do WiFi**),
  `dataset/` (v1), `dataset-v2/`, zips exportados na raiz (1.0.1 float32, 1.0.2 v1, 1.0.3 v2),
  `build/` = `build-v2/` (v2), `build-v1/` (v1 com o firmware atual, para repetir o A/B),
  `validacao/serial-completo.txt` (~36 min de serial).

## Comandos (PowerShell, na raiz do projeto)

```powershell
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')
.venv\Scripts\python -m pytest -q           # esperado: 58 passed
git status --short; git log --oneline -5; git log origin/main..main

# ver a placa ao vivo (tirar o jumper + RST) → http://localhost:8001
.venv\Scripts\python viewer.py --port COM3
# gravar (jumper IO0↔GND + RST antes; parar o viewer, que ocupa a COM3)
.venv\Scripts\python -m esptool --chip esp32 --port COM3 --baud 460800 write-flash 0x0 release\fiap-esp32cam-fomo-v2-merged.bin
# repetir o A/B: gravar o v1 e depois voltar ao v2
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app --input-dir build-v1
arduino-cli upload -p COM3 --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app --input-dir build-v2
# validação: tentativas com as teclas 1–5 e avaliação
.venv\Scripts\python viewer.py --port COM3 --out validacao --log validacao\serial-completo.txt
.venv\Scripts\python tools\resultados_validacao.py validacao --meta
```

Ciclo para gravar: **jumper + RST** → gravar → subir o viewer → **tirar o jumper + RST**. O boot só
aparece no viewer se ele já estiver aberto antes do RST.

## Gotchas já pagos

- **IO0 jumpeado depois de gravar** → placa parada em `waiting for download`. Sempre tirar + RST.
- **`printf` no firmware** fura a fila do `Serial` e quebra as linhas `#DET`; o `ei_printf` já está
  redirecionado.
- **Arena na PSRAM é inevitável** no 96×96. A única alavanca de velocidade seria entrada 64×64, com retreino.
- O firmware manda `#FRAME N` **antes** da inferência e `#DET N` depois; o viewer só publica o quadro
  junto com o `#DET` dele.
- Validação do Studio (~33 imagens) é ruidosa; decidir pelo **Model testing**.
- Uploader do Edge Impulse: lotes de ~30 arquivos com caminhos relativos (limite de 8191 caracteres do `cmd.exe`).
- Publicar uma Version no Edge Impulse **exige login no Studio** (a API recusa com chave: JWT only).
- `sed` com `\U`/`\r` na substituição corrompe texto (aconteceu no HANDOFF): para caminhos Windows,
  editar com a ferramenta Edit ou com um script Python.

## Regras do projeto

- Repo em `C:\Users\ricar\dev\fiap-iot-esp32cam`, branch `main`, remote **público** `origin`.
  Push automático após testes verdes. A home `C:\Users\ricar` também é repo git: nunca
  `git add -A`/`git add .` lá; aqui, adicionar arquivos específicos.
- Commits em PT-BR, convencionais, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Nunca imprimir nem commitar a chave do `.env` nem o `backup/`.
- Responder ao Ricardo em PT-BR, tom casual.
