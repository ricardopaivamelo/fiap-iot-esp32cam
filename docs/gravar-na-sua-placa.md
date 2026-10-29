# Gravar o modelo na sua ESP32-CAM

Um arquivo só, `release/fiap-esp32cam-fomo-v2-merged.bin` (bootloader + partições + app), gravado no
endereço **0x0**. Não precisa de Arduino IDE nem do Edge Impulse.

## Requisitos

- **ESP32-CAM AI-Thinker (ou clone) com PSRAM** e câmera OV2640. Sem PSRAM o firmware não roda: a arena
  do modelo (~154 KB) só cabe na PSRAM.
- Adaptador USB-serial (FTDI, CH340 ou a base ESP32-CAM-MB) e 5 V estáveis.
- Ligação (adaptador → placa): `TX → U0R`, `RX → U0T`, `5V → 5V`, `GND → GND`. Diagrama em
  [`wiring/ligacao-esp32cam.html`](wiring/ligacao-esp32cam.html).

## 1. Entrar em modo de gravação

1. Ligue um jumper entre **IO0 e GND**.
2. Aperte o **RST** (ou desligue e ligue a placa).

A base ESP32-CAM-MB faz isso sozinha: segure o botão IO0, aperte RST e solte.

## 2. Gravar — opção A: pelo navegador (Chrome ou Edge)

1. Abra <https://espressif.github.io/esptool-js/>.
2. *Baudrate* **460800** (use 115200 se der erro) → **Connect** → escolha a porta do adaptador.
3. Em *Flash Address* coloque **0x0** e selecione `fiap-esp32cam-fomo-v2-merged.bin`.
4. **Program** e espere terminar (~30 s).

## 2. Gravar — opção B: pela linha de comando

```bash
pip install esptool
esptool --chip esp32 --port COM3 --baud 460800 write-flash 0x0 release/fiap-esp32cam-fomo-v2-merged.bin
```

Troque `COM3` pela porta do adaptador (Linux: `/dev/ttyUSB0`; macOS: `/dev/cu.usbserial-*`).
O esptool confere o hash no fim (`Hash of data verified`).

## 3. Rodar

1. **Tire o jumper IO0–GND** (se ficar, a placa para em `waiting for download`).
2. Aperte o **RST**.

## 4. Ver as detecções

O firmware é offline (sem WiFi) e manda tudo pela serial a **460800 baud**.

**Viewer no navegador** (imagem da câmera + detecções):

```bash
pip install -r requirements.txt
python viewer.py --port COM3
```

Abra <http://localhost:8001>. As classes detectadas aparecem embaixo da imagem; marque
"marcar detecções na imagem" para ver os centróides.

**Só texto:** qualquer monitor serial a 460800 (Arduino IDE, PuTTY). As linhas `#FRAME` são a imagem
em base64; as detecções aparecem assim:

```
Object detection bounding boxes:
  caneca (0.980469) [ x: 40, y: 16, width: 8, height: 16 ]
```

## Problemas comuns

| Sintoma | Causa provável |
|---|---|
| `Failed to connect` ao gravar | jumper IO0–GND solto ou RST não apertado; TX/RX invertidos |
| Gravou, mas nada aparece | jumper IO0 ainda ligado; tire e aperte RST |
| `Brownout detector was triggered` | alimentação fraca; use 5 V de outra porta USB ou fonte |
| `Camera init failed` | cabo flat da câmera mal encaixado ou placa diferente da AI-Thinker |
| Reinicia sem parar ao carregar o modelo | placa sem PSRAM |
| Viewer mostra "sem sinal da placa" | porta errada, outro programa usando a porta, ou falta apertar RST |

## O que esperar

Classes: `garrafa`, `caderno`, `caneca`. ~1 quadro por segundo (inferência de 741 ms). O modelo foi
treinado com uma mesa clara, luz de interior e objetos específicos, vistos de cima; fora disso a
precisão cai (ver [`resultados.md`](resultados.md), seção Limitações).
