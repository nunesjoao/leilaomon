import json
import sqlite3
from datetime import datetime

SCHEMA = """
CREATE TABLE IF NOT EXISTS lotes (
  id TEXT PRIMARY KEY, fonte TEXT, leilao_id TEXT, leilao_titulo TEXT, origem TEXT,
  leilao_data TEXT, url TEXT, numero TEXT, titulo TEXT,
  tipo TEXT, marca TEXT, modelo TEXT, ano_fab INT, ano_mod INT, combustivel TEXT, km INT,
  descricao TEXT, observacoes TEXT, monta TEXT, flags TEXT,
  lance_inicial REAL, lance_atual REAL, tem_lance INT,
  foto TEXT, comissao_pct REAL, despesas REAL, cidade TEXT, uf TEXT, lat REAL, lon REAL,
  fipe_tentado INT DEFAULT 0, fipe_valor REAL, fipe_codigo TEXT, fipe_modelo TEXT, fipe_score REAL,
  frete REAL, custo_total REAL, preco_ref REAL, desconto REAL,
  detalhe_ok INT DEFAULT 0, primeira_vez TEXT, atualizado TEXT
);
CREATE TABLE IF NOT EXISTS historico_lances (lote_id TEXT, ts TEXT, valor REAL);
CREATE TABLE IF NOT EXISTS notificacoes (
  lote_id TEXT, filtro TEXT, tipo TEXT, ts TEXT, PRIMARY KEY (lote_id, filtro, tipo));
CREATE TABLE IF NOT EXISTS fipe_cache (chave TEXT PRIMARY KEY, valor TEXT, ts TEXT);
"""


def agora() -> str:
    return datetime.now().isoformat(timespec="seconds")


class DB:
    def __init__(self, path: str):
        self.con = sqlite3.connect(path)
        self.con.row_factory = sqlite3.Row
        self.con.executescript(SCHEMA)
        cols = {r[1] for r in self.con.execute("PRAGMA table_info(lotes)")}
        for c, t in [("foto", "TEXT"), ("comissao_pct", "REAL"), ("despesas", "REAL")]:
            if c not in cols:
                self.con.execute(f"ALTER TABLE lotes ADD COLUMN {c} {t}")
        self.con.commit()

    def get(self, lote_id: str):
        return self.con.execute("SELECT * FROM lotes WHERE id=?", (lote_id,)).fetchone()

    def upsert(self, d: dict) -> bool:
        """Insere/atualiza lote. Retorna True se é novo. Registra mudança de lance."""
        d = dict(d)
        if isinstance(d.get("flags"), list):
            d["flags"] = json.dumps(d["flags"])
        antigo = self.get(d["id"])
        d["atualizado"] = agora()
        if antigo is None:
            d["primeira_vez"] = d["atualizado"]
            cols = ",".join(d)
            self.con.execute(f"INSERT INTO lotes ({cols}) VALUES ({','.join('?' * len(d))})", list(d.values()))
        else:
            sets = ",".join(f"{k}=?" for k in d if k != "id")
            self.con.execute(f"UPDATE lotes SET {sets} WHERE id=?", [v for k, v in d.items() if k != "id"] + [d["id"]])
        novo_lance = d.get("lance_atual")
        if novo_lance and (antigo is None or antigo["lance_atual"] != novo_lance):
            self.con.execute("INSERT INTO historico_lances VALUES (?,?,?)", (d["id"], d["atualizado"], novo_lance))
        self.con.commit()
        return antigo is None

    def ativos(self):
        return self.con.execute(
            "SELECT * FROM lotes WHERE leilao_data >= ? ORDER BY leilao_data", (agora(),)).fetchall()

    def ja_notificado(self, lote_id, filtro, tipo) -> bool:
        return self.con.execute("SELECT 1 FROM notificacoes WHERE lote_id=? AND filtro=? AND tipo=?",
                                (lote_id, filtro, tipo)).fetchone() is not None

    def marcar(self, lote_id, filtro, tipo):
        self.con.execute("INSERT OR IGNORE INTO notificacoes VALUES (?,?,?,?)", (lote_id, filtro, tipo, agora()))
        self.con.commit()

    def cache_get(self, chave, max_dias):
        r = self.con.execute("SELECT valor, ts FROM fipe_cache WHERE chave=?", (chave,)).fetchone()
        if r and (datetime.now() - datetime.fromisoformat(r["ts"])).days < max_dias:
            return json.loads(r["valor"])
        return None

    def cache_set(self, chave, valor):
        self.con.execute("INSERT OR REPLACE INTO fipe_cache VALUES (?,?,?)", (chave, json.dumps(valor), agora()))
        self.con.commit()


# campos que vêm da coleta (o resto é calculado no banco principal)
CAMPOS_COLETA = ["id", "fonte", "leilao_id", "leilao_titulo", "origem", "leilao_data", "url", "numero", "titulo",
                 "tipo", "marca", "modelo", "ano_fab", "ano_mod", "combustivel", "km", "descricao", "observacoes",
                 "monta", "flags", "lance_inicial", "lance_atual", "tem_lance", "foto", "comissao_pct", "despesas",
                 "cidade", "uf", "lat", "lon", "detalhe_ok"]


def importar(db: "DB", caminho: str) -> int:
    """Traz para o banco principal os lotes coletados em outro banco (executor residencial)."""
    import os
    if not os.path.exists(caminho):
        return 0
    outro = DB(caminho)
    n = 0
    for r in outro.ativos():
        db.upsert({k: r[k] for k in CAMPOS_COLETA if r[k] is not None})
        n += 1
    return n
