"""VIP Leilões (www.vipleiloes.com.br) — nacional, bancos/seguradoras/apreendidos.

A busca é uma Razor Page: POST /pesquisa?handler=pesquisar com os campos do formulário
(Filtro.SubCategoriaId, Filtro.Monta, CurrentPage...) devolve HTML com 12 cartões div.crd-link
(título "MODELO - AAAA/AAAA", marca, km, valor atual, valor inicial, lote, UF, lances, início).
A monta não aparece no cartão: faz uma passada geral e depois uma por monta para etiquetar.
Funciona a partir dos servidores do GitHub.
"""
import re
from datetime import datetime

from ..parsing import brl, combustivel_de, norm
from .base import Fonte

BASE = "https://www.vipleiloes.com.br"
SUBCAT = {"carro": "4eb1a9c3-6c2d-41da-81e1-b3020155414e", "moto": "1014c6a3-4316-40c5-aa57-b3020152608f"}
MONTAS = {"1": "conservado", "2": "pequena", "3": "media", "4": "nao_informada",
          "5": "grande", "6": "grande", "7": "grande", "8": "grande"}
STATUS_FORA = ("ENCERRAD", "VENDID", "CANCELAD", "SUSPENS", "RETIRAD", "CONDICIONAL")


class VIP(Fonte):
    nome = "vip"

    def listar_leiloes(self) -> list[dict]:
        self._get(BASE + "/pesquisa")  # cookies de sessão
        out = []
        for tipo in SUBCAT:
            out.append({"id": f"{tipo}", "tipo": tipo, "monta": None, "texto": f"VIP {tipo}", "data": None, "origem": ""})
            out += [{"id": f"{tipo}-m{m}", "tipo": tipo, "monta": m, "texto": f"VIP {tipo} monta {m}",
                     "data": None, "origem": ""} for m in MONTAS]
        return out

    def listar_lotes(self, leilao: dict, max_paginas: int = 150) -> list[dict]:
        lotes, vistos = [], set()
        for pag in range(1, max_paginas + 1):
            dados = {"CurrentPage": str(pag), "Filtro.CurrentPage": str(pag), "Filtro.SelecaoVeiculos": "true",
                     "Filtro.SelecaoOutros": "false", "Filtro.SomenteDestaques": "false", "Filtro.Financiavel": "false",
                     "Filtro.OrdenarPor": "DataInicio", "Filtro.SubCategoriaId": SUBCAT[leilao["tipo"]]}
            if leilao["monta"]:
                dados["Filtro.Monta"] = leilao["monta"]
            r = self.http.post(BASE + "/pesquisa?handler=pesquisar", data=dados,
                               headers={"X-Requested-With": "XMLHttpRequest"})
            r.raise_for_status()
            import time; time.sleep(self.delay)
            from bs4 import BeautifulSoup
            novos = [l for l in self._cards(BeautifulSoup(r.text, "html.parser"), leilao) if l["id"] not in vistos]
            if not novos:
                break
            vistos.update(l["id"] for l in novos)
            lotes.extend(l for l in novos if l.pop("_ativo"))
        return lotes

    def _cards(self, soup, leilao) -> list[dict]:
        out = []
        for c in soup.select("div.crd-link"):
            a = c.find("a", href=re.compile(r"/evento/anuncio/.+-\d+$"))
            if not a:
                continue
            lote_id = re.search(r"-(\d+)$", a["href"]).group(1)
            h1 = c.find("h1")
            titulo = h1.get_text(" ", strip=True) if h1 else ""
            modelo, _, anos = titulo.rpartition(" - ")
            m_anos = re.match(r"(\d{4})/(\d{4})", anos.strip())
            info = [s.get_text(" ", strip=True) for s in c.select(".anc-info span")]
            marca = norm(info[0]) if info else ""
            txt = c.get_text(" ", strip=True)
            km = re.search(r"([\d\.]+)\s*Km", txt)
            uf = re.search(r"Local:\s*([A-Z]{2})", txt)
            lances = re.search(r"(\d+)\s*Lances?", txt)
            atual = c.select_one(".valor-atual")
            ini = re.search(r"Valor inicial:\s*(R\$ ?[\d\.]+,\d{2})", txt)
            ini_d = c.select_one(".anc-start")
            hora = c.select_one(".anc-hour")
            data = None
            if ini_d:
                m = re.search(r"(\d{2}/\d{2}/\d{4})", ini_d.get_text())
                if m:
                    data = datetime.strptime(f"{m.group(1)} {hora.get_text(strip=True) if hora else '00:00'}",
                                             "%d/%m/%Y %H:%M").isoformat()
            st = c.select_one(".situacao")
            status = norm(st.get_text()) if st else ""
            img = c.select_one("img.card-img-top")
            tem_lance = bool(lances and int(lances.group(1)) > 0)
            d = {
                "id": f"vip:{lote_id}", "fonte": self.nome, "leilao_id": leilao["id"], "leilao_titulo": "VIP Leilões",
                "origem": "", "leilao_data": data, "url": BASE + a["href"],
                "titulo": f"{'MOTO ' if leilao['tipo'] == 'moto' else ''}{marca} {norm(modelo)} {anos.strip()}".strip(),
                "tipo": leilao["tipo"], "marca": marca, "modelo": norm(modelo),
                "ano_fab": int(m_anos.group(1)) if m_anos else None, "ano_mod": int(m_anos.group(2)) if m_anos else None,
                "combustivel": combustivel_de(modelo), "km": int(km.group(1).replace(".", "")) if km else None,
                "uf": uf.group(1) if uf else None, "foto": img.get("src") if img else None,
                "lance_inicial": brl(ini.group(1)) if ini else None, "tem_lance": int(tem_lance),
                "_ativo": bool(data) and not any(s in status for s in STATUS_FORA),
            }
            if tem_lance and atual:
                d["lance_atual"] = brl(atual.get_text())
            if leilao["monta"]:
                d["monta"] = MONTAS[leilao["monta"]]
                d["flags"] = ["sinistro_recuperado"] if leilao["monta"] == "4" else []
            out.append(d)
        return out

    def detalhar(self, lote: dict) -> dict:
        return {"detalhe_ok": 1}
