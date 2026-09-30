"""Normalização de títulos e textos livres de lotes."""
import re
import unicodedata

MARCAS_COMPOSTAS = [
    "VW - VOLKSWAGEN", "GM - CHEVROLET", "MERCEDES-BENZ", "MERCEDES BENZ",
    "CAOA CHERY", "ROYAL ENFIELD", "LAND ROVER", "KIA MOTORS", "ALFA ROMEO",
    "HARLEY-DAVIDSON", "HARLEY DAVIDSON", "MV AGUSTA", "ASTON MARTIN",
]
COMBUSTIVEIS = {
    "GASOLINA": "gasolina", "FLEX": "flex", "DIESEL": "diesel", "ALCOOL": "alcool",
    "HIBRIDO": "hibrido", "ELETRICO": "eletrico", "GNV": "gnv",
}
RE_TITULO = re.compile(r"^(?P<resto>.+?)\s+(?P<af>(19|20)\d{2})/(?P<am>(19|20)\d{2})\s*(?P<comb>[A-Z]+)?\s*$")
RE_KM = re.compile(r"com\s+([\d\.]+)\s*km", re.I)


def sem_acento(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def norm(s: str) -> str:
    s = sem_acento(s or "").upper()
    s = re.sub(r"[^A-Z0-9\.\s/-]", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def parse_titulo(titulo: str) -> dict:
    t = norm(titulo)
    tipo = "carro"
    if t.startswith("MOTO "):
        tipo, t = "moto", t[5:]
    elif t.startswith(("CAMINHAO ", "ONIBUS ")):
        tipo, t = "caminhao", t.split(" ", 1)[1]

    out = {"tipo": tipo, "marca": None, "modelo": None, "ano_fab": None, "ano_mod": None, "combustivel": None}
    m = RE_TITULO.match(t)
    if m:
        t = m["resto"]
        out["ano_fab"], out["ano_mod"] = int(m["af"]), int(m["am"])
        out["combustivel"] = COMBUSTIVEIS.get(m["comb"] or "")

    marca = next((mc for mc in MARCAS_COMPOSTAS if t.startswith(mc + " ")), None)
    if not marca:
        marca = t.split(" ", 1)[0]
    modelo = t[len(marca):].strip()
    # remove marca repetida ("HYUNDAI HYUNDAI CRETA") e anos soltos no modelo
    base = marca.split(" - ")[-1].split(" ")[0]
    modelo = re.sub(rf"^({re.escape(base)}\s+)+", "", modelo)
    modelo = re.sub(r"\b(19|20)\d{2}\b", "", modelo)
    for c in COMBUSTIVEIS:
        modelo = re.sub(rf"\b{c}\b", "", modelo)
    out["marca"] = marca
    out["modelo"] = re.sub(r"\s+", " ", modelo).strip()
    return out


def parse_km(texto: str):
    m = RE_KM.search(texto or "")
    return int(m.group(1).replace(".", "")) if m else None


# ordem importa: a primeira que casar define a monta
MONTAS = [
    ("grande", r"grande\s+monta|sucata|sem\s+aproveitamento|baixa\s+definitiva|irrecuper"),
    ("media", r"m[eé]dia\s+monta"),
    ("pequena", r"pequena\s+monta"),
]
FLAGS = {
    "remarcado": r"remarcad",
    "sem_documento": r"sem\s+doc",
    "sem_chave": r"sem\s+chave",
    "nao_funciona": r"n[aã]o\s+(funciona|liga|anda)|motor\s+(fundido|travado)",
    "enchente": r"enchente|alagamento|submers",
    "incendio": r"inc[eê]ndio|queimad",
    "roubo_furto": r"roubo|furto|recuperad[oa]\s+de\s+(roubo|furto)",
}


def classificar(texto: str, origem: str = "") -> tuple[str, list[str]]:
    t = sem_acento(texto or "").lower()
    monta = next((nome for nome, rx in MONTAS if re.search(sem_acento(rx), t)), None)
    if monta is None:
        monta = "conservado" if "banco" in (origem or "").lower() else "nao_informada"
    flags = [f for f, rx in FLAGS.items() if re.search(sem_acento(rx), t)]
    return monta, flags


def brl(s: str):
    """'R$ 31.000,00' -> 31000.0"""
    m = re.search(r"([\d\.]+,\d{2})", s or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None
