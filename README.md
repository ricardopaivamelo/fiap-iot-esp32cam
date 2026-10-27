# FIAP IoT — Classificação de objetos com ESP32-CAM + Edge Impulse

## Objetivo
Treinar no Edge Impulse um classificador de imagens com dados capturados pelo próprio ESP32-CAM,
exportar como biblioteca Arduino e rodar a inferência embarcada na placa.

## Hardware
- ESP32-CAM (clone AI-Thinker, OV2640, ~4 MB PSRAM)
- Adaptador USB-serial FT232R (COM3) — TX→U0R, RX→U0T, 5V→5V, GND→GND
- Modo de gravação: IO0→GND + RST; para rodar: remover IO0→GND + RST

## Como rodar
_Em construção — ver `docs/superpowers/plans/`._
