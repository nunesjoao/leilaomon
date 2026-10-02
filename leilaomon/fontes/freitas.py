"""Freitas Leiloeiro (www.freitasleiloeiro.com.br).

A busca de veículos carrega os lotes por AJAX em /Leiloes/PesquisarLotes (HTML parcial com
.cardlote: número, data/hora, descrição, valor, origem/condição e status). A página do lote
traz comissão, despesas operacionais/logística e o pátio de retirada (cidade/UF).
Cadeia TLS incompleta no servidor: requer truststore (repositório de certificados do SO).
Só responde a IPs residenciais brasileiros — roda no executor 'residencial'.
"""
import re
from datetime import datetime

from ..parsing import ano4, brl, classificar, combustivel_de, norm
from .base import Fonte

BASE = "https://www.freitasleiloeiro.com.br"
TIPOS = {"carro": 1, "moto": 3}
STATUS_OK = ("ABERTO", "EM BREVE", "AGUARDANDO", "PREGAO", "PREGÃO", "LOTEAMENTO")


class Freitas(Fonte):
    nome = "freitas"

    def listar_leiloes(self) -> list[dict]:
        # a busca já é transversal a todos os leilões; um "leilão" por tipo de veículo
        return [{"id": tipo, "tipo_lote": tid, "texto": f"Freitas {tipo}", "origem": "", "data": None}
                for tipo, tid in TIPOS.items()]

    def listar_lotes(self, leilao: dict, max_paginas: int = 30) -> list[dict]:
        lotes, vistos = [], set()
        for pag in range(1, max_paginas + 1):
            params = {"Nome": "", "Categoria": 1, "TipoLoteId": leilao["tipo_lote"], "FaixaValor": 0,
                      "Condicao": "", "PatioId": 0, "AnoModeloMin": 0, "AnoModeloMax": 0,
                      "ArCondicionado": "false", "DirecaoAssistida": "false", "Tag": "", "Estado": "",
                      "Cidade": "", "ClienteSclId": 0, "PageNumber": pag, "TopRows": 48}
            soup = self._soup(BASE + "/Leiloes/PesquisarLotes", params=params)
            novos = [l for l in self._cards(soup, leilao["id"]) if l["id"] not in vistos]
            if not novos:
                break
            vistos.update(l["id"] for l in novos)
            lotes.extend(l for l in novos if l.pop("_ativo"))
        return lotes

    def _cards(self, soup, tipo) -> list[dict]:
        out = []
        for c in soup.select("div.cardlote"):
            a = c.find("a", href=re.compile(r"LoteDetalhes"))
            if not a:
                continue
            m = re.search(r"leilaoId=(\d+)&(?:amp;)?loteNumero=(\d+)", a["href"])
            if not m:
                continue
            leilao_id, num = m.groups()
            data = [s.get_text(strip=True) for s in c.select(".cardLote-data span")]
            try:
                quando = datetime.strptime(" ".join(data[:2]), "%d/%m/%Y %H:%M").isoformat()
            except ValueError:
                continue
            desc = c.select_one(".cardLote-descVeic")
            desc = desc.get_text(" ", strip=True) if desc else ""
            det = c.select_one(".cardLote-details span")
            det_partes = [x.strip() for x in det.get_text("|", strip=True).split("|")] if det else []
            origem = det_partes[0] if det_partes else ""
            condicao = " ".join(det_partes[1:])
            status = c.select_one(".cardLote-btn")
            status = status.get_text(" ", strip=True).upper() if status else ""
            vlr = brl(c.select_one(".cardLote-vlr").get_text()) if c.select_one(".cardLote-vlr") else None
            rotulo = c.select_one(".cardLote-lance")
            tem_lance = bool(rotulo and "maior" in rotulo.get_text().lower())
            img = c.select_one("img.cardLote-img")

            desc = re.sub(r"^I\s*/\s*", "", desc)  # importado
            partes = [p.strip() for p in desc.split(",")]
            marca, _, modelo = partes[0].partition("/") if partes else ("", "", "")
            anos = next((re.match(r"(\d{2,4})/(\d{2,4})$", p) for p in partes if re.match(r"\d{2,4}/\d{2,4}$", p)), None)
            km = next((int(re.sub(r"\D", "", p)) for p in partes if re.search(r"\bKM\b", norm(p))), None)
            monta, flags = classificar(condicao, origem)
            d = {
                "id": f"fr:{leilao_id}-{num}", "fonte": self.nome, "leilao_id": leilao_id,
                "leilao_titulo": f"Freitas leilão {leilao_id}", "origem": origem.title(),
                "leilao_data": quando, "url": f"{BASE}/Leiloes/LoteDetalhes?leilaoId={leilao_id}&loteNumero={num}",
                "numero": num, "titulo": f"{'MOTO ' if tipo == 'moto' else ''}{desc}", "tipo": tipo,
                "marca": norm(marca), "modelo": norm(modelo), "combustivel": combustivel_de(desc),
                "ano_fab": ano4(anos.group(1)) if anos else None, "ano_mod": ano4(anos.group(2)) if anos else None,
                "km": km, "foto": img.get("src") if img else None, "monta": monta, "flags": flags,
                "observacoes": condicao, "tem_lance": int(tem_lance),
                "lance_atual" if tem_lance else "lance_inicial": vlr,
                "_ativo": any(s in status for s in STATUS_OK),
            }
            out.append(d)
        return out

    def detalhar(self, lote: dict) -> dict:
        ls = self.linhas(self._soup(lote["url"]))
        txt = "\n".join(ls)
        d = {"detalhe_ok": 1}
        m = re.search(r"\n(\d+(?:,\d+)?)%\nreferente à comissão", txt)
        if m:
            d["comissao_pct"] = float(m.group(1).replace(",", "."))
        desp = [brl(x) for x in re.findall(r"Despesas [^\n]*no valor de\n(R\$ ?[\d\.]+,\d{2})", txt)]
        if desp:
            d["despesas"] = sum(desp)
        m = re.search(r"Visitação/Retirada:\n([^\n]+)", txt)
        if m:
            loc = re.search(r"-\s*([A-ZÀ-Úa-zà-ú .']+?)\s*/\s*([A-Z]{2})\s*$", m.group(1))
            if loc:
                d["cidade"], d["uf"] = loc.group(1).strip().title(), loc.group(2)
        m = re.search(r"\n(R\$ ?[\d\.]+,\d{2})\nLance Inicial", txt)
        if m:
            d["lance_inicial"] = brl(m.group(1))
        return d
