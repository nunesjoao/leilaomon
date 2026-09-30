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

LISTA = """<div class=lista>
<div class=card><a href="/lote/143743/x">#</a><h3><a href="/lote/143743/moto-kawasaki">MOTO KAWASAKI NINJA ZX-6R 2025/2025 GASOLINA</a></h3>
<p>com 5.879km</p><img src=a.png><div><span>R$ 31.000,00</span><small>Lance inicial</small></div></div>
<div class=card><a href="/lote/143757/x">#</a><h3><a href="/lote/143757/honda-city">HONDA CITY SEDAN 2018/2018 FLEX</a></h3>
<p>Ar, vidro, direção, automatico com 31.196km</p><div><span>R$ 41.000,00</span><small>Por: F*****</small></div></div>
</div>"""

def test_cards():
    lei = {"id": "1626", "texto": "Seguradoras", "data": "2099-10-01T13:00:00", "origem": "Seguradoras"}
    c = RogerioMenezes()._cards(BeautifulSoup(LISTA, "html.parser"), lei)
    assert [x["id"] for x in c] == ["rm:143743", "rm:143757"]
    assert c[0]["lance_inicial"] == 31000 and "lance_atual" not in c[0] and c[0]["km"] == 5879
    assert c[1]["lance_atual"] == 41000 and c[1]["tem_lance"] == 1

CFG = {"destino": {"lat": -22.9, "lon": -43.2},
       "frete": {"fator_rodoviario": 1.3, "raio_local_km": 80, "sem_local": 1500,
                 "carro": {"local": 400, "rs_km": 4.5, "minimo": 600}, "moto": {"local": 250, "rs_km": 2.5, "minimo": 400}},
       "custos": {"comissao_pct": 5, "taxa_adm": 0, "transferencia": 400,
                  "regularizacao": {"media": 1500}, "desagio_mercado": {"media": 0.30}}}

def test_avaliar():
    l = {"lance_atual": None, "lance_inicial": 31000, "monta": "media", "lat": -22.8854, "lon": -43.6471,
         "tipo": "moto", "fipe_valor": 70000}
    r = avaliar(l, CFG)
    assert r["custo_total"] == 31000*1.05 + 250 + 1500 + 400
    assert abs(r["desconto"] - (1 - r["custo_total"]/49000)) < 1e-3
    lote = {**l, **r, "flags": "[]", "marca": "KAWASAKI", "titulo": "x", "ano_mod": 2025, "km": 5879}
    assert casa(lote, {"tipos": ["moto"], "desconto_min": 0.2})
    assert not casa(lote, {"tipos": ["carro"]})
