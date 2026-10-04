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
    assert d["lance_atual"] == 45500 and d["despesas"] == 2200 


def test_apl():
    from leilaomon.fontes.apl import APL
    a = APL(); a._soup = lambda url, **kw: sp("apl_home.html")
    L = a.listar_leiloes()
    assert len(L) >= 10 and L[0]["data"]
    c = a._cards(sp("apl_leilao.html"), L[0])
    assert len(c) == 46 and c[1]["marca"] == "HONDA" and c[1]["monta"] == "conservado" and c[1]["cidade"] == "Teresópolis"

def test_edgar():
    from leilaomon.fontes.edgarcarvalho import EdgarCarvalho
    e = EdgarCarvalho()
    e._soup = lambda url, **kw: sp("ec_oferta.html" if "/oferta/" in url else "ec_leiloes.html")
    L = e.listar_leiloes()
    assert len(L) == 1 and L[0]["avulso"]
    l = e.listar_lotes(L[0])[0]
    assert l["lance_inicial"] == 20000 and l["ano_mod"] == 2010 and l["leilao_data"].startswith("2026-10-12")


def test_vip():
    from leilaomon.fontes.vip import VIP
    c = VIP()._cards(sp("vip_pesquisa.html"), {"id": "carro-m3", "tipo": "carro", "monta": "3"})
    assert len(c) == 12 and c[0]["marca"] == "FIAT" and c[0]["ano_mod"] == 2025 and c[0]["uf"] == "RJ"
    assert c[0]["lance_atual"] == 23000 and c[0]["lance_inicial"] == 21000 and c[0]["monta"] == "media"
