import time

import httpx
from bs4 import BeautifulSoup

try:  # cadeia de certificados incompleta em alguns sites (ex.: Freitas)
    import truststore
    truststore.inject_into_ssl()
except ImportError:
    pass

UA = "Mozilla/5.0 (compatible; leilaomon/0.1; monitor pessoal)"


class Fonte:
    nome = ""

    def __init__(self, delay: float = 1.5, timeout: float = 30):
        self.delay = delay
        self.http = httpx.Client(timeout=timeout, follow_redirects=True, headers={"User-Agent": UA})

    def _get(self, url: str, **kw) -> httpx.Response:
        for tentativa in range(3):
            try:
                r = self.http.get(url, **kw)
                r.raise_for_status()
                time.sleep(self.delay)
                return r
            except httpx.HTTPError:
                if tentativa == 2:
                    raise
                time.sleep(5 * (tentativa + 1))

    def _soup(self, url: str, **kw) -> BeautifulSoup:
        return BeautifulSoup(self._get(url, **kw).text, "html.parser")

    @staticmethod
    def linhas(soup: BeautifulSoup) -> list[str]:
        for t in soup(["script", "style", "noscript"]):
            t.decompose()
        return [l.strip() for l in soup.get_text("\n").split("\n") if l.strip()]
