"""Uso:
  python -m leilaomon run            # coleta + avalia + notifica (para o cron)
  python -m leilaomon coletar
  python -m leilaomon avaliar
  python -m leilaomon notificar [--seco]
  python -m leilaomon top [-n 20]    # melhores oportunidades no terminal
  python -m leilaomon teste-notificacao
"""
import argparse
import logging
import os
import sys

import yaml

from .avaliacao import avaliar, casa, horas_ate
from .db import DB
from .fipe import Fipe
from .fontes.rogeriomenezes import RogerioMenezes
from .notificar import Email, WhatsApp, fmt_brl, fmt_pct, html_digest, texto_whats

log = logging.getLogger("leilaomon")
FONTES = {"rogeriomenezes": RogerioMenezes}


def coletar(db, cfg):
    for nome in cfg["fontes"]:
        fonte = FONTES[nome]()
        leiloes = fonte.listar_leiloes()
        log.info("%s: %d leilões de veículos na agenda", nome, len(leiloes))
        for lei in leiloes:
            lotes = fonte.listar_lotes(lei)
            log.info("  leilão %s (%s): %d lotes", lei["id"], lei["data"][:16], len(lotes))
            for l in lotes:
                db.upsert(l)
                atual = db.get(l["id"])
                if not atual["detalhe_ok"] or horas_ate(atual) < 30:  # rechecar obs. perto do pregão
                    try:
                        db.upsert({"id": l["id"], **fonte.detalhar(l)})
                    except Exception as e:  # noqa: BLE001
                        log.warning("detalhe falhou %s: %s", l["url"], e)


def avaliar_todos(db, cfg):
    fipe = Fipe(db, os.getenv("FIPE_TOKEN") or None)
    for l in db.ativos():
        upd = {"id": l["id"]}
        if not l["fipe_tentado"]:
            try:
                upd.update(fipe.cotar(l["tipo"], l["marca"], l["modelo"], l["ano_mod"], l["combustivel"]) or {})
                upd["fipe_tentado"] = 1
            except RuntimeError as e:
                log.error("%s", e)
                break
            except Exception as e:  # noqa: BLE001
                log.warning("FIPE falhou para %s: %s", l["titulo"], e)
        db.upsert(upd)
        l = db.get(l["id"])
        db.upsert({"id": l["id"], **avaliar(l, cfg)})


def _canal(cls):
    try:
        return cls()
    except KeyError as e:
        log.info("%s desativado (variável %s ausente)", cls.__name__, e)
        return None


def notificar(db, cfg, seco=False):
    email, whats = (None, None) if seco else (_canal(Email), _canal(WhatsApp))
    wcfg = cfg["whatsapp"]
    digest, urgentes = [], []
    for l in db.ativos():
        for f in cfg["filtros"]:
            if not casa(l, f):
                continue
            n = f["nome"]
            if not db.ja_notificado(l["id"], n, "email"):
                digest.append((n, l))
            quente = l["desconto"] is not None and l["desconto"] >= wcfg["desconto_min"]
            if quente and not db.ja_notificado(l["id"], n, "whats"):
                urgentes.append((n, l, "whats"))
            elif horas_ate(l) <= wcfg["lembrete_horas"] and not db.ja_notificado(l["id"], n, "lembrete"):
                urgentes.append((n, l, "lembrete"))

    digest.sort(key=lambda x: -(x[1]["desconto"] or -1))
    if seco:
        for n, l in digest:
            print(f"[{n}] {fmt_pct(l['desconto']):>5} {fmt_brl(l['custo_total']):>12}  {l['titulo']}")
        print(f"{len(urgentes)} alertas urgentes pendentes")
        return
    if digest and email:
        email.enviar(f"Leilões: {len(digest)} lote(s) novo(s) nos seus filtros", html_digest(digest))
        for n, l in digest:
            db.marcar(l["id"], n, "email")
    for n, l, tipo in urgentes:
        canal = whats or email
        if not canal:
            break
        if canal is whats:
            whats.enviar(("⏰ Encerra em breve\n" if tipo == "lembrete" else "") + texto_whats(n, l))
        else:
            email.enviar(f"[{tipo}] {l['titulo']}", html_digest([(n, l)]))
        db.marcar(l["id"], n, tipo)
    log.info("notificados: %d no digest, %d urgentes", len(digest), len(urgentes))


def top(db, n):
    rows = [l for l in db.ativos() if l["desconto"] is not None]
    rows.sort(key=lambda l: -l["desconto"])
    for l in rows[:n]:
        print(f"{fmt_pct(l['desconto']):>5}  custo {fmt_brl(l['custo_total']):>11}  FIPE {fmt_brl(l['fipe_valor']):>11}"
              f"  {l['monta']:<13} {l['titulo']}\n       {l['url']}")


def main():
    p = argparse.ArgumentParser(prog="leilaomon")
    p.add_argument("cmd", choices=["run", "coletar", "avaliar", "notificar", "top", "teste-notificacao"])
    p.add_argument("-c", "--config", default="config.yaml")
    p.add_argument("-n", type=int, default=20)
    p.add_argument("--seco", action="store_true", help="não envia, só imprime")
    a = p.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    cfg = yaml.safe_load(open(a.config, encoding="utf-8"))
    db = DB(cfg.get("db", "leiloes.db"))

    if a.cmd in ("run", "coletar"):
        coletar(db, cfg)
    if a.cmd in ("run", "avaliar"):
        avaliar_todos(db, cfg)
    if a.cmd in ("run", "notificar"):
        notificar(db, cfg, seco=a.seco)
    if a.cmd == "top":
        top(db, a.n)
    if a.cmd == "teste-notificacao":
        for cls in (Email, WhatsApp):
            c = _canal(cls)
            if c:
                c.enviar("Teste leilaomon", "Teste leilaomon ✅") if cls is Email else c.enviar("Teste leilaomon ✅")
                print(cls.__name__, "ok")


if __name__ == "__main__":
    sys.exit(main())
