#!/usr/bin/env python3
"""
Adiciona uma rodada ECMWF IFS 0,25 ao artefato "Risco climático para a eleição de 4/10 no Paraná".

Uso:
    python atualizar_ecmwf.py 2026100206 base_artefato.html artefato_atualizado.html
    (data e ciclo em AAAAMMDDHH, UTC)

Mesma janela e grade do GFS (lat -26.5 a -22.5, lon -54.5 a -48.0, 27x17).
Variaveis ECMWF: tp (chuva acumulada, m->mm), 10fg (rajada), mucape (CAPE), tcwv (PWAT).
Baixa via HTTP Range usando o .index (so as 4 variaveis, nao os 138MB completos).
"""
import sys, os, json, time, urllib.request, subprocess
from datetime import datetime, timedelta, timezone
import numpy as np
import pygrib

CYC, BASE, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
run = datetime.strptime(CYC, "%Y%m%d%H").replace(tzinfo=timezone.utc)
ELEI = datetime(2026, 10, 4, 3, tzinfo=timezone.utc)
W0, W1 = ELEI - timedelta(hours=24), ELEI + timedelta(hours=48)
f0 = int((W0 - run).total_seconds() // 3600)
f1 = int((W1 - run).total_seconds() // 3600)
assert f0 >= 0 and f0 % 3 == 0 and f1 <= 384, f"prazos inesperados: {f0}-{f1}"
FH = list(range(f0, f1 + 1, 3))
print(f"Rodada ECMWF {CYC}: prazos f{f0:03d} a f{f1:03d} ({len(FH)} arquivos)")

ROOT = f"https://data.ecmwf.int/forecasts/{CYC[:8]}/{CYC[8:]}z/ifs/0p25/oper/"
BASE_URL = f"{ROOT}{CYC[:8]}{CYC[8:]}0000"
PARAMS = ['tp', '10fg', 'mucape', 'tcwv']
os.makedirs("grib_ecmwf_" + CYC, exist_ok=True)

def get_index(f):
    url = f"{BASE_URL}-{f}h-oper-fc.index"
    for _ in range(4):
        try:
            return urllib.request.urlopen(url, timeout=60).read().decode()
        except Exception as e:
            print(f"  index f{f} tentativa: {e}"); time.sleep(2)
    sys.exit(f"ERRO: index f{f} indisponivel")

def get_range(f, off, ln):
    url = f"{BASE_URL}-{f}h-oper-fc.grib2"
    req = urllib.request.Request(url, headers={'Range': f'bytes={off}-{off+ln-1}'})
    for _ in range(4):
        try:
            return urllib.request.urlopen(req, timeout=120).read()
        except Exception as e:
            print(f"  range f{f} tentativa: {e}"); time.sleep(2)
    sys.exit(f"ERRO: range f{f} indisponivel")

def baixar(f):
    p = f"grib_ecmwf_{CYC}/f{f:03d}.grib2"
    if os.path.exists(p) and os.path.getsize(p) > 1000:
        return p
    idx = get_index(f)
    params = {}
    for line in idx.strip().splitlines():
        try: d = json.loads(line)
        except: continue
        if d.get('param') in PARAMS or d.get('param') == '10fg3':
            params[d['param']] = (d['_offset'], d['_length'])
    if len(params) < 4:
        sys.exit(f"ERRO: f{f} so tem {len(params)} das 4 variaveis")
    with open(p, "wb") as out:
        for prm in PARAMS:
            # aceita 10fg ou 10fg3 (rajada de 3h para prazos >72h)
            key = prm if prm in params else ('10fg3' if prm == '10fg' else None)
            if key is None:
                sys.exit(f"ERRO: f{f} sem {prm}")
            off, ln = params[key]
            out.write(get_range(f, off, ln))
    return p

# grade do artefato
NX, NY = 27, 17
LON0, LAT0, D = -54.5, -26.5, 0.25
ixs = [int(round((LON0 + ix*D + 180) / 0.25)) for ix in range(NX)]
iys = [int(round((90 - (LAT0 + iy*D)) / 0.25)) for iy in range(NY)]

def ler(p, f):
    g, out = pygrib.open(p), {}
    for m in g:
        v = m.values
        if m.shortName == "tp": out["tp"] = v * 1000.0  # m -> mm
        elif m.shortName in ("10fg", "10fg3"): out["gust"] = v
        elif m.shortName == "mucape": out["cape"] = v
        elif m.shortName == "tcwv": out["pw"] = v
    for k in ("tp", "gust", "cape", "pw"):
        if k not in out: sys.exit(f"ERRO: f{f} sem o campo {k}")
    sub = {k: np.array([[out[k][iy, ix] for ix in ixs] for iy in iys]) for k in out}
    return sub

G = {}
for f in FH:
    print(f"baixando f{f:03d}"); G[f] = ler(baixar(f), f)

# ---- artefato base
html = open(BASE, encoding="utf-8").read().split("\n")
k = next(i for i, l in enumerate(html) if l.startswith("const D="))
D = json.loads(html[k][8:].rstrip().rstrip(";"))
reg = np.array(D["reg"]).reshape(17, 27)
iso = run.strftime("%Y-%m-%dT%H:00Z")
if any(r["run"] == iso and r.get("model") == "ecmwf" for r in D["runs"]): sys.exit(f"ERRO: a rodada ECMWF {iso} ja esta no artefato")

rhu = lambda x: float(np.floor(x + 0.5))
frames, prob = [], []
for a, b in zip(FH[:-1], FH[1:]):
    A, B = G[a], G[b]
    iv = np.clip(B["tp"] - A["tp"], 0, None)
    gust = np.maximum(A["gust"], B["gust"])
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

# consistencia: intervalos continuos de 3 h cobrindo -24 a 48
if frames[0]["t0"] != -24 or frames[-1]["t1"] != 48 or any(f["t1"] - f["t0"] != 3 for f in frames):
    prob.append("intervalos nao cobrem 03/10 0h a 06/10 0h em passos de 3 h")

print("\nChecagens:", "OK" if not prob else "")
for p in prob: print("  PROBLEMA:", p)
if prob: sys.exit("Artefato NAO gerado. Resolva os problemas acima.")

D["runs"].append({"label": run.strftime("%d/%m · %H UTC"), "run": iso, "model": "ecmwf",
                  "frames": frames, "hasWind": True, "section": "current"})
D["runs"].sort(key=lambda r: r["run"])
for i, r in enumerate(D["runs"]):
    r["section"] = "current" if i >= len(D["runs"]) - 2 else "archive"
html[k] = "const D=" + json.dumps(D, ensure_ascii=False, separators=(",", ":")) + ";"
open(OUT, "w", encoding="utf-8").write("\n".join(html))

print(f"\nGerado {OUT} com {len(D['runs'])} rodadas ({os.path.getsize(OUT)/1e6:.1f} MB)")
print("Maximo por regiao no dia 04/10 (chuva mm em 3 h / rajada km/h):")
for f in frames:
    if 0 <= f["t0"] < 24:
        print(f"  {f['t0']:02d}h-{f['t1']:02d}h  " + "  ".join(
            f"{n}: {s['rain']:5.1f}/{s['gust']:3d}{'*' if s['storm'] else ' '}"
            for n, s in zip(["Oeste", "Norte", "C-Sul", "Leste"], f["st"])))
print("  (* = potencial de temporal)")
