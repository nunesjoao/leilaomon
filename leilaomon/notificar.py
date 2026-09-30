import os
import smtplib
from email.mime.text import MIMEText
from html import escape

import httpx


def _env(k, default=None):
    v = os.getenv(k) or default
    if v is None:
        raise KeyError(k)
    return v


def fmt_brl(v):
    return "—" if v is None else f"R$ {v:,.0f}".replace(",", ".")


def fmt_pct(v):
    return "—" if v is None else f"{v * 100:.0f}%"


class Email:
    def __init__(self):
        self.host = _env("SMTP_HOST", "smtp.gmail.com")
        self.port = int(_env("SMTP_PORT", "465"))
        self.user = _env("SMTP_USER")
        self.pwd = _env("SMTP_PASS")  # Gmail: senha de app
        self.to = _env("EMAIL_TO", self.user)

    def enviar(self, assunto: str, html: str):
        msg = MIMEText(html, "html", "utf-8")
        msg["Subject"], msg["From"], msg["To"] = assunto, self.user, self.to
        with smtplib.SMTP_SSL(self.host, self.port) as s:
            s.login(self.user, self.pwd)
            s.send_message(msg)


class WhatsApp:
    """CallMeBot: envie 'I allow callmebot to send me messages' ao número do bot
    (ver callmebot.com) para receber a apikey. Só envia para o seu próprio número."""

    def __init__(self):
        self.phone = _env("CALLMEBOT_PHONE")  # formato +5521999999999
        self.key = _env("CALLMEBOT_APIKEY")

    def enviar(self, texto: str):
        r = httpx.get("https://api.callmebot.com/whatsapp.php", timeout=30,
                      params={"phone": self.phone, "text": texto[:1500], "apikey": self.key})
        r.raise_for_status()


def html_digest(itens) -> str:
    """itens: lista de (filtro, lote)"""
    linhas = []
    for filtro, l in itens:
        linhas.append(
            f"<tr><td>{escape(filtro)}</td>"
            f"<td><a href='{escape(l['url'])}'>{escape(l['titulo'])}</a><br>"
            f"<small>{escape(l['monta'] or '')} · {l['km'] or '?'} km · {escape(l['cidade'] or '')}/{escape(l['uf'] or '')}"
            f" · leilão {escape(l['leilao_data'][:16].replace('T', ' '))}</small></td>"
            f"<td>{fmt_brl(l['lance_atual'] or l['lance_inicial'])}</td>"
            f"<td>{fmt_brl(l['custo_total'])}</td><td>{fmt_brl(l['fipe_valor'])}</td>"
            f"<td><b>{fmt_pct(l['desconto'])}</b></td></tr>")
    return ("<table border=1 cellpadding=4 style='border-collapse:collapse;font-family:sans-serif;font-size:13px'>"
            "<tr><th>Filtro</th><th>Lote</th><th>Lance</th><th>Custo real</th><th>FIPE</th><th>Desc.</th></tr>"
            + "".join(linhas) + "</table>"
            "<p style='font-size:12px'>Desconto = 1 − custo real ÷ (FIPE × fator da monta). "
            "Lance inicial é piso: o arremate costuma sair acima.</p>")


def texto_whats(filtro, l) -> str:
    return (f"🚨 {l['titulo']}\n{l['monta']} · {l['km'] or '?'} km\n"
            f"Lance {fmt_brl(l['lance_atual'] or l['lance_inicial'])} · custo {fmt_brl(l['custo_total'])} · "
            f"FIPE {fmt_brl(l['fipe_valor'])} · desc {fmt_pct(l['desconto'])}\n"
            f"Leilão {l['leilao_data'][:16].replace('T', ' ')} [{filtro}]\n{l['url']}")
