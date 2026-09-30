"""Salva HTML bruto e status HTTP em diag/ para depurar o adaptador."""
import os
import re

from .fontes.rogeriomenezes import BASE, RogerioMenezes


def main():
    os.makedirs("diag", exist_ok=True)
    rm = RogerioMenezes(delay=1)
    urls = {"home": BASE + "/"}
    r = rm.http.get(urls["home"])
    print("home", r.status_code, r.headers.get("server"), len(r.text))
    open("diag/home.html", "w").write(r.text)
    ids = re.findall(r"/leilao/(\d+)", r.text)
    print("links /leilao/:", len(ids), sorted(set(ids))[:20])
    for nome, url in [("leilao", f"{BASE}/leilao/1627"), ("lote", f"{BASE}/lote/143743/x")]:
        r = rm.http.get(url)
        print(nome, r.status_code, len(r.text), "lotes:", len(set(re.findall(r"/lote/(\d+)", r.text))))
        open(f"diag/{nome}.html", "w").write(r.text)
    try:
        print("listar_leiloes ->", rm.listar_leiloes())
    except Exception as e:  # noqa: BLE001
        print("listar_leiloes ERRO", repr(e))


if __name__ == "__main__":
    main()
