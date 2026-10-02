from bs4 import BeautifulSoup
from leilaomon.parsing import parse_titulo, classificar, brl, parse_km
from leilaomon.fontes.rogeriomenezes import RogerioMenezes
from leilaomon.avaliacao import avaliar, casa

def test_titulos():
    t = parse_titulo("MOTO KAWASAKI NINJA ZX-6R 2025/2025 GASOLINA")
    assert (t["tipo"], t["marca"], t["modelo"], t["ano_mod"], t["combustivel"]) == ("moto","KAWASAKI","NINJA ZX-6R",2025,"gasolina")
    t = parse_titulo("HYUNDAI HYUNDAI CRETA PULSE 1.6 16V FLEX AUT. 2017 2017/2017 FLEX")
    assert t["marca"] == "HYUNDAI" and t["modelo"] == "CRETA PULSE 1.6 16V AUT." and t["ano_mod"] == 2017
    t = parse_titulo("VW - VOLKSWAGEN JETTA 2.0T 2013/2013 GASOLINA")
    assert t["marca"] == "VW - VOLKSWAGEN" and t["modelo"] == "JETTA 2.0T"
    t = parse_titulo("CAOA CHERY TIGGO 8 PHEV 1.5 2022/2023 HíBRIDO")
    assert t["marca"] == "CAOA CHERY" and t["combustivel"] == "hibrido" and t["ano_fab"] == 2022
    assert parse_titulo("CAMINHÃO MERCEDES-BENZ ACTROS 2548S 2021/2021 DIESEL")["tipo"] == "caminhao"

def test_classificar():
    assert classificar("Media monta")[0] == "media"
    assert classificar("SUCATA SEM APROVEITAMENTO")[0] == "grande"
    assert classificar("", "Bancos")[0] == "conservado"
    assert classificar("chassi remarcado, sem chave")[1] == ["remarcado", "sem_chave"]
    assert brl("R$ 31.000,00") == 31000.0 and parse_km("com 5.879km") == 5879

def test_cards_real():
    import pathlib
    html = pathlib.Path(__file__).parent.parent.joinpath("tests/fixtures/rm_leilao.html").read_text()
    lei = {"id": "1627", "texto": "x", "data": "2099-10-05T13:00:00", "origem": "Seguradoras"}
    c = RogerioMenezes()._cards(BeautifulSoup(html, "html.parser"), lei)
    assert len(c) == 20 and all(x["titulo"] for x in c)
    assert all((x.get("lance_inicial") or x.get("lance_atual")) for x in c)

CFG = {"destino": {"lat": -22.9, "lon": -43.2},
       "frete": {"fator_rodoviario": 1.3, "raio_local_km": 80, "sem_local": 1500,
                 "carro": {"local": 400, "rs_km": 4.5, "minimo": 600}, "moto": {"local": 250, "rs_km": 2.5, "minimo": 400}},
       "custos": {"comissao_pct": 5, "taxa_adm": 0, "transferencia": 400,
                  "regularizacao": {"media": 1500}, "desagio_mercado": {"media": 0.30}}}

def test_avaliar():
    l = {"lance_atual": None, "lance_inicial": 31000, "monta": "media", "lat": -22.8854, "lon": -43.6471,
         "tipo": "moto", "fipe_valor": 70000, "comissao_pct": None, "despesas": None}
    r = avaliar(l, CFG)
    assert r["custo_total"] == 31000*1.05 + 250 + 1500 + 400
    assert abs(r["desconto"] - (1 - r["custo_total"]/49000)) < 1e-3
    lote = {**l, **r, "flags": "[]", "marca": "KAWASAKI", "titulo": "x", "ano_mod": 2025, "km": 5879}
    assert casa(lote, {"tipos": ["moto"], "desconto_min": 0.2})
    assert not casa(lote, {"tipos": ["carro"]})
