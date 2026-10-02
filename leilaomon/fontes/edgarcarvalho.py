"""Edgar de Carvalho Jr. Leiloeiro (www.edgarcarvalholeiloeiro.com.br) — Suporte Leilões.

Leiloeiro dos leilões de veículos da SEOP (prefeitura do Rio) e do Detran-RJ; no resto do
tempo vende principalmente materiais. A agenda (/leiloes) tem <article> por evento, com a
categoria ("Veículos") e "Data Única: dd/mm/aaaa às HH:MM". Um evento pode ser:
  - leilão com vários lotes: /leiloes/<id>?page=N, div.lote com /oferta/leilao/veiculos/...,
    "Localização: Cidade / UF", "Valor inicial: R$", status (.lote-status);
  - oferta avulsa (um veículo): /oferta/leilao/veiculos/<sub>/<id>/... com "Encerramento",
    "LOCAL DE RETIRADA", "R$ X / Lance inicial".
Funciona a partir dos servidores do GitHub.
"""
import re
from datetime import datetime

from ..parsing import ano4, brl, classificar, combustivel_de, eh_moto, norm
from .base import Fonte

BASE = "https://www.edgarcarvalholeiloeiro.com.br"
RE_OFERTA = re.compile(r"/oferta/leilao/veiculos/([^/]+)/(\d+)/")
STATUS_FORA = ("ENCERRAD", "VENDID", "ARREMATAD", "RETIRAD", "CANCELAD", "SUSPENS")


def _veiculo(titulo: str, sub: str) -> dict:
    t = norm(titulo)
    cab = t.split(" - ")[0]
    marca, _, modelo = cab.partition("/")
    marca, modelo = marca.strip(), modelo.strip()
    anos = re.search(r"\b((?:19|20)\d{2})\s*/\s*((?:19|20)\d{2})\b", t) or re.search(r"\bANO\s*((?:19|20)\d{2})\b", t)
    af = int(anos.group(1)) if anos else None
    am = int(anos.group(2)) if anos and anos.lastindex == 2 else af
    tipo = "moto" if "moto" in sub or eh_moto(marca, modelo) else "carro"
    return {"tipo": tipo, "marca": marca, "modelo": modelo, "ano_fab": af, "ano_mod": am,
            "combustivel": combustivel_de(t),
            "titulo": f"{'MOTO ' if tipo == 'moto' else ''}{marca} {modelo} {f'{af}/{am}' if af else ''}".strip()}


