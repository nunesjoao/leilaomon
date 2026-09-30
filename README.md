# leilaomon — monitor pessoal de leilões de veículos

## Setup
```bash
python -m venv .venv && . .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # preencher; exportar com: set -a; . ./.env; set +a
# editar config.yaml: destino (lat/lon), custos e filtros
```

## Primeira execução (sem enviar nada)
```bash
python -m leilaomon coletar
python -m leilaomon avaliar
python -m leilaomon top -n 30
python -m leilaomon notificar --seco
python -m leilaomon teste-notificacao
```

## Cron (a cada 3 h)
```
0 */3 * * * cd /opt/leilaomon && set -a && . ./.env && set +a && .venv/bin/python -m leilaomon run >> run.log 2>&1
```

## Lógica
- custo real = lance × (1 + comissão) + taxa adm + frete + regularização(monta) + transferência
- preço de referência = FIPE × (1 − deságio de mercado da monta)
- desconto = 1 − custo real ÷ preço de referência
- e-mail: digest de lotes novos que casam com algum filtro (1× por lote/filtro)
- WhatsApp: desconto ≥ `whatsapp.desconto_min`, ou lembrete `lembrete_horas` antes do pregão
- grande monta/sucata nunca entra (não está em `montas` dos filtros)

## Adicionar fonte
Criar `leilaomon/fontes/<nome>.py` com `listar_leiloes()`, `listar_lotes(leilao)`, `detalhar(lote)`
retornando os mesmos campos, e registrar em `FONTES` no `__main__.py`.
