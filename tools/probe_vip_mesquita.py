"""Sondas: VIP (/pesquisa?handler=pesquisar) e Mesquita (ApiEngine/GetBusca com ajuste automático de tipos)."""
import json, os, re, traceback
import httpx
try:
    import truststore; truststore.inject_into_ssl()
except ImportError:
    pass
UA = {"User-Agent": "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"}
os.makedirs("diag", exist_ok=True)
res = {}
try:
    c = httpx.Client(follow_redirects=True, timeout=40, headers=UA)
    B = "https://www.vipleiloes.com.br"
    c.get(B + "/pesquisa")
    p = {"handler": "pesquisar", "Filtro.CurrentPage": "1", "Filtro.SelecaoVeiculos": "true", "Filtro.SelecaoOutros": "false",
         "Filtro.SomenteDestaques": "false", "Filtro.Financiavel": "false", "Filtro.OrdenarPor": "DataInicio"}
    for k, req in {"get": lambda: c.get(B + "/pesquisa", params=p, headers={"X-Requested-With": "XMLHttpRequest"}),
                   "get_p2": lambda: c.get(B + "/pesquisa", params={**p, "Filtro.CurrentPage": "2"}, headers={"X-Requested-With": "XMLHttpRequest"}),
                   "post": lambda: c.post(B + "/pesquisa?handler=pesquisar", data={k2: v for k2, v in p.items() if k2 != "handler"},
                                          headers={"X-Requested-With": "XMLHttpRequest"})}.items():
        r = req()
        res["vip_" + k] = {"status": r.status_code, "cards": r.text.count('class="crd-link"'),
                           "ids": sorted(set(re.findall(r'/evento/anuncio/[a-z0-9\-]+-(\d+)"', r.text)))[:6], "len": len(r.text)}
        open(f"diag/vip_{k}.html", "w", encoding="utf-8").write(r.text)
except Exception:
    res["vip_erro"] = traceback.format_exc()

try:
    M = "https://www.mesquitaleiloes.com.br/"
    c2 = httpx.Client(follow_redirects=True, timeout=40, headers=UA)
    r = c2.get(M + "busca/")
    tok = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', r.text).group(1)
    body = {"Scopo": 1, "Busca": "", "Mapa": "", "ID_Categoria": 65, "Pagina": 1, "PaginaIndex": 1, "QtdPorPagina": 24,
            "Ordem": 0, "Filtro": {}}
    h = {"RequestVerificationToken": tok, "X-Requested-With": "XMLHttpRequest", "Referer": M + "busca/",
         "Content-Type": "application/json; charset=utf-8"}
    tent = []
    for _ in range(25):
        rr = c2.post(M + "ApiEngine/GetBusca/1/1/0", content=json.dumps(body), headers=h)
        tent.append({"status": rr.status_code, "len": len(rr.text), "head": rr.text[:400]})
        if rr.status_code != 400:
            break
        m = re.search(r'"\$\.(\w+)":\["The JSON value could not be converted to System\.(\w+)', rr.text)
        if not m:
            break
        campo, tipo = m.groups()
        body[campo] = {"Int32": 0, "Int64": 0, "Boolean": False, "String": "", "Decimal": 0, "Double": 0}.get(tipo, None)
    res["mq_tentativas"] = tent
    res["mq_body_final"] = body
    open("diag/mq_resp.json", "w", encoding="utf-8").write(rr.text)
    # sem corpo vazio? tentar também sem Filtro e com ID_Categoria string
except Exception:
    res["mq_erro"] = traceback.format_exc()
json.dump(res, open("diag/probe.json", "w"), ensure_ascii=False, indent=1)
print("ok")
