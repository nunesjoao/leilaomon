"""APL Leilões (aplleiloes.com.br) — plataforma Suporte Leilões, layout "eventos".

Veículos apreendidos (Detran-RJ / prefeituras) em pátios do interior do RJ e da capital.
  Home: article[class^=evento-index-] com /eventos/leilao/<id>/<slug>, título h3, data/hora
  Leilão: article.lote-main (classe lote-main-status-N), "Lote N", h3 categoria
     (AUTOMOVEL, MOTOCICLETA...), <p> "MARCA/MODELO-AAAA/AAAA-COMB-PLACA/UF-APL - PÁTIO-CONDIÇÃO",
     Lance Inicial, Lance Atual (quando há lance), status. Tudo na listagem: sem página de detalhe.
Funciona a partir dos servidores do GitHub (sem desafio do Cloudflare).
"""
import re
from datetime import datetime

from ..parsing import brl, classificar, combustivel_de, norm
from .base import Fonte

BASE = "https://aplleiloes.com.br"
RE_DESC = re.compile(r"^(?P<mm>.+?)-(?P<af>\d{4})/(?P<am>\d{4})-(?P<comb>[^-]*)-(?P<placa>[^-]*)-APL\s*-\s*"
                     r"(?P<patio>.+?)-(?P<cond>[^-]+)$")
PATIOS = {"CAMPO GRANDE": ("Rio de Janeiro", "RJ"), "TERESOPOLIS": ("Teresópolis", "RJ"),
          "BARRA DO PIRAI": ("Barra do Piraí", "RJ"), "NOVA IGUACU": ("Nova Iguaçu", "RJ")}
CAT_MOTO = ("MOTOCICLETA", "MOTONETA", "CICLOMOTOR", "TRICICLO", "QUADRICICLO")
STATUS_OK = ("ABERTO", "EM BREVE", "LOTEAMENTO", "PREGAO", "PREGÃO")


class APL(Fonte):
    nome = "apl"

    def listar_leiloes(self) -> list[dict]:
        soup = self._soup(BASE + "/")
        out = {}
        for art in soup.select('article[class*="evento-index-"]'):
            a = art.find("a", href=re.compile(r"/eventos/leilao/\d+/"))
            if not a:
                continue
            lid = re.search(r"/eventos/leilao/(\d+)/", a["href"]).group(1)
            txt = art.get_text(" ", strip=True)
            st = art.select_one(".strong-status")
            if st and "encerrad" in st.get_text().lower():
                continue
            m = re.search(r"(\d{2}/\d{2}/\d{4}).*?(\d{1,2}:\d{2})", txt)
            if not m:
                continue
            titulo = art.find("h3").get_text(" ", strip=True) if art.find("h3") else lid
            out[lid] = {"id": lid, "url": BASE + a["href"].replace(BASE, ""), "texto": titulo,
                        "data": datetime.strptime(" ".join(m.groups()), "%d/%m/%Y %H:%M").isoformat(),
                        "origem": "Apreendido (órgão público)"}
        return list(out.values())

    def listar_lotes(self, leilao: dict, max_paginas: int = 15) -> list[dict]:
        lotes, vistos = [], set()
        for pag in range(1, max_paginas + 1):
            soup = self._soup(leilao["url"], params={"page": pag} if pag > 1 else None)
            novos = [l for l in self._cards(soup, leilao) if l["id"] not in vistos]
            if not novos:
                break
            vistos.update(l["id"] for l in novos)
            lotes.extend(l for l in novos if l.pop("_ativo"))
        return lotes

    def _cards(self, soup, leilao) -> list[dict]:
        out, ids = [], set()
        for art in soup.select("article.lote-main"):
            a = art.find("a", href=re.compile(r"/lote/\d+/"))
            if not a:
                continue
            lote_id = re.search(r"/lote/(\d+)/", a["href"]).group(1)
            if lote_id in ids:
                continue
            ids.add(lote_id)
            num = art.select_one(".item-numeroLote")
            num = re.search(r"\d+", num.get_text()).group(0) if num and re.search(r"\d+", num.get_text()) else None
            cat = norm(art.find("h3").get_text()) if art.find("h3") else ""
            p = art.find("p")
            desc = p.get_text(" ", strip=True) if p else ""
            st = art.select_one(".strong-status")
            status = norm(st.get_text()) if st else ""
            ini = art.select_one("strong.close-text-isLance")
            atual = art.select_one("strong.valor-grid")
            v_ini = brl(ini.get_text()) if ini else None
            v_atu = brl(atual.get_text()) if atual else None
            img = art.select_one("img.img-evento")
            m = RE_DESC.match(norm(desc))
            mm = m["mm"] if m else desc.split("-")[0]
            marca, _, modelo = mm.partition("/")
            patio = norm(m["patio"]) if m else ""
            cidade, uf = PATIOS.get(patio, (patio.title() or None, "RJ"))
            tipo = "moto" if cat.startswith(CAT_MOTO) else "carro"
            monta, flags = classificar(f"{cat} {desc}", leilao["origem"])
            d = {
                "id": f"apl:{lote_id}", "fonte": self.nome, "leilao_id": leilao["id"],
                "leilao_titulo": leilao["texto"], "origem": leilao["origem"], "leilao_data": leilao["data"],
                "url": BASE + a["href"].replace(BASE, ""), "numero": num,
                "titulo": f"{'MOTO ' if tipo == 'moto' else ''}{norm(marca)} {norm(modelo)} "
                          f"{m['af'] + '/' + m['am'] if m else ''}".strip(),
                "tipo": tipo, "marca": norm(marca), "modelo": norm(modelo),
                "ano_fab": int(m["af"]) if m else None, "ano_mod": int(m["am"]) if m else None,
                "combustivel": combustivel_de(m["comb"]) if m else None,
                "foto": img.get("src") if img else None, "monta": monta, "flags": flags,
                "observacoes": desc, "cidade": cidade, "uf": uf,
                "lance_inicial": v_ini, "tem_lance": int(bool(v_atu)),
                "_ativo": any(s in status for s in STATUS_OK) or not status,
            }
            if v_atu:
                d["lance_atual"] = v_atu
            out.append(d)
        return out

    def detalhar(self, lote: dict) -> dict:
        return {"detalhe_ok": 1}  # a listagem já traz tudo
