#!/usr/bin/env python3
"""Monitor GFS 18Z — roda via hermes cron a cada 30min."""
import sys, os, urllib.request

CYC = "2026092918"
URL = ("https://nomads.ncep.noaa.gov/cgi-bin/filter_gfs_0p25.pl?"
       "dir=%2Fgfs.{d}%2F{h}%2Fatmos&file=gfs.t{h}z.pgrb2.0p25.f{f:03d}"
       "&var_APCP=on&var_PWAT=on&var_GUST=on&var_CAPE=on&all_lev=on&subregion="
       "&toplat=-22.5&bottomlat=-26.5&leftlon=305.5&rightlon=312")

def check(f):
    url = URL.format(d=CYC[:8], h=CYC[8:], f=f)
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.read(4) == b"GRIB"
    except Exception:
        return False

if not check(132):
    sys.exit(0)

os.chdir("/root")
os.system("source /root/.hermes/venv-gfs/bin/activate && "
          "python3 /root/atualizar_gfs.py 2026092918 /root/artefato_final.html /root/artefato_final.html")