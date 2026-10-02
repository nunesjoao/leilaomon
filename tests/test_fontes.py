import pathlib
from bs4 import BeautifulSoup
from leilaomon.fontes.freitas import Freitas
from leilaomon.fontes.joaoemilio import JoaoEmilio

F = pathlib.Path(__file__).parent / "fixtures"
sp = lambda n: BeautifulSoup((F / n).read_text(), "html.parser")

def test_freitas():
    c = Freitas()._cards(sp("freitas_lotes.html"), "moto")
    assert len(c) == 12 and c[0]["id"] == "fr:8082-198" and c[0]["monta"] == "pequena"
    f = Freitas(); f._soup = lambda url, **kw: sp("freitas_detalhe.html")
    d = f.detalhar({"url": "x"})
    assert d["despesas"] == 850 and d["uf"] == "SP" and d["comissao_pct"] == 5

def test_joaoemilio():
    je = JoaoEmilio(); je._soup = lambda url, **kw: sp("je_leiloes.html")
    assert "6212" in [l["id"] for l in je.listar_leiloes()]
    c = je._cards(sp("je_lotes.html"), {"id": "6212", "texto": "", "data": "2099-01-01T00:00:00", "origem": "Multimarcas"})
    assert len(c) == 30 and any(x["_ativo"] for x in c)
    je._soup = lambda url, **kw: sp("je_detalhe.html")
    d = je.detalhar({"url": "x"})
    assert d["lance_atual"] == 45500 and d["despesas"] == 2200 and d["uf"] == "RJ"
