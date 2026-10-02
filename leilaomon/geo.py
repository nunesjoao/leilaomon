"""Cidade/UF -> lat/lon. Nominatim (OSM) com cache; capital da UF como fallback."""
import time

import httpx

from .parsing import norm

CAPITAIS = {
    "AC": (-9.97, -67.81), "AL": (-9.67, -35.74), "AP": (0.03, -51.07), "AM": (-3.12, -60.02),
    "BA": (-12.97, -38.50), "CE": (-3.73, -38.53), "DF": (-15.79, -47.88), "ES": (-20.32, -40.34),
    "GO": (-16.68, -49.26), "MA": (-2.53, -44.30), "MT": (-15.60, -56.10), "MS": (-20.44, -54.65),
    "MG": (-19.92, -43.94), "PA": (-1.46, -48.49), "PB": (-7.12, -34.86), "PR": (-25.43, -49.27),
    "PE": (-8.05, -34.88), "PI": (-5.09, -42.80), "RJ": (-22.91, -43.17), "RN": (-5.79, -35.21),
    "RS": (-30.03, -51.23), "RO": (-8.76, -63.90), "RR": (2.82, -60.67), "SC": (-27.60, -48.55),
    "SP": (-23.55, -46.63), "SE": (-10.91, -37.07), "TO": (-10.18, -48.33),
}


def geocodificar(db, cidade: str | None, uf: str | None):
    uf = (uf or "").upper().strip()
    if not cidade or uf not in CAPITAIS:
        return CAPITAIS.get(uf, (None, None))
    chave = f"geo:{norm(cidade)}/{uf}"
    v = db.cache_get(chave, 3650)
    if v:
        return tuple(v)
    try:
        r = httpx.get("https://nominatim.openstreetmap.org/search", timeout=20,
                      params={"city": cidade, "state": uf, "country": "Brazil", "format": "json", "limit": 1},
                      headers={"User-Agent": "leilaomon/0.1 (monitor pessoal)"})
        time.sleep(1.1)  # política de uso do Nominatim: 1 req/s
        j = r.json() if r.status_code == 200 else []
        ll = (float(j[0]["lat"]), float(j[0]["lon"])) if j else CAPITAIS[uf]
    except Exception:  # noqa: BLE001
        ll = CAPITAIS[uf]
    db.cache_set(chave, list(ll))
    return ll
