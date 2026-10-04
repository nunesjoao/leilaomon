"""Sonda a API de busca do Mesquita (categoria Veículos) e salva a resposta em diag/."""
import json, os, re
import httpx
try:
    import truststore; truststore.inject_into_ssl()
except ImportError:
    pass
B = "https://www.mesquitaleiloes.com.br/"
os.makedirs("diag", exist_ok=True)
c = httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"})
r = c.get(B + "busca/")
tok = re.search(r'name="__RequestVerificationToken" type="hidden" value="([^"]+)"', r.text)
item = {"Scopo": 1, "Busca": "", "Mapa": "", "ID_Categoria": 65, "Pagina": 1, "PaginaIndex": 1, "QtdPorPagina": 48,
        "Ordem": 0, "TiposLeiloes": [], "Filtro": {}}
out = {}
for hdr in ["RequestVerificationToken", "X-CSRF-TOKEN"]:
    resp = c.post(B + "ApiEngine/GetBusca/1/1/0", json=item,
                  headers={hdr: tok.group(1) if tok else "", "X-Requested-With": "XMLHttpRequest"})
    out[hdr] = {"status": resp.status_code, "body": resp.text[:200000]}
    if resp.status_code == 200:
        break
f = open(os.path.join("..", "Ajax_Funcoes.js"), "w") if False else None
js = c.get(B + "Core/V1/js/Ajax/Ajax_Funcoes.js").text
m = re.search(r"ajaxAntiForgerySetup[\s\S]{0,600}", js)
out["antiforgery_js"] = m.group(0) if m else None
out["token_ok"] = bool(tok)
json.dump(out, open("diag/mesquita.json", "w", encoding="utf-8"), ensure_ascii=False)
print({k: (v["status"] if isinstance(v, dict) else v) for k, v in out.items() if k != "antiforgery_js"})
