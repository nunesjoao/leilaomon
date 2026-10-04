"""Sonda Copart BR: descobre endpoints públicos usados pelo front (Angular) e testa a busca."""
import json, os, re, traceback
import httpx
UA = {"User-Agent": "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"}
os.makedirs("diag", exist_ok=True)
B = "https://www.copart.com.br"
res = {}
try:
    c = httpx.Client(follow_redirects=True, timeout=40, headers=UA)
    h = c.get(B + "/")
    res["home"] = [h.status_code, len(h.text)]
    js = sorted(set(re.findall(r'src="(/dist/[^"]+\.js)"', h.text)))
    res["js"] = js
    eps = set()
    for j in js:
        t = c.get(B + j).text
        eps.update(re.findall(r'["\'](/?public/[A-Za-z0-9_\-/{}]+)["\']', t))
        eps.update(re.findall(r'["\'](/?data/[A-Za-z0-9_\-/{}]+)["\']', t))
    res["endpoints"] = sorted(eps)[:200]
    corpo = {"query": ["*"], "filter": {}, "sort": ["auction_date_type desc", "auction_date_utc asc"],
             "page": 0, "size": 20, "start": 0, "watchListOnly": False, "freeFormSearch": False,
             "hideImages": False, "defaultSort": False, "specificRowProvided": False, "displayName": "",
             "searchName": "", "backUrl": "", "includeTagByField": {}, "rawParams": {}}
    hdr = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"}
    for nome, req in {
        "search_results_json": lambda: c.post(B + "/public/lots/search-results", json=corpo, headers=hdr),
        "search_form": lambda: c.post(B + "/public/lots/search", data={"draw": "1", "start": "0", "length": "20", "query": "*"}, headers=hdr),
        "vehicle_finder": lambda: c.post(B + "/public/vehicleFinder/search", data={"draw": "1", "start": "0", "length": "20"}, headers=hdr),
    }.items():
        try:
            r = req()
            res[nome] = {"status": r.status_code, "ctype": r.headers.get("content-type"), "len": len(r.text), "ini": r.text[:400]}
            open(f"diag/copart_{nome}.txt", "w", encoding="utf-8").write(r.text)
        except Exception as e:  # noqa: BLE001
            res[nome] = repr(e)
except Exception:
    res["erro"] = traceback.format_exc()
open("diag/copart_probe.json", "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps({k: (v if k != "endpoints" else len(v)) for k, v in res.items()}, ensure_ascii=False)[:3000])
