# HANDOFF — retomar o projeto em outra sessão

Leia isto primeiro. Depois: `docs/superpowers/plans/2026-10-27-esp32cam-edge-impulse.md` (plano vivo)
e `docs/processo.md` (o que foi feito e por quê). **Reconfira os fatos abaixo com comando** antes de
afirmar qualquer coisa — este arquivo é um retrato de 2026-10-28.

## Onde estamos (2026-10-28)

- **Feito:** setup, coleta v1 (201 fotos, objeto na mão), boxes manuais, 3 iterações de treino,
  firmware offline + `viewer.py`. Modelo **v1 int8** (F1 teste 0,89) **gravado e rodando** na placa:
  inferência 741 ms, ciclo ~0,88 s. Otimização de latência encerrada (limite de RAM interna).
- **Task 6 em andamento** — recoleta **sem a mão** (objetos na mesa) e retreino v2.
  D8 = substituir o v1 (Version + desativar amostras); D9 = coleta pelo viewer (Ricardo, 2026-10-28).
  - Steps 1–6 feitos. Version **`v1-mao`** (versão 1) criada; as **201 amostras v1 desativadas** (não apagadas).
  - `dataset-v2/`: **289 fotos únicas** 320×240 (caderno 62, garrafa 64, caneca 63, misto 60, vazio 40,
    vazio inclui mão sem objeto). Enviadas ao EI com prefixo `v2-` → **289 ativas (230 treino / 59 teste)**.
  - Coleta gerou 128 cópias idênticas (tecla repetida no mesmo quadro): apagadas no EI, movidas para fora
    do dataset localmente; bug corrigido no viewer (`532ee14`, 34 testes). Fotos movidas de pasta pelo
    Ricardo mantêm o nome antigo localmente; no EI foram renomeadas `v2-<pasta>_movida-<nome>`.
  - **Step 7 feito (2026-10-29):** 285 amostras ativas (227 treino / 58 teste), boxes: caneca 123,
    caderno 108, garrafa 104; `check_labels` → 0 objetos sem box. Rotulagem: Ricardo marcou parte dos
    mistos/cadernos no Studio (sugestões YOLOv5, labels COCO corrigidos depois via API); caderno, caneca,
    garrafa e o resto dos mistos foram marcados pela API com revisão visual (sub-agentes + conferência),
    regra **mão sempre fora da box** (no FOMO, mão fora da box vira exemplo de background). 4 amostras
    desativadas por mão cobrindo o objeto (caderno 0102/0103, garrafa 0036/0037). Folhas de conferência
    em `docs/img/rotulagem-v2/` (`tools/folhas_rotulagem.py <cena>` regenera).
- **Próximo passo:** Step 8 — retreino (dá para disparar pela API: a chave do `.env` é **Admin**).
- **Placa:** está com o firmware de inferência v1 gravado. O build atual em `build/` é a versão
  final limpa (sem o log `[alloc]`); a placa ainda roda a anterior, que imprime `[alloc] 153937 B -> PSRAM`
  por ciclo — inofensivo, some na próxima gravação.

## Como retomar (comandos, PowerShell, na raiz do projeto)

```powershell
# PATH atualizado (arduino-cli / esptool instalados depois do shell abrir)
$env:Path = [Environment]::GetEnvironmentVariable('Path','Machine') + ';' + [Environment]::GetEnvironmentVariable('Path','User')

arduino-cli board list                      # COM3 = FTDI da placa
.venv\Scripts\python -m pytest -q           # esperado: 33 passed
git status --short; git log --oneline -5

# compilar / gravar (gravar: jumper IO0↔GND + RST antes; parar o viewer antes, ele ocupa a COM3)
arduino-cli compile --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app firmware\esp32_camera --output-dir build
arduino-cli upload  -p COM3 --fqbn esp32:esp32:esp32cam:PartitionScheme=huge_app --input-dir build

# rodar (tirar o jumper + RST) e abrir http://localhost:8001
.venv\Scripts\python viewer.py --port COM3
```

Ciclo com o Ricardo para gravar: pedir **jumper + RST** → upload → subir o viewer → pedir **tirar jumper + RST**.
O boot só aparece se o leitor da serial já estiver aberto **antes** do RST.

## Onde está cada coisa

