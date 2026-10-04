"""Sonda Copart BR v3: ordenação por data de leilão e mensagem de erro dos filtros."""
import json, os, traceback
import httpx
UA = {"User-Agent": "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"}
os.makedirs("diag", exist_ok=True)
B = "https://www.copart.com.br/public/lots/search"
hdr = {"X-Requested-With": "XMLHttpRequest", "Accept": "application/json, text/plain, */*"}
F = 'dataleilao:"06/10/2026 14:00:00"'
variantes = {
    "erro_filtro": {"query": "*", "filter[dataleilao]": F},
    "sort_ad": {"query": "*", "size": "20", "sort": "auction_date_utc asc"},
    "sort_ad_desc": {"query": "*", "size": "20", "sort": "auction_date_utc desc"},
    "sort_type": {"query": "*", "size": "20", "sort": "auction_date_type desc,auction_date_utc asc"},
    "order_col": {"query": "*", "size": "20", "order[0][column]": "8", "order[0][dir]": "asc"},
    "upcoming_flag": {"query": "*", "size": "20", "showUpComing": "false"},
    "filter_MISC_upcoming": {"query": "*", "size": "20", "filter[MISC]": "#VehicleTypeCode:VEHTYPE_V,#LotYear:[2018 TO 2027]"},
}
res = {}
c = httpx.Client(timeout=40, headers=UA)
c.get("https://www.copart.com.br/")
for k, data in variantes.items():
    try:
        r = c.post(B, data=data, headers=hdr)
        J = r.json()
        j = J["data"].get("results")
        if j is None:
            res[k] = {"status": r.status_code, "resp": json.dumps(J, ensure_ascii=False)[:500]}
            continue
        res[k] = {"status": r.status_code, "total": j["totalElements"], "n": len(j["content"]),
                  "ad": [x.get("ad") or x.get("adf") or "" for x in j["content"][:8]],
                  "yn": [x.get("yn") for x in j["content"][:3]]}
    except Exception:
        res[k] = traceback.format_exc()[-400:]
open("diag/copart_probe3.json", "w", encoding="utf-8").write(json.dumps(res, ensure_ascii=False, indent=1))
print(json.dumps(res, ensure_ascii=False)[:3000])
