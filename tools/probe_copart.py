"""Sonda Copart BR v2: formato de filtro e paginação de /public/lots/search."""
import json, os, traceback
import httpx
UA = {"User-Agent": "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"}
os.makedirs("diag", exist_ok=True)
B = "https://www.copart.com.br/public/lots/search"
hdr = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"}
F = 'dataleilao:"06/10/2026 14:00:00"'
variantes = {
    "base": {"query": "*"},
    "size100": {"query": "*", "size": "100"},
    "length100": {"query": "*", "start": "0", "length": "100"},
    "page1": {"query": "*", "page": "1"},
    "start10": {"query": "*", "start": "10"},
    "filtro_colchete": {"query": "*", "filter[dataleilao]": F},
    "filtro_FILTER": {"query": "*", "filter[MISC]": F},
    "fq": {"query": "*", "fq": F},
    "query_facet": {"query": F},
    "upcoming": {"query": "*", "filter[patioleilao]": '-patioleilao:"Não Preenchido"'},
}
res = {}
c = httpx.Client(timeout=40, headers=UA)
c.get("https://www.copart.com.br/")
for k, data in variantes.items():
    try:
        r = c.post(B, data=data, headers=hdr)
        j = r.json()["data"]["results"]
        res[k] = {"status": r.status_code, "total": j["totalElements"], "n": len(j["content"]),
                  "first": [x["ln"] for x in j["content"][:3]], "ad": [x.get("ad") for x in j["content"][:3]],
                  "q": r.json()["data"]["query"]}
    except Exception:
        res[k] = traceback.format_exc()[-400:]
# JSON no corpo
try:
    r = c.post(B, json={"query": ["*"], "filter": {"MISC": [F]}, "page": 0, "size": 100}, headers=hdr)
    j = r.json()["data"]["results"]; res["json_body"] = {"total": j["totalElements"], "n": len(j["content"])}
except Exception:
    res["json_body"] = traceback.format_exc()[-300:]
open("diag/copart_probe2.json", "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps(res, ensure_ascii=False)[:3000])
