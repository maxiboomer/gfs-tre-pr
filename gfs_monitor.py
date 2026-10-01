#!/usr/bin/env python3
"""
Monitor GFS — roda via hermes cron a cada 30 min.

Descobre sozinho a rodada mais recente DISPONIVEL no NOMADS (a partir da
ciclo 12Z de hoje, retrocedendo), e roda o atualizador quando ela ainda nao
esta no artefato. Nao ha ciclo fixo no codigo: trocar a data aqui nao e mais
necessario, e o monitor nao trava quando uma rodada demora a aparecer.

Apos ingerir, PUBLICA no VPS e na release do GitHub — o atualizador so escreve
o arquivo local; sem a publicacao o site publico fica desatualizado.

Saida: nada quando nao ha rodada nova (o cron nao notifica).
        texto quando houve ingestao (o cron entrega no WhatsApp).
"""
import sys, os, json, re, subprocess, urllib.request
from datetime import datetime, timedelta, timezone

ART = "/root/artefato_final.html"
PY = "/root/.hermes/venv-gfs/bin/python3"
BASE_URL = ("https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?"
            "dir=%2Fgfs.{d}%2F{h}%2Fatmos&file=gfs.t{h}z.pgrb2.0p25.f{f:03d}"
            "&var_APCP=on&var_PWAT=on&var_GUST=on&var_CAPE=on&all_lev=on&subregion="
            "&toplat=-22.5&bottomlat=-26.5&leftlon=305.5&rightlon=312")

# janela do artefato: 03/10 00h BRT .. 06/10 00h BRT = 03/10 03Z .. 06/10 03Z
ELEI = datetime(2026, 10, 4, 3, tzinfo=timezone.utc)


def probe(cyc, f):
    """True se o arquivo existe e e GRIB de verdade (nao pagina de erro do NOMADS)."""
    try:
        with urllib.request.urlopen(BASE_URL.format(d=cyc[:8], h=cyc[8:], f=f), timeout=20) as r:
            return r.read(4) == b"GRIB"
    except Exception:
        return False


def existe_no_artefato(cyc):
    """Rotinas ja ingeridas, lidas direto do HTML publicado."""
    iso = datetime.strptime(cyc, "%Y%m%d%H").replace(tzinfo=timezone.utc).strftime("%Y-%m-%dT%H:00Z")
    with open(ART, encoding="utf-8") as fh:
        m = re.search(r'const D=(\{.*?\});\n', fh.read(), re.DOTALL)
    return iso in [r["run"] for r in json.loads(m.group(1))["runs"]]


def candidatas():
    """12Z de hoje e dos dias anteriores, do mais novo para o mais antigo.

    12Z e a referencia do projeto: e o ciclo que melhor representa a manha do
    dia da eleicao, e as rodadas 18Z/00Z entram depois por decisao manual.
    """
    agora = datetime.now(timezone.utc)
    out = []
    for d in range(0, 12):
        dia = agora - timedelta(days=d)
        h = "12"
        if dia.hour < 12:  # o ciclo 12Z de hoje ainda nao aconteceu
            dia -= timedelta(days=1)
        out.append(f"{dia.strftime('%Y%m%d')}{h}")
    return out


def publicar():
    """Sobe o artefato para o VPS e recria a release v1.0 do GitHub.

    Retorna 0 em sucesso, 1 em falha. O VPS usa scp com a chave do servidor;
    a release usa o gh CLI (tag mutavel, apagada e recriada).
    """
    vps = subprocess.run(
        ["scp", "-i", "/root/.ssh/vps_tre", "-o", "StrictHostKeyChecking=no",
         ART, "root@163.245.212.102:/var/www/html/artefato.html"],
        capture_output=True, text=True, timeout=120)
    if vps.returncode != 0:
        sys.stderr.write("scp VPS falhou: " + (vps.stderr or "")[:300] + "\n")
        return 1

    gh = subprocess.run(
        ["bash", "-lc",
         "cd /root/gfs-tre-pr && "
         "gh release delete v1.0 --yes >/dev/null 2>&1; "
         "gh release create v1.0 --title 'Rodada GFS atualizada' "
         "--notes 'Atualizacao automatica pelo monitor GFS.' "
         "--repo maxiboomer/gfs-tre-pr >/dev/null 2>&1 && "
         "gh release upload v1.0 " + ART + " --repo maxiboomer/gfs-tre-pr >/dev/null 2>&1"],
        capture_output=True, text=True, timeout=180)
    if gh.returncode != 0:
        sys.stderr.write("release GitHub falhou: " + (gh.stderr or "")[:300] + "\n")
        return 1
    return 0


def main():
    if not os.path.exists(ART):
        sys.stderr.write("artefato ausente\n")
        return 1

    for cyc in candidatas():
        t = datetime.strptime(cyc, "%Y%m%d%H").replace(tzinfo=timezone.utc)
        # a rodada e usavel se o primeiro prazo da janela (24 h antes da eleicao)
        # existir e o ultimo (48 h depois) nao passar de f384
        f0 = int((ELEI - timedelta(hours=24) - t).total_seconds() // 3600)
        f1 = int((ELEI + timedelta(hours=48) - t).total_seconds() // 3600)
        if f0 < 0 or f1 > 384:
            continue
        if existe_no_artefato(cyc):
            return 0  # ja ingerida; nada a fazer
        if not probe(cyc, 132):  # f132 = marco de disponibilidade
            continue
        # a rodada pode estar ainda incompleta: espera o primeiro prazo
        if not probe(cyc, f0):
            continue

        cmd = [PY, "/root/atualizar_gfs.py", cyc, ART, ART]
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if r.returncode != 0:
            sys.stderr.write((r.stdout or "") + (r.stderr or ""))
            return 1

        # publica no VPS e na release (o atualizador so escreve o arquivo local)
        pub = publicar()
        if pub != 0:
            sys.stderr.write("ingestao ok, mas a publicacao falhou\n")
            return pub

        resumo = re.findall(r"^(?:  )?\S.*?pico.*?$", r.stdout, re.M)
        dt = datetime.strptime(cyc, "%Y%m%d%H")
        print(f"GFS {dt.strftime('%d/%m')} {cyc[8:]}Z ingerida e publicada no VPS e na release.")
        for ln in resumo[-4:]:
            print("  " + ln.strip())
        return 0

    return 0  # nada novo disponivel ainda


if __name__ == "__main__":
    sys.exit(main())
