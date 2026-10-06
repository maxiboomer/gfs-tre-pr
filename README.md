# GFS TRE-PR — Risco Climático Eleição 2026

Monitoramento dos modelos GFS 0,25° e ECMWF IFS 0,25° para previsão de risco climático no Paraná durante as eleições de 2026 (**1º turno 04/10, 2º turno 25/10**).

## O que faz

- Baixa dados GFS 0,25° (APCP, PWAT, GUST, CAPE) para o recorte do Paraná
- Calcula chuva por intervalo de 3h, rajada, CAPE, água precipitável
- Detecta potencial de temporal (CAPE ≥ 1500 J/kg + chuva ≥ 5mm/3h)
- Atualiza artefato HTML com nova rodada de forecast
- Valida consistência: total x baldes, soma dos intervalos, cobertura temporal

## Arquivos

| Arquivo | Descrição |
|---|---|
| `atualizar_gfs.py` | Script principal — baixa GRIB, processa, atualiza artefato (turno via 4º arg) |
| `atualizar_ecmwf.py` | Baixa ECMWF IFS 0,25° (HTTP Range), processa, atualiza artefato |
| `gfs_monitor.py` | Monitor para cron — verifica disponibilidade, roda atualização |
| `eleicao_config.py` | Config dos turnos: ELEI, janela, turno ativo por data (override `ELEI_TURNO`) |
| `monitor_gfs.py` | Monitor antigo (loop 30min) — substituído por cron do Hermes |

## Turnos

O artefato tem **dois painéis** (1º e 2º turno), alternados por `?turno=1t|2t` na URL. Cada turno tem data de referência e janela próprias:

| Turno | Eleição | Janela |
|---|---|---|
| 1t | 04/10 | -24h..+48h (véspera + eleição + dia seguinte) |
| 2t | 25/10 | -48h..+24h (2 dias antes + 1 dia depois) |

O turno ativo é detectado por data: **1t até 21/10, 2t a partir de 22/10** (3 dias antes, para acumular rodadas de comparação). Override com `ELEI_TURNO=1t|2t`.

## Uso

```bash
# Deixar o monitor descobrir a rodada sozinho (é o que o cron faz)
/root/.hermes/venv-gfs/bin/python3 gfs_monitor.py

# Ou forçar uma rodada específica (ciclo AAAAMMDDHH, turno opcional)
python3 atualizar_gfs.py 2026093012 artefato_final.html artefato_final.html 1t
python3 atualizar_ecmwf.py 2026100212 artefato_final.html artefato_final.html 2t
```

O monitor descobre sozinho a rodada **12Z** mais recente que ainda não está no
artefato, valida se o NOMADS já a publicou e só então roda o atualizador. Não há
ciclo fixo no código. Rodar duas vezes não duplica rodada.

## Requisitos

```bash
pip install pygrib numpy
```

## Artefato

**O HTML não é versionado no git** (`.gitignore` exclui `artefato*.html`): são
2,7 MB por versão e muda a cada rodada, o que inflaria o histórico. Ele é
publicado em dois lugares:

- **VPS**: `https://noaa.netspin.com.br/artefato.html`
- **Release**: [`v1.0`](https://github.com/maxiboomer/gfs-tre-pr/releases/tag/v1.0)
  (`artefato_final.html` anexado)

A release v1.0 é uma **tag mutável**: é apagada e recriada a cada publicação.
A URL é estável, o conteúdo não é append-only. Para recuperar o artefato
atual: baixe o anexo da release, ou `scp` do VPS.

Para rodar `atualizar_gfs.py` localmente, baixe o artefato da release e
use-o como entrada e saída.

Contém:
- Mapa interativo do Paraná com previsão por região
- Timeline de chuva/rajada
- Risco por região (Oeste, Norte, Centro-Sul, Leste)
- Índice de tensão para interrupção de energia (0–100), com hover mostrando o
  motivo de cada valor
- Ranking dos 12 cartórios de maior tensão, cruzado com a vulnerabilidade da SECAD
- Comparação entre rodadas, com abas Atual (2 últimas) e Archive
- Rodapé "Fórmulas e índices": equação, pesos, faixas e limitações

## Cronograma

- Ciclos GFS: 00Z, 06Z, 12Z, 18Z (diários)
- Monitor foca no **12Z** (mais relevante para janela 03/10–06/10)
- Atualização automática quando dados publicados (~3h após ciclo)

## Armadilhas conhecidas

Verificadas nos incidents de 30/09. Vale conferir antes de mexer no CSS:

- **Chaves CSS balanceadas.** Um `@media` sem o `}` de fechamento engole todo o
  CSS seguinte: o browser aceita 2 de 117 regras e descarta o resto **sem erro
  no console**. Confira com `document.styleSheets[1].cssRules.length` — tem que
  ser > 50. Um `replace` de texto sobre HTML pode comer a chave vizinha.
- **`node --check` não valida CSS.** Só sintaxe de JavaScript. Um artefato com
  CSS destruído passa nele.
- **Verificar no browser, não só no arquivo.** `base_artefato.html` é a base
  original e **não tem** o índice de tensão, o rodapé de método nem as abas.
  Regenerar a partir dele perde esse trabalho. Use sempre o artefato atual como
  entrada.
- **Contraste das cores de risco.** Os valores originais reprovavam WCAG AA
  (o amarelo de "moderado" dava 1,96:1). Recalibrados; manter ≥ 3:1 no claro e
  no escuro.

## Dados

- Fonte: NOAA/NCEP GFS 0,25° (nomads.ncep.noaa.gov)
- Recorte: lat -26,5 a -22,5, lon 305,5 a 312
- Janela: 03/10 00Z a 06/10 00Z (véspera + dia da eleição)
- Regiões: Oeste, Norte, Centro-Sul, Leste

## Configuração

1. `gh auth login` (GitHub CLI)
2. `hermes cron create '*/30 * * * *' --name "GFS 12Z monitor" --script gfs_monitor.py --no-agent --deliver whatsapp:Fabio`
3. Aguardar DNS `noaa.netspin.com.br` propagar

## Licença

Uso interno TRE-PR.
