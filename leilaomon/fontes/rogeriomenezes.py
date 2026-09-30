"""Adaptador para www.rogeriomenezes.com.br (plataforma Wtis / suporteleiloes).

Estrutura observada (set/2026):
  - Home: agenda com links /leilao/<id> e texto "dd/mm/aaaa, às HHh ... N VEÍCULOS"
  - /leilao/<id>?page=N: ~20 cards por página, link /lote/<id>/<slug>, preço
    com "Lance inicial" (sem lance) ou "Por: X*****" (maior lance atual)
  - /lote/<id>/<slug>: blocos "Descrição", "Observações" (ex.: "Media monta"), "Lote: N"
O parsing é por texto/âncoras, não por classes CSS, para tolerar mudanças de layout.
"""
import re
import time
from datetime import datetime

import httpx
from bs4 import BeautifulSoup

from ..parsing import brl, classificar, parse_km, parse_titulo

BASE = "https://www.rogeriomenezes.com.br"
PATIO = {"cidade": "Rio de Janeiro", "uf": "RJ", "lat": -22.8854, "lon": -43.6471}  # Av. Brasil 51.467
RE_LEILAO = re.compile(r"/leilao/(\d+)")
RE_LOTE = re.compile(r"/lote/(\d+)")
RE_DATA = re.compile(r"(\d{2})/(\d{2})/(\d{4}),?\s*às\s*(\d{1,2})h(\d{2})?")
PALAVRAS_VEICULO = ("VEÍCULO", "VEICULO", "SUCATA", "MOTO", "CARRO", "CAMINH")


class RogerioMenezes:
    nome = "rogeriomenezes"

    def __init__(self, delay: float = 1.5, timeout: float = 30):
        self.delay = delay
        self.http = httpx.Client(
            timeout=timeout, follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"})

    def _soup(self, url: str) -> BeautifulSoup:
        for tentativa in range(3):
            try:
                r = self.http.get(url)
                r.raise_for_status()
                time.sleep(self.delay)
                return BeautifulSoup(r.text, "html.parser")
            except httpx.HTTPError:
                if tentativa == 2:
                    raise
                time.sleep(5 * (tentativa + 1))

    # ---------- agenda ----------
    def listar_leiloes(self) -> list[dict]:
        soup = self._soup(BASE + "/")
        por_id: dict[str, str] = {}
        for a in soup.find_all("a", href=RE_LEILAO):
            lid = RE_LEILAO.search(a["href"]).group(1)
            txt = a.get_text(" ", strip=True)
            if len(txt) > len(por_id.get(lid, "")):
                por_id[lid] = txt
        leiloes = []
        for lid, txt in por_id.items():
            up = txt.upper()
            if "JUDICIAL" in up or not any(p in up for p in PALAVRAS_VEICULO):
                continue
            m = RE_DATA.search(txt)
            if not m:
                continue
            d, mo, a, h, mi = m.groups()
            data = datetime(int(a), int(mo), int(d), int(h), int(mi or 0))
            origem = "Bancos" if "BANCO" in up else "Seguradoras" if "SEGURADORA" in up else ""
            leiloes.append({"id": lid, "texto": txt, "data": data.isoformat(), "origem": origem})
        return leiloes

    # ---------- listagem ----------
    def listar_lotes(self, leilao: dict, max_paginas: int = 40) -> list[dict]:
        lotes, vistos = [], set()
        for pag in range(1, max_paginas + 1):
            soup = self._soup(f"{BASE}/leilao/{leilao['id']}?page={pag}")
            novos = self._cards(soup, leilao)
            novos = [l for l in novos if l["id"] not in vistos]
            if not novos:
                break
            vistos.update(l["id"] for l in novos)
            lotes.extend(novos)
        return lotes

    def _cards(self, soup: BeautifulSoup, leilao: dict) -> list[dict]:
        out = []
        for card in soup.select("div.lote-item"):
            a = card.find("a", href=RE_LOTE)
            h = card.find(["h3", "h2", "h4"])
            if not a or not h:
                continue
            lote_id = RE_LOTE.search(a["href"]).group(1)
            titulo = h.get_text(" ", strip=True)
            selo = card.select_one("div.img span")
            selo = selo.get_text(" ", strip=True) if selo else ""
            preco = card.select_one(".lance-atual")
            quem = card.select_one(".lance-atual-usuario")
            quem = quem.get_text(" ", strip=True) if quem else ""
            valor = brl(preco.get_text() if preco else card.get_text())
            tem_lance = quem.startswith("Por")
            texto = card.get_text(" ", strip=True)
            monta, flags = classificar(f"{selo} {titulo}", leilao["origem"])
            d = {
                "id": f"rm:{lote_id}", "fonte": self.nome, "leilao_id": leilao["id"],
                "leilao_titulo": leilao["texto"][:200], "origem": leilao["origem"],
                "leilao_data": leilao["data"], "url": BASE + a["href"].replace(BASE, ""),
                "titulo": titulo, "km": parse_km(texto), "tem_lance": int(tem_lance),
                "lance_inicial": valor, "lance_atual": valor,
                **PATIO, **parse_titulo(titulo),
            }
            if monta == "grande":  # selo/título "sucata" já define; detalhe pode refinar
                d["monta"] = monta
            # não sobrescreve com None o campo que a listagem não mostra
            d.pop("lance_inicial" if tem_lance else "lance_atual")
            out.append(d)
        return out

    # ---------- detalhe ----------
    def detalhar(self, lote: dict) -> dict:
        soup = self._soup(lote["url"])
        linhas = [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
        corrido = " ".join(linhas)

        def bloco(inicio, fins):
            try:
                i = linhas.index(inicio)
            except ValueError:
                return ""
            buf = []
            for l in linhas[i + 1:]:
                if l in fins:
                    break
                buf.append(l)
            return " ".join(buf)[:1000]

        descricao = bloco("Descrição", {"Observações", "Valor inicial"})
        obs = bloco("Observações", {"Valor inicial", "Visitação:"})
        num = re.search(r"Lote:\s*(\d+)", corrido)
        monta, flags = classificar(f"{lote.get('titulo', '')} {descricao} {obs}", lote.get("origem", ""))
        m_ini = re.search(r"Lance inicial:\s*\|?\s*R\$\s*([\d\.]+,\d{2})", corrido)
        d = {
            "descricao": descricao, "observacoes": obs, "monta": monta, "flags": flags,
            "numero": num.group(1) if num else None, "detalhe_ok": 1,
            "km": lote.get("km") or parse_km(descricao),
        }
        if m_ini:
            d["lance_inicial"] = brl(m_ini.group(0))
        return d
