"""Copart Brasil (www.copart.com.br).

Usa a mesma busca pública que o site chama (POST /public/lots/search), que responde JSON.
Com showUpComing=false a busca devolve só os lotes já agendados para leilão (~1.400),
paginados com size/page. robots.txt da Copart não restringe nada. Roda pelo GitHub.
Campos: ln (lote), mkn/lm (marca/modelo), lcy/manufactureYear (anos), eng, orr (km),
yn (pátio "CIDADE - UF"), ad (data do leilão), hb (maior lance), tims (foto),
damageClassification (monta), vinType/tipodocumento (Recuperável/Irrecuperável), lossType (origem).
"""
import re
from datetime import datetime

from ..parsing import classificar, combustivel_de, norm
from .base import Fonte

BASE = "https://www.copart.com.br"
HDR = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"}
MONTA = {"PEQUENA MONTA": "pequena", "MEDIA MONTA": "media", "GRANDE MONTA": "grande"}


class Copart(Fonte):
    nome = "copart"

    def listar_leiloes(self) -> list[dict]:
        self._get(BASE + "/")  # cookies de sessão do site
        return [{"id": "agendados", "texto": "Copart: lotes agendados", "data": None, "origem": ""}]

    def listar_lotes(self, leilao: dict, max_paginas: int = 40) -> list[dict]:
        lotes = []
        for pag in range(max_paginas):
            r = self.http.post(BASE + "/public/lots/search", headers=HDR,
                               data={"query": "*", "size": "100", "page": str(pag), "showUpComing": "false"})
            r.raise_for_status()
            res = r.json()["data"]["results"]
            itens = res["content"]
            lotes.extend(l for l in (self._lote(x) for x in itens) if l)
            if len(itens) < 100 or (pag + 1) * 100 >= res["totalElements"]:
                break
            self._pausa()
        return lotes

    def _pausa(self):
        import time
        time.sleep(self.delay)

    def _lote(self, x: dict):
        if (x.get("saleType") or "") != "Leilão":
            return None  # "Compre agora"/Copart Select: sem data de pregão
        try:
            quando = datetime.strptime(x.get("ad") or "", "%Y-%m-%d %H:%M:%S").isoformat()
        except ValueError:
            return None
        cat = norm(x.get("vehicleType") or "")
        tipo = "moto" if "MOTO" in cat else "caminhao" if "CAMINH" in cat or "ONIBUS" in cat else "carro"
        marca, modelo = norm(x.get("mkn") or ""), norm(f"{x.get('lm') or ''} {x.get('eng') or ''}")
        yard = x.get("yn") or ""
        m = re.match(r"^(.*?)\s*(?:\(.*\))?\s*-\s*([A-Z]{2})$", yard.strip())
        cidade, uf = (m.group(1).title(), m.group(2)) if m else (None, None)
        dano = norm(x.get("damageClassification") or "")
        doc = norm(x.get("vinType") or "")
        perda = x.get("lossType") or ""
        monta = MONTA.get(dano)
        if "IRRECUPER" in doc:
            monta = "grande"
        texto_flags = f"{perda} {x.get('drivabilityRating') or ''}"
        m2, flags = classificar(texto_flags, perda)
        if monta is None:
            monta = m2 if m2 in ("conservado", "grande") else "nao_informada"
        if norm(x.get("drivabilityRating") or "") == "NAO DA PARTIDA":
            flags.append("nao_funciona")
        hb = float(x.get("hb") or 0)
        ano_m = int(x["lcy"]) if str(x.get("lcy") or "").isdigit() else None
        ano_f = int(x["manufactureYear"]) if str(x.get("manufactureYear") or "").isdigit() else ano_m
        km = int(x["orr"]) if x.get("orr") else None
        return {
            "id": f"cp:{x['ln']}", "fonte": self.nome, "leilao_id": quando[:10], "leilao_titulo": f"Copart {yard}",
            "origem": perda.title(), "leilao_data": quando, "url": f"{BASE}/lot/{x['ln']}",
            "numero": str(x["ln"]), "tipo": tipo, "marca": marca, "modelo": modelo.strip(),
            "titulo": f"{'MOTO ' if tipo == 'moto' else ''}{marca} {modelo.strip()} {ano_f or ''}/{ano_m or ''}".strip(),
            "ano_fab": ano_f, "ano_mod": ano_m, "km": km or None, "combustivel": combustivel_de(x.get("ft") or ""),
            "foto": x.get("tims"), "monta": monta, "flags": flags,
            "observacoes": f"{perda}; {x.get('damageClassification') or ''}; documento {x.get('vinType') or '?'}; "
                           f"{x.get('drivabilityRating') or ''}; dano: {x.get('dd') or '?'}",
            "cidade": cidade, "uf": uf, "tem_lance": int(hb > 0),
            **({"lance_atual": hb} if hb > 0 else {}),
        }

    def detalhar(self, lote: dict) -> dict:
        return {"detalhe_ok": 1}
