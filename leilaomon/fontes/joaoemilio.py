"""João Emílio Leiloeiro (www.joaoemilio.com.br) — plataforma SOLEON.

  /leiloes: cards .box-leilao com /leilao/<id>/lotes, título, "Data: dd/mm/aaaa", "Início do leilão às HH:MM"
  /leilao/<id>/lotes?page=N: div.lote (classe = status), "Lote N", /item/<id>/detalhes, h5 título,
     Marca/Modelo, Ano/Modelo, Combustível, foto em background-image; sem preço na listagem
  /item/<id>/detalhes: maior lance, lance inicial, comissão %, despesas R$, cidade-UF, data do leilão
Atrás de Cloudflare: só responde sem desafio a IP residencial — roda no executor 'residencial'.
"""
import re
from datetime import datetime

from ..parsing import ano4, brl, classificar, combustivel_de, eh_moto, norm
from .base import Fonte

BASE = "https://www.joaoemilio.com.br"
# a cidade que aparece na página do lote é a do licitante, não do veículo; usa o pátio
PATIO = {"cidade": "Rio de Janeiro", "uf": "RJ", "lat": -22.985, "lon": -43.43}  # Estr. dos Bandeirantes
INCLUI = re.compile(r"VEIC|VEÍC|MULTIMARCA|MOTO|SINISTR|SEGUR|FROTA|CARRO|AUTOM|SUCATA|RECUPERAD|FINANC", re.I)
EXCLUI = re.compile(r"EMPILHADEIRA|M[OÓ]VEIS|MOBILI|EQUIPAMENTO|IM[OÓ]VE|AERON|TRANSFORMADOR|CAMINH|PESADOS", re.I)
STATUS_FORA = ("vendido", "sustado", "retirado", "cancelado", "condicional", "encerrado", "nao_vendido")


class JoaoEmilio(Fonte):
    nome = "joaoemilio"

    def listar_leiloes(self) -> list[dict]:
        soup = self._soup(BASE + "/leiloes")
        out = {}
        for card in soup.select(".box-leilao"):
            a = card.find("a", href=re.compile(r"/leilao/\d+/lotes"))
            if not a:
                continue
            lid = re.search(r"/leilao/(\d+)/", a["href"]).group(1)
            txt = card.get_text(" ", strip=True)
            titulo = card.select_one(".card-title")
            titulo = titulo.get_text(" ", strip=True) if titulo else ""
            m = re.search(r"(\d{2}/\d{2}/\d{4}).*?às\s*(\d{1,2}:\d{2})", txt)
            if not m or not INCLUI.search(txt) or EXCLUI.search(titulo):
                continue
            data = datetime.strptime(f"{m.group(1)} {m.group(2)}", "%d/%m/%Y %H:%M")
            out[lid] = {"id": lid, "texto": txt[:200], "data": data.isoformat(),
                        "origem": titulo.title()}
        return list(out.values())

    def listar_lotes(self, leilao: dict, max_paginas: int = 20) -> list[dict]:
        lotes, vistos = [], set()
        for pag in range(1, max_paginas + 1):
            soup = self._soup(f"{BASE}/leilao/{leilao['id']}/lotes", params={"page": pag})
            novos = [l for l in self._cards(soup, leilao) if l["id"] not in vistos]
            if not novos:
                break
            vistos.update(l["id"] for l in novos)
            lotes.extend(l for l in novos if l.pop("_ativo"))
        return lotes

    def _cards(self, soup, leilao) -> list[dict]:
        out = []
        for c in soup.select("div.lote"):
            a = c.find("a", href=re.compile(r"/item/\d+/detalhes"))
            num = c.find("h4")
            m_num = re.search(r"\d+", num.get_text()) if num else None
            st = c.select_one(".label_lote")
            status = st.get_text(" ", strip=True) if st else ""
            classes = " ".join(c.get("class", []))
            ativo = bool(a) and not any(s in norm(status).lower().replace(" ", "_") or s in classes
                                        for s in STATUS_FORA)
            item_id = re.search(r"/item/(\d+)/", a["href"]).group(1) if a else f"x{m_num.group(0) if m_num else ''}"
            h5 = c.find("h5")
            titulo = h5.get_text(" ", strip=True) if h5 else ""
            p = c.find("p")
            ptxt = p.get_text(" ", strip=True) if p else ""
            mm = re.search(r"Marca/Modelo:\s*(.+?)\s*(Placa:|Ano/Modelo:|Cor:|$)", ptxt)
            mm = mm.group(1) if mm else titulo
            mm = re.sub(r"^_/_\s*", "", mm)
            if " - " in mm and "/" not in mm.split(" - ")[0]:
                marca, _, modelo = mm.partition(" - ")
            else:
                marca, _, modelo = mm.partition("/")
            anos = re.search(r"Ano/Modelo:\s*(\d{2,4})\s*/\s*(\d{2,4})", ptxt)
            comb = re.search(r"Combust[ií]vel:\s*([A-Z/ ]+)", ptxt)
            foto = re.search(r"url\('([^']+)'\)", str(c))
            # selo "Sucata" aparece antes de Marca/Modelo
            monta, flags = classificar(f"{titulo} {ptxt.split('Marca/Modelo')[0]}", leilao["origem"])
            tipo = "moto" if eh_moto(marca, modelo) else "carro"
            out.append({
                "id": f"je:{item_id}", "fonte": self.nome, "leilao_id": leilao["id"],
                "leilao_titulo": leilao["texto"], "origem": leilao["origem"], "leilao_data": leilao["data"],
                "url": f"{BASE}/item/{item_id}/detalhes", "numero": m_num.group(0) if m_num else None,
                "titulo": f"{'MOTO ' if tipo == 'moto' else ''}{norm(marca)} {norm(modelo)} "
                          f"{anos.group(1) if anos else ''}/{anos.group(2) if anos else ''}".strip(),
                "tipo": tipo, "marca": norm(marca), "modelo": norm(modelo),
                "ano_fab": ano4(anos.group(1)) if anos else None, "ano_mod": ano4(anos.group(2)) if anos else None,
                "combustivel": combustivel_de(comb.group(1)) if comb else None,
                "foto": foto.group(1) if foto else None, "monta": monta, "flags": flags,
                "observacoes": titulo, "_ativo": ativo, **PATIO,
            })
        return out

    def detalhar(self, lote: dict) -> dict:
        ls = self.linhas(self._soup(lote["url"]))
        txt = "\n".join(ls)
        d = {"detalhe_ok": 1}
        m = re.search(r"MAIOR LANCE NO MOMENTO\n(R\$ ?[\d\.]+,\d{2})", txt)
        if m:
            d["lance_atual"], d["tem_lance"] = brl(m.group(1)), 1
        m = re.search(r"Lance Inicial:\n(R\$ ?[\d\.]+,\d{2})", txt)
        if m:
            d["lance_inicial"] = brl(m.group(1))
        m = re.search(r"Comiss[aã]o:\s*(\d+(?:,\d+)?)%", txt)
        if m:
            d["comissao_pct"] = float(m.group(1).replace(",", "."))
        m = re.search(r"Despesas:\s*(R\$ ?[\d\.]+,\d{2})", txt)
        if m:
            d["despesas"] = brl(m.group(1))
        m = re.search(r"Data do Leil[aã]o:\n(\d{2}/\d{2}/\d{4} \d{1,2}:\d{2})", txt)
        if m:
            d["leilao_data"] = datetime.strptime(m.group(1), "%d/%m/%Y %H:%M").isoformat()
        return d
