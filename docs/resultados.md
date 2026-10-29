# Resultados — validação do modelo v2 na ESP32-CAM

Validação ao vivo do modelo **v2 int8** (FOMO MobileNetV2 0.35, 96×96 RGB), rodando na placa,
em 2026-10-29. Processo e decisões em [`processo.md`](processo.md); este arquivo traz só os números.

## 1. Métricas do Edge Impulse

| Conjunto | int8 (na placa) | float32 |
|---|---|---|
| Validação (20% do treino) | F1 0,94 (P 0,92 / R 0,97) | F1 0,96 (P 0,94 / R 0,98) |
| **Teste (58 amostras separadas)** | **F1 0,92** (P 0,90 / R 0,95), 54/58, accuracy 93,1% | F1 0,95 (P 0,91 / R 0,98) |

F1 de validação int8 por classe: caderno 0,97, caneca 0,96, garrafa 0,88. O v1 (dataset com o objeto
na mão) tinha F1 de teste **0,89**. Prints: `img/10-treino-v2.png`, `img/10b-treino-v2-float32.png`,
`img/11-model-testing-v2.png`.

## 2. Desempenho na placa

Medido em **2.351 ciclos** de log real (`viewer.py --log`, ~36 min); trecho em [`serial-log.txt`](serial-log.txt).

| Etapa | Mediana | Faixa |
|---|---|---|
| Inferência (NN) | **741 ms** | 740–741 ms |
| DSP (resize/normalização) | 9 ms | 9 ms |
| Captura + JPEG→RGB + resize | 157 ms | 108–251 ms |
| **Ciclo completo** | **924 ms** (~1,1 quadro/s) | 874–1018 ms |

A inferência é determinística (depende só da arquitetura, não da cena). A captura varia com o tamanho
do JPEG da cena. Estimativa do Studio para o int8: 996 ms, RAM de pico 133 KB, flash 81 KB. A arena do
TFLite (~154 KB) fica na PSRAM, porque é maior que o maior bloco livre de RAM interna (~110 KB).

## 3. Validação ao vivo — cena de treino

**Protocolo.** Mesa e luz da coleta v2, objetos sem a mão. Cada **tentativa** = um quadro gravado pela
tecla da cena montada (não da cena detectada), com a posição ou o ângulo alterado entre tentativas. O
viewer grava o quadro e um `.json` com as detecções **daquele mesmo quadro**, em `../validacao/<cena>/`.
A avaliação é automática (`tools/resultados_validacao.py`).

**Critério de acerto:** exatamente as classes da cena. Objeto sozinho: só ele (dois centróides do mesmo
objeto contam como acerto). Misto: as classes que estavam na foto. Vazio: nenhuma detecção. No misto,
9 fotos foram montadas com **pares** e 8 com **os três objetos**; `../validacao/gabarito.json` registra o
que havia em cada foto. **Meta do plano:** ≥ 8/10 por classe e 0 falsos positivos no vazio.

| Cena | Tentativas | Acertos | Taxa | Meta |
|---|---|---|---|---|
| garrafa | 10 | 10 | 100% | ✅ |
| caderno | 10 | 10 | 100% | ✅ |
| caneca | 10 | 10 | 100% | ✅ |
| misto — três objetos | 8 | 7 | 88% | — |
| misto — pares | 9 | 9 | 100% | — |
| vazio | 10 | 10 | 100% | ✅ |
| **Total** | **57** | **56** | **98%** | |

Confiança dos acertos: garrafa 72–100%, caderno 52–100%, caneca 86–100%.

**Erros observados (os dois são garrafa → caneca):**
- `misto_0013` (três objetos): a garrafa, deitada no alto do quadro com o fundo voltado para a câmera,
  saiu como **caneca 97%**; a garrafa não foi detectada.
- `misto_0008` (par garrafa + caneca): conta como acerto pelo critério de classes, mas tem um
  **centróide falso de caneca (100%) no gargalo da garrafa**, em (32, 16), além da caneca real em (24, 64).
  O critério por conjunto de classes não enxerga esse erro; ele foi achado na inspeção das coordenadas.

Vistos de cima, o fundo e o gargalo da garrafa são círculos escuros, parecidos com a boca da caneca.
É a mesma confusão que o v1 cometia com frequência (seção 4), agora rara.

## 4. Comparação ao vivo com o v1 (teste A/B)

O v1 foi recompilado com o **mesmo firmware** e gravado na mesma placa, mesma mesa e mesma luz; só o
modelo muda. Prints em `img/ao-vivo/ab-v1-*.png`.

| Cena | v1 | v2 |
|---|---|---|
| garrafa + caderno | garrafa 96–97%, **caneca falsa** 63–66%, caderno 58% ou ausente | garrafa 98–100%, caderno 97–100%, nada além |
| três objetos | caderno não detectado | os três (7/8 tentativas) |
| caderno com a mão | oscila entre caderno, nada e **garrafa** 51% | — (fora do protocolo v2) |
| garrafa na mão | **caneca** 59% | — |
| mão vazia | sem erro neste A/B | background; 1 quadro isolado de caneca 55% |

## 5. Limitações

- **Uma única cena.** Treino, teste e validação usam a mesma mesa, a mesma luz e os mesmos três objetos.
  Os números acima não medem generalização para outro fundo, luz ou objetos parecidos. O teste fora
  da distribuição (outra luz, objeto na mão) foi planejado e não foi feito.