class EdgarCarvalho(Fonte):
    nome = "edgarcarvalho"

    def listar_leiloes(self) -> list[dict]:
        soup = self._soup(BASE + "/leiloes")
        out = []
        for art in soup.find_all("article"):
            a = art.find("a", href=True)
            if not a:
                continue
            txt = art.get_text(" | ", strip=True)
            cat = art.select_one(".r1")
            if not cat or "VEICULO" not in norm(cat.get_text()) or any(s in norm(txt) for s in STATUS_FORA):
                continue
            m = re.search(r"(\d{2}/\d{2}/\d{4}) às (\d{1,2}:\d{2})", txt)
            if not m:
                continue
            data = datetime.strptime(" ".join(m.groups()), "%d/%m/%Y %H:%M").isoformat()
            href = a["href"].replace(BASE, "")
            h3 = art.find("h3")
            out.append({"id": re.sub(r"\W+", "-", href).strip("-")[-40:], "url": BASE + href, "data": data,
                        "texto": h3.get_text(" ", strip=True) if h3 else href, "origem": "",
                        "avulso": "/oferta/" in href})
        return out

    def listar_lotes(self, leilao: dict, max_paginas: int = 20) -> list[dict]:
        if leilao["avulso"]:
            l = self._oferta(leilao)
            return [l] if l else []
        lotes, vistos = [], set()
        for pag in range(1, max_paginas + 1):
            soup = self._soup(leilao["url"], params={"page": pag} if pag > 1 else None)
            cards = soup.select("div.lote")
            novos = [c for c in cards if c.get("id") not in vistos]
            if not novos:
                break
            vistos.update(c.get("id") for c in novos)
            for c in novos:
                l = self._card(c, leilao)
                if l:
                    lotes.append(l)
        return lotes

    def _base(self, leilao, lote_id, sub, url, titulo):
        return {"id": f"ec:{lote_id}", "fonte": self.nome, "leilao_id": leilao["id"],
                "leilao_titulo": leilao["texto"][:200], "origem": leilao["origem"],
                "leilao_data": leilao["data"], "url": url, **_veiculo(titulo, sub)}

    def _card(self, c, leilao):
        a = c.find("a", href=RE_OFERTA)
        if not a:
            return None  # não é veículo
        sub, lote_id = RE_OFERTA.search(a["href"]).groups()
        txt = c.get_text(" | ", strip=True)
        st = c.select_one(".lote-status")
        if st and any(s in norm(st.get_text()) for s in STATUS_FORA):
            return None
        h3 = c.find("h3")
        titulo = h3.get_text(" ", strip=True) if h3 else ""
        desc = c.select_one(".descricao")
        desc = desc.get_text(" ", strip=True) if desc else ""
        loc = re.search(r"Localização:\s*([^|/]+?)\s*/\s*([A-Z]{2})", c.get_text(" ", strip=True))
        img = re.search(r"url\(([^)]+)\)", str(c))
        d = self._base(leilao, lote_id, sub, BASE + a["href"].replace(BASE, ""), titulo)
        monta, flags = classificar(f"{titulo} {desc}", leilao["origem"])
        num = re.search(r"LOTE\s*(\d+)", txt)
        valor = re.search(r"Valor inicial:\s*\|\s*(R\$ ?[\d\.]+,\d{2})", txt)
        d.update({"numero": num.group(1) if num else None, "observacoes": f"{titulo} {desc}".strip(),
                  "monta": monta, "flags": flags, "foto": img.group(1).strip("'\"") if img else None,
                  "lance_inicial": brl(valor.group(1)) if valor else None, "tem_lance": 0})
        if loc:
            d["cidade"], d["uf"] = loc.group(1).strip(), loc.group(2)
        return d

    def _oferta(self, leilao):
        m = RE_OFERTA.search(leilao["url"])
        if not m:
            return None
        sub, lote_id = m.groups()
        soup = self._soup(leilao["url"])
        og = soup.find("meta", property="og:image")
        foto = og["content"] if og else None
        if not foto:
            m_img = re.search(r"https://static\.suporteleiloes\.com\.br/[^\"' )]+/(?:bens|leiloes)/[^\"' )]+\.(?:jpe?g|png|webp)", str(soup))
            foto = m_img.group(0) if m_img else None
        ls = self.linhas(soup)
        txt = "\n".join(ls)
        titulo = ls[0].split("|")[0].strip() if ls else leilao["texto"]
        d = self._base(leilao, lote_id, sub, leilao["url"], titulo)
        monta, flags = classificar(titulo, leilao["origem"])
        ini = re.search(r"(R\$ ?[\d\.]+,\d{2})\nLance inicial", txt)
        atual = re.search(r"(R\$ ?[\d\.]+,\d{2})\nLance atual", txt, re.I)
        fim = re.search(r"Encerramento:\n(\d{2}/\d{2}/\d{4}) a partir das (\d{1,2}:\d{2})", txt)
        local = re.search(r"LOCAL DE RETIRADA:\s*([^\n]+)", txt)
        num = re.search(r"Lote:\s*(\d+)", txt)
        d.update({"numero": num.group(1) if num else None, "monta": monta, "flags": flags,
                  "observacoes": f"{titulo}. Retirada: {local.group(1).strip()}" if local else titulo,
                  "foto": foto, "lance_inicial": brl(ini.group(1)) if ini else None,
                  "cidade": "Rio de Janeiro", "uf": "RJ", "detalhe_ok": 1, "tem_lance": int(bool(atual))})
        if atual:
            d["lance_atual"] = brl(atual.group(1))
        if fim:
            d["leilao_data"] = datetime.strptime(" ".join(fim.groups()), "%d/%m/%Y %H:%M").isoformat()
        return d

    def detalhar(self, lote: dict) -> dict:
        return {"detalhe_ok": 1}
