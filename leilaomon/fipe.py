"""FIPE via API pública Parallelum v2 (https://fipe.online/docs).
Sem token: ~500 req/dia. Com token gratuito (header X-Subscription-Token) o limite sobe.
Tudo é cacheado no SQLite, então o custo em requisições cai rápido.
"""
import re
import time

import httpx
from rapidfuzz import fuzz, process

from .parsing import brl, norm

BASE = "https://fipe.parallelum.com.br/api/v2"
TIPO_API = {"carro": "cars", "moto": "motorcycles", "caminhao": "trucks"}
ALIAS_MARCA = {
    "VW - VOLKSWAGEN": "VW - VOLKSWAGEN", "VOLKSWAGEN": "VW - VOLKSWAGEN",
    "GM - CHEVROLET": "GM - CHEVROLET", "CHEVROLET": "GM - CHEVROLET",
    "MERCEDES BENZ": "MERCEDES-BENZ", "KIA": "KIA MOTORS", "CHERY": "CAOA CHERY",
    "HARLEY DAVIDSON": "HARLEY-DAVIDSON", "VW": "VW - VOLKSWAGEN", "GM": "GM - CHEVROLET",
    "M.BENZ": "MERCEDES-BENZ", "M BENZ": "MERCEDES-BENZ", "MBENZ": "MERCEDES-BENZ", "MMC": "MITSUBISHI", "CHEVROLLET": "GM - CHEVROLET", "VOLKSWAGEM": "VW - VOLKSWAGEN",
    "LR": "LAND ROVER", "CITROEN": "CITROEN", "JAC": "JAC",
}
COD_COMB = {"gasolina": "1", "flex": "1", "hibrido": "1", "alcool": "2", "diesel": "3"}
RE_CIL = re.compile(r"\b\d\.\d\b")


class Fipe:
    def __init__(self, db, token: str | None = None):
        self.db = db
        h = {"X-Subscription-Token": token} if token else {}
        self.http = httpx.Client(timeout=20, headers=h)

    def _get(self, path: str, max_dias: int):
        v = self.db.cache_get(path, max_dias)
        if v is not None:
            return v
        r = self.http.get(BASE + path)
        if r.status_code == 429:
            raise RuntimeError("FIPE: limite diário atingido (configure FIPE_TOKEN)")
        r.raise_for_status()
        time.sleep(0.3)
        v = r.json()
        self.db.cache_set(path, v)
        return v

    def _marca(self, tipo, marca):
        marcas = self._get(f"/{TIPO_API[tipo]}/brands", 30)
        alvo = ALIAS_MARCA.get(norm(marca), norm(marca))
        nomes = {m["code"]: norm(m["name"]) for m in marcas}
        best = process.extractOne(alvo, nomes, scorer=fuzz.WRatio, score_cutoff=85)
        return best[2] if best else None

    def _candidatos(self, tipo, cod_marca, modelo, n=5):
        modelos = self._get(f"/{TIPO_API[tipo]}/brands/{cod_marca}/models", 30)
        alvo = norm(modelo)
        cil = set(RE_CIL.findall(alvo))
        scored = []
        for m in modelos:
            nome = norm(m["name"])
            s = fuzz.token_set_ratio(alvo, nome)
            # primeira palavra do modelo (ex.: "CITY", "NINJA") precisa bater
            if alvo.split(" ")[0] not in nome.split(" "):
                s -= 25
            if cil and cil & set(RE_CIL.findall(nome)):
                s += 10
            scored.append((s, m))
        scored.sort(key=lambda x: -x[0])
        return [(s, m) for s, m in scored[:n] if s >= 55]

    def cotar(self, tipo, marca, modelo, ano_mod, combustivel) -> dict | None:
        if tipo not in TIPO_API or not (marca and modelo and ano_mod):
            return None
        cod_marca = self._marca(tipo, marca)
        if not cod_marca:
            return None
        pref = COD_COMB.get(combustivel or "", "1")
        for score, m in self._candidatos(tipo, cod_marca, modelo):
            base = f"/{TIPO_API[tipo]}/brands/{cod_marca}/models/{m['code']}/years"
            anos = [a for a in self._get(base, 30) if a["code"].startswith(f"{ano_mod}-")]
            if not anos:
                continue
            ano = next((a for a in anos if a["code"].endswith(f"-{pref}")), anos[0])
            p = self._get(f"{base}/{ano['code']}", 7)
            return {"fipe_valor": brl(p.get("price", "")), "fipe_codigo": p.get("codeFipe"),
                    "fipe_modelo": p.get("model"), "fipe_score": score}
        return None
