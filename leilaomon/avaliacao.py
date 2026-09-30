import json
import math
import re
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
    lance = lote["lance_atual"] or lote["lance_inicial"] or 0
    monta = lote["monta"] or "nao_informada"
    fr = frete(lote, cfg)
    custo = (lance * (1 + c["comissao_pct"] / 100) + c["taxa_adm"] + fr
             + c["regularizacao"].get(monta, 0) + c["transferencia"])
    out = {"frete": round(fr, 2), "custo_total": round(custo, 2), "preco_ref": None, "desconto": None}
    if lote["fipe_valor"]:
        ref = lote["fipe_valor"] * (1 - c["desagio_mercado"].get(monta, 0))
        out["preco_ref"] = round(ref, 2)
        out["desconto"] = round(1 - custo / ref, 4)
    return out


def casa(lote, f: dict) -> bool:
    """Retorna True se o lote atende ao filtro (chaves ausentes = sem restrição)."""
    if f.get("tipos") and lote["tipo"] not in f["tipos"]:
        return False
    if f.get("montas") and (lote["monta"] or "nao_informada") not in f["montas"]:
        return False
    flags = set(json.loads(lote["flags"] or "[]"))
    if flags & set(f.get("excluir_flags", [])):
        return False
    if f.get("marcas") and not any(m.upper() in (lote["marca"] or "") for m in f["marcas"]):
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
        if lote["desconto"] is None:
            return bool(f.get("aceitar_sem_fipe"))
        if lote["desconto"] < f["desconto_min"]:
            return False
    return True


def horas_ate(lote) -> float:
    return (datetime.fromisoformat(lote["leilao_data"]) - datetime.now()).total_seconds() / 3600
