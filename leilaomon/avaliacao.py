import json
import math
import re

from .parsing import norm
from datetime import datetime


def haversine(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def frete(lote, cfg) -> float:
    f = cfg["frete"]
    if lote["lat"] is None:
        return f["sem_local"]
    km = haversine(lote["lat"], lote["lon"], cfg["destino"]["lat"], cfg["destino"]["lon"]) * f["fator_rodoviario"]
    t = f["moto"] if lote["tipo"] == "moto" else f["carro"]
    if km <= f["raio_local_km"]:
        return t["local"]
    return max(t["minimo"], km * t["rs_km"])


def avaliar(lote, cfg) -> dict:
    c = cfg["custos"]
    lance = lote["lance_atual"] or lote["lance_inicial"]
    if not lance:  # lote ainda sem valor publicado
        return {"frete": None, "custo_total": None, "preco_ref": None, "desconto": None}
    monta = lote["monta"] or "nao_informada"
    fr = frete(lote, cfg)
    pct = lote["comissao_pct"] if lote["comissao_pct"] is not None else c["comissao_pct"]
    taxa = lote["despesas"] if lote["despesas"] is not None else c["taxa_adm"]
    custo = (lance * (1 + pct / 100) + taxa + fr
             + c["regularizacao"].get(monta, 0) + c["transferencia"])
    out = {"frete": round(fr, 2), "custo_total": round(custo, 2), "preco_ref": None, "desconto": None}
    if lote["fipe_valor"]:
        ref = lote["fipe_valor"] * (1 - c["desagio_mercado"].get(monta, 0))
        out["preco_ref"] = round(ref, 2)
        out["desconto"] = round(1 - custo / ref, 4) if ref > 0 else None
    return out


def _tokens(s) -> set:
    return {t for t in re.split(r"[\s\-/]+", norm(s)) if len(t) >= 2}


def _familia(nome) -> str:
    t = re.split(r"[\s/]+", norm(nome).strip())
    return t[0] if t and t[0] else ""


def casa_veiculo(lote, e: dict) -> bool:
    """Lote corresponde a uma entrada da lista (referência FIPE).
    e = {tipo, marca, marca_cod, familia?, modelo?, modelo_cod?}. Sem família/modelo = marca inteira."""
    if e.get("tipo") and lote["tipo"] != e["tipo"]:
        return False
    if lote["fipe_marca_cod"] and e.get("marca_cod"):
        if str(lote["fipe_marca_cod"]) != str(e["marca_cod"]):
            return False
    elif not (_tokens(e.get("marca")) & _tokens(lote["marca"])):
        return False
    if e.get("modelo_cod"):
        if lote["fipe_modelo_cod"]:
            return str(lote["fipe_modelo_cod"]) == str(e["modelo_cod"])
        return bool(e.get("modelo")) and norm(e["modelo"]) in norm(lote["titulo"])
    fam = norm(e.get("familia") or "")
    if not fam:
        return True
    return fam == _familia(lote["fipe_modelo"] or "") or re.search(rf"\b{re.escape(fam)}\b", norm(lote["modelo"] or lote["titulo"])) is not None


def casa(lote, f: dict, excluir_sempre=None) -> bool:
    """Retorna True se o lote atende ao filtro (chaves ausentes = sem restrição)."""
    if any(casa_veiculo(lote, e) for e in (excluir_sempre or []) + (f.get("excluir_veiculos") or [])):
        return False
    if f.get("permitir_veiculos") and not any(casa_veiculo(lote, e) for e in f["permitir_veiculos"]):
        return False
    if f.get("tipos") and lote["tipo"] not in f["tipos"]:
        return False
    if f.get("montas") and (lote["monta"] or "nao_informada") not in f["montas"]:
        return False
    flags = set(json.loads(lote["flags"] or "[]"))
    if flags & set(f.get("excluir_flags", [])):
        return False
    if f.get("marcas") and not any(norm(m) in norm(lote["marca"]) for m in f["marcas"]):
        return False
    if f.get("modelos") and not any(norm(m) in norm(lote["titulo"]) for m in f["modelos"]):
        return False
    lance = lote["lance_atual"] or lote["lance_inicial"]
    if f.get("lance_max") and (not lance or lance > f["lance_max"]):
        return False
    if f.get("modelo_regex") and not re.search(f["modelo_regex"], lote["titulo"] or "", re.I):
        return False
    if f.get("ano_min") and (lote["ano_mod"] or 0) < f["ano_min"]:
        return False
    if f.get("km_max") and lote["km"] and lote["km"] > f["km_max"]:
        return False
    if f.get("custo_max") and (lote["custo_total"] or 1e12) > f["custo_max"]:
        return False
    if f.get("desconto_min") is not None:
        if lote["desconto"] is None:  # sem cotação FIPE: entra, a menos que o filtro exija FIPE
            return not f.get("exigir_fipe")
        if lote["desconto"] < f["desconto_min"]:
            return False
    return True


def horas_ate(lote) -> float:
    return (datetime.fromisoformat(lote["leilao_data"]) - datetime.now()).total_seconds() / 3600