- **Garrafa → caneca** é a confusão residual, quando a garrafa aparece de ponta (fundo ou gargalo).
- **Objeto na mão:** o v2 foi treinado com a mão fora das boxes; o desempenho com o objeto segurado
  não foi medido.
- **~1,1 quadro/s.** A inferência de 741 ms limita o uso a cenas paradas ou lentas.
- **Contagem de objetos:** o FOMO devolve centróides; um objeto grande pode gerar dois pontos, então o
  número de detecções não é uma contagem confiável.
- **Validação manual:** 57 tentativas montadas por uma pessoa, com o ângulo variado a critério dela;
  é amostra pequena e não aleatória.

## 6. Tentativas (detalhe)

Saída de `python tools/resultados_validacao.py validacao` (uma linha por tentativa).

**garrafa**

| Tentativa | Detecções (conf.) | Acerto |
|---|---|---|
| `garrafa_0000` | garrafa 92% | ✅ |
| `garrafa_0001` | garrafa 96% | ✅ |
| `garrafa_0002` | garrafa 72% | ✅ |
| `garrafa_0003` | garrafa 94% | ✅ |
| `garrafa_0004` | garrafa 98% | ✅ |
| `garrafa_0005` | garrafa 96% | ✅ |
| `garrafa_0006` | garrafa 100% | ✅ |
| `garrafa_0007` | garrafa 91% | ✅ |
| `garrafa_0008` | garrafa 98% | ✅ |
| `garrafa_0009` | garrafa 99% | ✅ |

**caderno**

| Tentativa | Detecções (conf.) | Acerto |
|---|---|---|
| `caderno_0000` | caderno 98% | ✅ |
| `caderno_0001` | caderno 100% | ✅ |
| `caderno_0002` | caderno 87% | ✅ |
| `caderno_0003` | caderno 100% | ✅ |
| `caderno_0004` | caderno 99% | ✅ |
| `caderno_0005` | caderno 71% | ✅ |
| `caderno_0006` | caderno 100% | ✅ |
| `caderno_0007` | caderno 52% | ✅ |
| `caderno_0008` | caderno 88% | ✅ |
| `caderno_0009` | caderno 96% | ✅ |

**caneca**

| Tentativa | Detecções (conf.) | Acerto |
|---|---|---|
| `caneca_0000` | caneca 99% | ✅ |
| `caneca_0001` | caneca 87% | ✅ |
| `caneca_0002` | caneca 100% | ✅ |
| `caneca_0003` | caneca 99% | ✅ |
| `caneca_0004` | caneca 100% | ✅ |
| `caneca_0005` | caneca 86% | ✅ |
| `caneca_0006` | caneca 96% | ✅ |
| `caneca_0007` | caneca 95% | ✅ |
| `caneca_0008` | caneca 95% | ✅ |
| `caneca_0009` | caneca 100% | ✅ |

**misto**

| Tentativa | Na cena | Detecções (conf.) | Acerto |
|---|---|---|---|
| `misto_0000` | caderno, caneca | caneca 100%, caderno 91% | ✅ |
| `misto_0001` | caderno, caneca | caderno 65%, caneca 100% | ✅ |
| `misto_0002` | caderno, garrafa | garrafa 88%, caderno 90% | ✅ |
| `misto_0003` | caderno, garrafa | garrafa 81%, caderno 91% | ✅ |
| `misto_0004` | caderno, garrafa | garrafa 99%, caderno 100% | ✅ |
| `misto_0005` | caneca, garrafa | garrafa 100%, caneca 87% | ✅ |
| `misto_0006` | caneca, garrafa | garrafa 100%, caneca 96% | ✅ |
| `misto_0007` | caneca, garrafa | garrafa 53%, caneca 98% | ✅ |
| `misto_0008` | caneca, garrafa | caneca 100%, garrafa 84%, caneca 96% | ✅ |
| `misto_0009` | caderno, caneca, garrafa | garrafa 100%, caderno 92%, caneca 99% | ✅ |
| `misto_0010` | caderno, caneca, garrafa | garrafa 100%, caderno 87%, caneca 100% | ✅ |
| `misto_0011` | caderno, caneca, garrafa | garrafa 100%, caderno 86%, caneca 100% | ✅ |
| `misto_0012` | caderno, caneca, garrafa | garrafa 100%, caneca 99%, caderno 95% | ✅ |
| `misto_0013` | caderno, caneca, garrafa | caneca 97%, caneca 99%, caderno 99% | ❌ |
| `misto_0014` | caderno, caneca, garrafa | caneca 96%, caderno 62%, garrafa 99% | ✅ |
| `misto_0015` | caderno, caneca, garrafa | caneca 100%, caderno 94%, garrafa 100% | ✅ |
| `misto_0016` | caderno, caneca, garrafa | caneca 100%, caderno 92%, garrafa 100% | ✅ |

**vazio**

| Tentativa | Detecções (conf.) | Acerto |
|---|---|---|
| `vazio_0000` | — | ✅ |
| `vazio_0001` | — | ✅ |
| `vazio_0002` | — | ✅ |
| `vazio_0003` | — | ✅ |
| `vazio_0004` | — | ✅ |
| `vazio_0005` | — | ✅ |
| `vazio_0006` | — | ✅ |
| `vazio_0007` | — | ✅ |
| `vazio_0008` | — | ✅ |
| `vazio_0009` | — | ✅ |
