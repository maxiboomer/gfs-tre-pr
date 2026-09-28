# GFS TRE-PR — Risco Climático Eleição 2026

Monitoramento do modelo GFS 0,25° para previsão de risco climático no Paraná durante a eleição de 4 de outubro de 2026.

## O que faz

- Baixa dados GFS 0,25° (APCP, PWAT, GUST, CAPE) para o recorte do Paraná
- Calcula chuva por intervalo de 3h, rajada, CAPE, água precipitável
- Detecta potencial de temporal (CAPE ≥ 1500 J/kg + chuva ≥ 5mm/3h)
- Atualiza artefato HTML com nova rodada de forecast
- Valida consistência: total x baldes, soma dos intervalos, cobertura temporal

## Arquivos

| Arquivo | Descrição |
|---|---|
| `atualizar_gfs.py` | Script principal — baixa GRIB, processa, atualiza artefato |
| `gfs_monitor.py` | Monitor para cron — verifica disponibilidade, roda atualização |
| `monitor_gfs.py` | Monitor antigo (loop 30min) — substituído por cron do Hermes |

## Uso

```bash
# Rodar manualmente (ciclo AAAAMMDDHH)
python3 atualizar_gfs.py 2026092912 artefato_final.html artefato_final.html

# Monitor (cron a cada 30min)
# Configurado em: hermes cron list → "GFS 12Z monitor"
```

## Requisitos

```bash
pip install pygrib numpy
```

## Artefato

O artefato HTML é publicado no VPS em `https://noaa.netspin.com.br/`
Contém:
- Mapa interativo do Paraná com previsão por região
- Timeline de chuva/rajada
- Risco por região (Oeste, Norte, Centro-Sul, Leste)
- Cartórios de risco alto/crítico
- Comparação entre rodadas

## Cronograma

- Ciclos GFS: 00Z, 06Z, 12Z, 18Z (diários)
- Monitor foca no **12Z** (mais relevante para janela 03/10–06/10)
- Atualização automática quando dados publicados (~3h após ciclo)

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
