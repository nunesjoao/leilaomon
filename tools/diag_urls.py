"""Baixa HTML bruto de URLs e publica na branch 'diag' (para inspeção remota)."""
import os, subprocess, sys, time
import httpx

UA = "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"
os.makedirs("diag", exist_ok=True)
linhas = []
with httpx.Client(follow_redirects=True, timeout=30, headers={"User-Agent": UA}) as c:
    for i, u in enumerate(sys.argv[1].split(), 1):
        try:
            r = c.get(u)
            open(f"diag/{i}.html", "w", encoding="utf-8").write(r.text)
            linhas.append(f"{i} {r.status_code} {len(r.text)} {r.headers.get('server','')} {u}")
        except Exception as e:  # noqa: BLE001
            linhas.append(f"{i} ERRO {type(e).__name__}: {e} {u}")
        time.sleep(2)
open("diag/index.txt", "w", encoding="utf-8").write("\n".join(linhas) + "\n")
print("\n".join(linhas))

g = lambda *a: subprocess.run(["git", *a], check=True)
g("config", "user.name", "leilaomon-bot"); g("config", "user.email", "bot@users.noreply.github.com")
g("checkout", "--orphan", "diag-tmp"); g("rm", "-rq", "--cached", ".")
g("add", "-f", "diag"); g("commit", "-qm", "diag"); g("push", "-f", "origin", "HEAD:diag")
