#!/usr/bin/env python3
"""
Adiciona uma rodada GFS 0,25 ao artefato "Risco climático para a eleição de 4/10 no Paraná".

Uso:
    python atualizar_gfs.py 2026092712 base_artefato.html artefato_atualizado.html
    (data e ciclo em AAAAMMDDHH, UTC)

Janela: 03/10 00h a 06/10 00h (Brasília) = 03/10 03Z a 06/10 03Z.
Recorte: lat -26.5 a -22.5, lon 305.5 a 312. Variáveis: APCP, PWAT, GUST, CAPE.
Metodologia (conferida contra a rodada 26/09 12 UTC já publicada, diferença <= 0,05):
  chuva do intervalo = acumulado total (0-N h) no fim - no início
  rajada = maior entre início e fim, em km/h
  CAPE   = CAPE de superfície, maior entre início e fim
  água precipitável = valor no fim do intervalo
  "temporal" = algum ponto com >= 5 mm em 3 h e CAPE >= 1500 J/kg
Requisitos: pip install pygrib numpy
"""
import sys, os, json, time, urllib.request
from datetime import datetime, timedelta, timezone
import numpy as np
import pygrib

CYC, BASE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
run = datetime.strptime(CYC, "%Y%m%d%H").replace(tzinfo=timezone.utc)
TURNO = sys.argv[4] if len(sys.argv) > 4 else None   # '1t' | '2t' (default: ativo por data)
sys.path.insert(0, "/root")
from eleicao_config import config, janela, turno_ativo
CFG = config(TURNO)
ELEI = CFG["elei"]
W0, W1 = janela(CFG["key"])
f0 = max(0, int((W0 - run).total_seconds() // 3600))
f1 = int((W1 - run).total_seconds() // 3600)
assert f0 % 3 == 0 and f1 <= 384, f"prazos inesperados: {f0}-{f1}"
FH = list(range(f0, f1 + 1, 3))
if FH[0] == 0:
    FH = FH[1:]  # f000 nao tem tp_0-0 (instante inicial); comeca no f003
print(f"Rodada {CYC}: prazos f{FH[0]:03d} a f{FH[-1]:03d} ({len(FH)} arquivos, {len(FH)-1} intervalos)")

URL = ("https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?"
       "dir=%2Fgfs.{d}%2F{h}%2Fatmos&file=gfs.t{h}z.pgrb2.0p25.f{f:03d}"
       "&var_APCP=on&var_PWAT=on&var_GUST=on&var_CAPE=on&all_lev=on&subregion="
       "&toplat=-22.5&bottomlat=-26.5&leftlon=305.5&rightlon=312")
os.makedirs("grib_" + CYC, exist_ok=True)

def baixar(f):
    p = f"grib_{CYC}/f{f:03d}.grb"
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        return p
    for tent in range(4):
        try:
            with urllib.request.urlopen(URL.format(d=CYC[:8], h=CYC[8:], f=f), timeout=90) as r:
                b = r.read()
            if b[:4] == b"GRIB":
                open(p, "wb").write(b); return p
            raise RuntimeError("resposta não é GRIB (arquivo ainda não publicado?)")
        except Exception as e:
            print(f"  f{f:03d} tentativa {tent+1}: {e}"); time.sleep(10)
    sys.exit(f"ERRO: f{f:03d} indisponível. A rodada pode não estar completa; tente mais tarde.")

def ler(p, f):
    g, out = pygrib.open(p), {}
    for m in g:
        v = m.values
        lat = m.latlons()[0]
        if lat[0, 0] > lat[-1, 0]: v = v[::-1]
        if m.shortName == "tp": out["tp_" + m.stepRange] = v
        elif m.shortName == "cape" and m.typeOfLevel == "surface": out["cape"] = v
        elif m.shortName == "gust": out["gust"] = v
        elif m.shortName == "pwat": out["pw"] = v
    for k in ("cape", "gust", "pw", f"tp_0-{f}"):
        if k not in out: sys.exit(f"ERRO: f{f:03d} sem o campo {k}")
    if out["pw"].shape != (17, 27): sys.exit(f"ERRO: grade inesperada {out['pw'].shape}")
    return out

G = {}
for f in FH:
    print(f"baixando f{f:03d}"); G[f] = ler(baixar(f), f)

# ---- artefato base
html = open(BASE, encoding="utf-8").read().split("\n")
k = next(i for i, l in enumerate(html) if l.startswith(f"const D{CFG['key'].upper()}="))
D = json.loads(html[k][len(f"const D{CFG['key'].upper()}="):].rstrip().rstrip(";"))
reg = np.array(D["reg"]).reshape(17, 27)
iso = run.strftime("%Y-%m-%dT%H:00Z")
if any(r["run"] == iso for r in D["runs"]): sys.exit(f"ERRO: a rodada {iso} já está no artefato")

rhu = lambda x: float(np.floor(x + 0.5))            # arredondamento igual ao Math.round do JS
frames, prob = [], []
for a, b in zip(FH[:-1], FH[1:]):
    A, B = G[a], G[b]
    iv = B[f"tp_0-{b}"] - A[f"tp_0-{a}"]
    # consistência 1: intervalo pelo total x intervalo pelos baldes de 6 h do GFS
    bb = B[f"tp_{b - (b % 6 or 6)}-{b}"]
    ivb = bb if b % 6 == 3 else bb - A[f"tp_{b-6}-{a}"]
    d = np.abs(iv - ivb).max()
    if d > 0.2: prob.append(f"f{a}-{b}: total x baldes diferem {d:.2f} mm")
    if iv.min() < -0.05: prob.append(f"f{a}-{b}: chuva negativa {iv.min():.2f}")
    iv = np.clip(iv, 0, None)
    gust = np.maximum(A["gust"], B["gust"]) * 3.6
    cape = np.maximum(A["cape"], B["cape"])
    t0 = int(((run + timedelta(hours=a)) - ELEI).total_seconds() // 3600)
    t1 = int(((run + timedelta(hours=b)) - ELEI).total_seconds() // 3600)
    norm = (t1 - t0) / 3
    st = []
    for r in range(1, 5):
        m = reg == r
        st.append({"rain": round(float(iv[m].max()) / norm, 1),
                   "gust": int(rhu(gust[m].max())),
                   "cape": int(rhu(cape[m].max())),
                   "storm": bool(((iv / norm >= 5) & (cape >= 1500) & m).any())})
    frames.append({"t0": t0, "t1": t1,
                   "iv": [round(float(x), 1) for x in iv.ravel()],
                   "gust": [round(float(x), 1) for x in gust.ravel()],
                   "cape": [int(rhu(x)) for x in cape.ravel()],
                   "pw": [round(float(x), 1) for x in B["pw"].ravel()],
                   "st": st, "rainAll": round(float(iv[reg > 0].max()) / norm, 1)})

# consistência 2: soma dos intervalos = acumulado da janela inteira
tot = G[FH[-1]][f"tp_0-{FH[-1]}"] - G[FH[0]][f"tp_0-{FH[0]}"]
soma = sum(np.array(f["iv"]).reshape(17, 27) for f in frames)
d = np.abs(tot - soma).max()
if d > 0.05 * len(frames) + 0.1: prob.append(f"soma dos intervalos difere do total da janela em {d:.2f} mm")
# consistência 3: intervalos contínuos de 3 h (a rodada pode começar depois de -24
# quando e mais recente que a janela; outras rodadas cobrem o inicio)
if any(f["t1"] - f["t0"] != 3 for f in frames):
    prob.append("intervalos não são contínuos de 3 h")

print("\nChecagens:", "OK" if not prob else "")
for p in prob: print("  PROBLEMA:", p)
if prob: sys.exit("Artefato NÃO gerado. Resolva os problemas acima.")

D["runs"].append({"label": run.strftime("%d/%m · %H UTC"), "run": iso, "model": "gfs", "frames": frames, "hasWind": True, "section": "current"})
D["runs"].sort(key=lambda r: r["run"])
# marca seções: ultimas 2 = current, resto = archive
for i, r in enumerate(D["runs"]):
    r["section"] = "current" if i >= len(D["runs"]) - 2 else "archive"
html[k] = f"const D{CFG['key'].upper()}=" + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + ";"
open(OUT, "w", encoding="utf-8").write("\n".join(html))

# resumo para conferência
print(f"\nGerado {OUT} com {len(D['runs'])} rodadas ({os.path.getsize(OUT)/1e6:.1f} MB)")
print("Máximo por região no dia 04/10 (chuva mm em 3 h / rajada km/h):")
for f in frames:
    if 0 <= f["t0"] < 24:
        print(f"  {f['t0']:02d}h-{f['t1']:02d}h  " + "  ".join(
            f"{n}: {s['rain']:5.1f}/{s['gust']:3d}{'*' if s['storm'] else ' '}"
            for n, s in zip(["Oeste", "Norte", "C-Sul", "Leste"], f["st"])))
print("  (* = potencial de temporal)")