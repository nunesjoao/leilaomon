"""Sondas: VIP (/pesquisa) e Mesquita (ApiEngine/GetBusca). Salva em diag/."""
import json, os, re
import httpx
try:
    import truststore; truststore.inject_into_ssl()
except ImportError:
    pass
UA = {"User-Agent": "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"}
os.makedirs("diag", exist_ok=True)
res = {}

# ---- VIP
c = httpx.Client(follow_redirects=True, timeout=40, headers=UA)
B = "https://www.vipleiloes.com.br"
tent = {
    "get_index": ("GET", B + "/pesquisa/index", {"Filtro.SelecaoVeiculos": "true", "Filtro.CurrentPage": "2"}),
    "get_pesq": ("GET", B + "/pesquisa", {"Filtro.SelecaoVeiculos": "true", "Filtro.CurrentPage": "2"}),
    "post_pesq": ("POST", B + "/pesquisa", {"Filtro.SelecaoVeiculos": "true", "Filtro.SelecaoOutros": "false", "Filtro.CurrentPage": "2"}),
    "classif": ("GET", B + "/pesquisa", {"classificacao": "Motos"}),
}
for k, (m, u, p) in tent.items():
    try:
        r = c.get(u, params=p) if m == "GET" else c.post(u, data=p)
        n = len(re.findall(r'class="crd-link"', r.text))
        ids = re.findall(r'/evento/anuncio/[a-z0-9\-]+-(\d+)"', r.text)
        res["vip_" + k] = {"status": r.status_code, "cards": n, "ids": sorted(set(ids))[:8], "len": len(r.text)}
        open(f"diag/vip_{k}.html", "w", encoding="utf-8").write(r.text)
    except Exception as e:
        res["vip_" + k] = repr(e)

# ---- Mesquita
M = "https://www.mesquitaleiloes.com.br/"
c2 = httpx.Client(follow_redirects=True, timeout=40, headers=UA)
r = c2.get(M + "busca/")
tok = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', r.text).group(1)
base = {"RangeValores": "", "Scopo": "1", "IgnoreScopo": "", "OrientacaoBusca": "0", "Mapa": "", "Busca": "",
        "ID_Categoria": "65", "ID_Estado": "", "ID_Cidade": "", "Bairro": "", "ID_Regiao": "",
        "ValorMinSelecionado": "", "ValorMaxSelecionado": "", "CFGs": "", "Pagina": "1", "sInL": "",
        "Ordem": "0", "OrdSt": "", "QtdPorPagina": "24", "SubStatus": "", "ID_Leiloes_Status": "",
        "PaginaIndex": "1", "BuscaProcesso": "", "NomesPartes": "", "CodLeilao": "", "TiposLeiloes": "[]",
        "PracaAtual": "", "DataAbertura": "", "DataEncerramento": "", "Filtro": {}}
h = {"RequestVerificationToken": tok, "X-Requested-With": "XMLHttpRequest", "Referer": M + "busca/"}
for k, body in {"full_str": base, "full_num": {**base, "Scopo": 1, "ID_Categoria": 65, "Pagina": 1, "PaginaIndex": 1, "QtdPorPagina": 24}}.items():
    rr = c2.post(M + "ApiEngine/GetBusca/1/1/0", content=json.dumps(body), headers={**h, "Content-Type": "application/json; charset=utf-8"})
    res["mq_" + k] = {"status": rr.status_code, "len": len(rr.text), "head": rr.text[:300], "ct": rr.headers.get("content-type")}
    open(f"diag/mq_{k}.json", "w", encoding="utf-8").write(rr.text)
json.dump(res, open("diag/probe.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])