| Coisa | Local |
|---|---|
| Firmware | `firmware/esp32_camera/esp32_camera.ino` (mudanças marcadas `FIAP`) + `build_opt.h` |
| Biblioteca do modelo instalada | `C:\Users\ricar\OneDrive\Documentos\Arduino\libraries\fiap-iot-esp32cam_inferencing` (int8 **1.0.2**) |
| Zips exportados (fora do git) | raiz: `ei-fiap-iot-esp32cam-arduino-1.0.1-float32.zip`, `…-1.0.2-int8.zip` |
| Dataset v1 (fora do git) | `dataset/<cena>/` — 640×480; v2 irá em `dataset-v2/` |
| Prints do relatório | `docs/img/01`–`08` (próximos: `09+`, ver plano) |
| Conferência de rótulos no EI | `tools/check_labels.py` (lê `EI_API_KEY` do `.env`, nunca imprime) |
| Ledger de execução (local, gitignored) | `.superpowers/sdd/2026-10-27-esp32cam-edge-impulse/progress.md` + logs de compile/upload |
| Build float32 antigo (fora do git) | `build-float32/` |
| Backup do firmware VisionGuard | `backup/visionguard-flash.bin` — **contém senha do WiFi**, nunca commitar |
| Diagrama de ligação | `docs/wiring/ligacao-esp32cam.html` |

## Edge Impulse

- Projeto `fiap-iot-esp32cam`, id **1149980**. Chave da API só no `.env` (`EI_API_KEY`) — nunca colar no chat.
- Impulse: 96×96, Squash, RGB, FOMO MobileNetV2 0.35, 100 epochs, LR 0.001, augmentation.
- Export: **Arduino library → Quantized (int8)**, EON ligado. Ricardo baixa o zip e põe na raiz;
  instalar com `arduino-cli lib install --zip-path <zip>` (precisa `library.enable_unsafe_install true`).
- Uploader: chamar `%APPDATA%\npm\edge-impulse-uploader.cmd` (o shim `.ps1` junta os caminhos num argumento só).
  Mandar em **lotes de ~30 com nomes relativos** (`cwd` na pasta): 100 caminhos absolutos estouram o limite
  de 8191 caracteres do `cmd.exe` e o uploader sai com exit 1 sem mensagem.
- Chave do `.env` = `claude-cli-admin` (role **Admin**, criada 2026-10-28; a antiga era ingestion/deployment,
  que não cria versão/desativa/treina). Revogar em Dashboard → Keys ao fim do trabalho.

## Gotchas já pagos

- **IO0 jumpeado depois de gravar** → placa parada em `waiting for download`. Sempre tirar + RST.
- **`printf` × `Serial`:** com o buffer de TX de 8 KB, qualquer `printf` direto fura a fila e quebra as
  linhas `#DET`. O `ei_printf` já está redirecionado ao `Serial`; não use `printf` no firmware.
- **Arena na PSRAM é inevitável** no 96×96 (154 KB > maior bloco interno de 110 KB). Não reabrir essa
  otimização; a única alavanca é entrada menor (64×64), que exige retreino.
- `EI_MAX_OVERFLOW_BUFFER_COUNT=200` via `build_opt.h` (só foi necessário no float32, mantido).
- Validação do Studio (~33 imagens) é ruidosa; decidir pelo **Model testing**.
- `Set-Content` no PowerShell interpreta strings começando com `-D…` como parâmetro — usar a ferramenta Write.
- Pouca memória na máquina: o Claude Code pode encerrar processos em background ociosos (aconteceu com o `collector_ui`).

## Regras do projeto (não negociáveis)

- Repo próprio em `C:\Users\ricar\dev\fiap-iot-esp32cam`, branch `main`, **sem remote** ainda.
  A home `C:\Users\ricar` também é repo git: nunca `git add -A`/`git add .` lá; aqui, adicionar arquivos específicos.
- Commits em PT-BR, convencionais, terminando com `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Criar repo no GitHub só depois do Ricardo confirmar a visibilidade (D5).
- Responder ao Ricardo em PT-BR, tom casual.

## Decisões pendentes do Ricardo

D2 entregável · D4 prazo · D5 visibilidade do repo · D6 vídeo · D7 dataset público no EI ·
**D8** substituir ou somar o dataset v1 · **D9** método da recoleta (viewer × VisionGuard) ·
mensagem ao professor (mão ou mesa? mesmos objetos? modelo da placa dele?). Detalhes no plano.
