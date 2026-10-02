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
    t = re.sub(r"(?<=[A-Z])/(?=[A-Z])", " ", t)
    t = re.sub(r"^SUCATA\s+(DE\s+|DA\s+|DO\s+)?", "", t)
    if t.startswith("MOTO "):
        tipo, t = "moto", t[5:]
    elif t.startswith(("CAMINHAO ", "ONIBUS ", "CAVALO MECANICO ")):
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
    modelo = modelo.lstrip("/- ")
    if re.search(r"REBOQUE|CARRETA|DOLLY", modelo):
        tipo = out["tipo"] = "outro"
    out["marca"] = marca
    out["modelo"] = re.sub(r"\s+", " ", modelo).strip()
    return out


def parse_km(texto: str):
    m = RE_KM.search(texto or "")
    return int(m.group(1).replace(".", "")) if m else None


# ordem importa: a primeira que casar define a monta
MONTAS = [
    ("grande", r"gr(ande)?\.?\s*mont|sucata|sem\s+aproveitamento|baixa\s+definitiva|irrecuper"),
    ("media", r"m[eé]d(ia)?\.?\s*mont"),
    ("pequena", r"peq(uena)?\.?\s*mont"),
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
        conservado = re.search(r"banco|financ|frota|locadora|empresa", sem_acento(f"{origem} {t}").lower())
        monta = "conservado" if conservado and "sinistr" not in t else "nao_informada"
    flags = [f for f, rx in FLAGS.items() if re.search(sem_acento(rx), t)]
    return monta, flags


def brl(s: str):
    """'R$ 31.000,00' -> 31000.0"""
    m = re.search(r"([\d\.]+,\d{2})", s or "")
    return float(m.group(1).replace(".", "").replace(",", ".")) if m else None


MARCAS_SO_MOTO = {"YAMAHA", "KAWASAKI", "SHINERAY", "DAFRA", "TRIUMPH", "HARLEY-DAVIDSON", "HARLEY DAVIDSON",
                  "KTM", "ROYAL ENFIELD", "DUCATI", "HAOJUE", "BAJAJ", "MOTTU", "JTZ", "SUNDOWN", "TRAXX",
                  "KASINSKI", "MV AGUSTA", "BENELLI", "VOLTZ", "AVELLOZ", "HUSQVARNA", "ZONTES"}
RE_MODELO_MOTO = re.compile(
    r"\b(CG|CB|CBR|XRE|NXR|BROS|BIZ|POP|PCX|ADV|ELITE|LEAD|SH|NC|XR|CRF|TITAN|FAN|START|CARGO|"
    r"FAZER|YBR|FACTOR|LANDER|TENERE|CROSSER|NMAX|XMAX|NEO|CRYPTON|MT[- ]?\d|R[1-9]|"
    r"BURGMAN|GSX|V[- ]?STROM|INTRUDER|YES|HAYABUSA|AFRICA TWIN|X[- ]?ADV|"
    r"G\s?310|F\s?[789]\d0|R\s?1[23]\d0|S\s?1000|NINJA|Z\s?\d{3,4}|VERSYS)\b")


def eh_moto(marca: str, modelo: str) -> bool:
    m = norm(marca)
    if m in MARCAS_SO_MOTO or norm(modelo).startswith("MOTO "):
        return True
    if m in {"HONDA", "SUZUKI", "BMW"}:
        return bool(RE_MODELO_MOTO.search(norm(modelo)))
    return False


def combustivel_de(texto: str):
    t = norm(texto)
    if "ALCOOL" in t and "GASOLINA" in t or "FLEX" in t:
        return "flex"
    if "ELETRICO" in t and "GASOLINA" in t or "HIBRIDO" in t:
        return "hibrido"
    return next((v for k, v in COMBUSTIVEIS.items() if k in t), None)


def ano4(a: str) -> int:
    a = int(a)
    return a if a > 1000 else (2000 + a if a < 60 else 1900 + a)
