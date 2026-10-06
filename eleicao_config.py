#!/usr/bin/env python3
"""Configuracao compartilhada dos turnos das eleicoes 2026.

Cada turno tem: data de referencia (ELEI = 00h de Brasilia = 03Z do dia),
janela de prazos (W0, W1 em horas relativas a ELEI) e chave no artefato.

Turno 1 (04/10): janela -24..+48 (vespera + eleicao + dia seguinte).
Turno 2 (25/10): janela -48..+24 (2 dias antes + 1 dia depois, recomendado).

Regra de turno ativo: por data, com override por variavel de ambiente.
1T ativo ate 21/10; 2T ativo a partir de 22/10 (3 dias antes, para acumular
rodadas de comparacao antes do dia da eleicao).
"""
from datetime import datetime, timedelta, timezone

ELEICOES = {
    "1t": {"elei": datetime(2026, 10, 4, 3, tzinfo=timezone.utc), "w0": -24, "w1": 48,
           "label": "1º turno", "data": "04/10"},
    "2t": {"elei": datetime(2026, 10, 25, 3, tzinfo=timezone.utc), "w0": -48, "w1": 24,
           "label": "2º turno", "data": "25/10"},
}

TURNO_1T_ATE = datetime(2026, 10, 21, 23, 59, tzinfo=timezone.utc)


def turno_ativo(agora=None):
    """Chave do turno ativo ('1t' ou '2t'), por data ou override ELEI_TURNO."""
    env = __import__("os").environ.get("ELEI_TURNO", "").strip().lower()
    if env in ELEICOES:
        return env
    agora = agora or datetime.now(timezone.utc)
    return "1t" if agora <= TURNO_1T_ATE else "2t"


def config(turno=None):
    """Retorna a config do turno: {key, elei, w0, w1, label, data}."""
    key = turno or turno_ativo()
    c = dict(ELEICOES[key])
    c["key"] = key
    return c


def janela(turno=None):
    """Datas W0/W1 (UTC) da janela de prazos do turno."""
    c = config(turno)
    return c["elei"] + timedelta(hours=c["w0"]), c["elei"] + timedelta(hours=c["w1"])


if __name__ == "__main__":
    for k in ELEICOES:
        c = config(k)
        w0, w1 = janela(k)
        print(f"{k} {c['label']}: ELEI={c['elei']} janela {w0} .. {w1}")
    print("turno ativo agora:", turno_ativo())
