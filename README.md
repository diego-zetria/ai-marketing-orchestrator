# Marketing Briefing Bot

Sistema de automacao com IA para a agencia de marketing **Agency**. O bot recebe briefings de clientes via Telegram e cria automaticamente tasks estruturadas no ClickUp, seguindo o fluxo de trabalho padrao da agencia.

## Problema

O time de atendimento da Agency recebe briefings de clientes e precisa criar manualmente cards no ClickUp com titulo padronizado, subtasks por post, assignees corretos e status inicial. Esse processo e repetitivo e propenso a erros.

## Solucao

Um bot no Telegram da agencia onde o funcionario do atendimento envia o briefing do cliente em texto livre. Um agente de IA analisa o briefing e cria automaticamente o card completo no ClickUp.

### Fluxo

```
Funcionario envia briefing no Telegram
    -> Telegram Webhook recebe a mensagem
    -> Agente IA analisa o briefing (Agno + OpenRouter)
    -> Motor de Regras determina assignees (rules.yaml)
    -> ClickUp API cria card + subtasks
    -> Bot responde no Telegram com confirmacao
```

### Exemplo de Interacao

**Funcionario envia:**
> Briefing do cliente Loja Bella: Precisamos de 3 posts para Instagram sobre a promocao de verao e 1 banner para o site. Urgente, promocao comeca dia 25.

**Bot responde:**
> **Briefing analisado - Cliente: Loja Bella**
>
> Card criado: **Instagram - Loja Bella - Fevereiro 2026**
> Prioridade: Urgente
>
> 4 subtasks criadas:
> - Post 1 - Promocao Verao -> Design: @joao | Copy: @maria
> - Post 2 - Promocao Verao -> Design: @joao | Copy: @maria
> - Post 3 - Promocao Verao -> Design: @joao | Copy: @maria
> - Banner Site - Promocao Verao -> Design: @ana

## Fluxo de Referencia - Social Media Agency

Baseado no fluxograma oficial da agencia (`Fluxograma Social Media.pdf`):

```
Atendimento -> Card ClickUp (Planejamento) -> Problematizar -> Direcionamento
-> Cronograma de posts -> Revisao Interna (Luis/Content Lead) -> Aprovacao Cliente
-> Desenvolvimento (Designer) -> Criacao Arte -> Revisao Interna
-> Aprovacao Cliente -> Agendamento (MLabs) -> Postagem -> Relatorio
```

**Padrao de nomenclatura do card:** `(Rede Social) (Cliente) (Mes) (Ano)`

**O MVP automatiza as etapas 1-2:** Recebe briefing e cria o card com subtasks no ClickUp.

## Stack Tecnica

| Componente | Tecnologia |
|---|---|
| Linguagem | Python 3.12+ |
| Bot Telegram | python-telegram-bot (webhook mode) |
| API Server | FastAPI + uvicorn |
| Agentes IA | Agno (structured output) |
| LLM | OpenRouter |
| Banco de dados | PostgreSQL + SQLAlchemy + Alembic |
| HTTP Client | httpx (async) |
| Validacao | Pydantic v2 |
| Config | pydantic-settings |
| Testes | pytest + pytest-asyncio + respx |
| Infra local | Docker Compose |
| Cloud (futuro) | AWS (ECS/Lambda + RDS) |

## Estrutura do Projeto

```
marketing-bot/
├── src/
│   ├── api/
│   │   └── app.py                # FastAPI (webhook endpoint, health check)
│   ├── agents/
│   │   ├── schemas.py            # Pydantic models (BriefingAnalysis, PostTask)
│   │   └── briefing_analyzer.py  # Agente Agno (analisa briefing)
│   ├── bot/
│   │   ├── handlers.py           # Handlers do Telegram
│   │   └── responses.py          # Formatacao de respostas
│   ├── integrations/
│   │   └── clickup/
│   │       ├── client.py         # Client async ClickUp API
│   │       └── models.py         # Models de request/response
│   ├── engine/
│   │   └── rules.py              # Motor de regras (YAML)
│   ├── db/
│   │   ├── models.py             # SQLAlchemy models
│   │   ├── session.py            # Async session factory
│   │   └── repository.py         # Operacoes de banco
│   ├── config/
│   │   └── settings.py           # Configuracoes (.env)
│   └── main.py                   # Entry point
├── config/
│   └── rules.yaml                # Regras de atribuicao
├── tests/                        # 28 testes
├── alembic/                      # Migrations
├── docs/
│   └── plans/
│       ├── 2026-02-20-marketing-briefing-bot-design.md
│       └── 2026-02-20-marketing-briefing-bot-implementation.md
├── docker-compose.yml
├── pyproject.toml
└── .env.example
```

## Setup Local

### Pre-requisitos

- Python 3.12+
- Docker (para PostgreSQL)

### Instalacao

```bash
# Clonar o repositorio
git clone git@github.com:MyOrg-AI/marketing-bot.git
cd marketing-bot

# Criar venv e instalar dependencias
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Copiar e preencher variaveis de ambiente
cp .env.example .env
# Edite .env com seus tokens reais

# Subir PostgreSQL
docker compose up -d

# Rodar migrations
alembic upgrade head

# Rodar testes
pytest tests/ -v
```

### Rodar o Bot

```bash
# Modo desenvolvimento (polling)
# Deixe TELEGRAM_WEBHOOK_URL vazio no .env
python -m src.main

# Modo producao (webhook)
# Preencha TELEGRAM_WEBHOOK_URL no .env
python -m src.main
```

## Configuracao de Regras

Edite `config/rules.yaml` para definir assignees, tags e overrides por cliente:

```yaml
assignment_rules:
  design:
    default_assignees: ["clickup_user_id"]
    tags: ["design"]
  copy:
    default_assignees: ["clickup_user_id"]
    tags: ["copy", "redacao"]

client_overrides:
  "Cliente X":
    designer: "clickup_user_id_especifico"
    list_id: "list_id_especifica"
```

## Variaveis de Ambiente

| Variavel | Descricao |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Token do bot Telegram (@BotFather) |
| `TELEGRAM_WEBHOOK_URL` | URL publica para webhook (vazio = polling mode) |
| `TELEGRAM_ALLOWED_USER_IDS` | IDs autorizados, separados por virgula |
| `OPENROUTER_API_KEY` | Chave da API do OpenRouter |
| `OPENROUTER_MODEL_ID` | Modelo LLM (default: `anthropic/claude-sonnet-4`) |
| `CLICKUP_API_TOKEN` | Token da API do ClickUp |
| `CLICKUP_DEFAULT_LIST_ID` | List ID padrao para criacao de tasks |
| `DATABASE_URL` | Connection string PostgreSQL |

## Testes

```bash
# Rodar todos os testes
pytest tests/ -v

# Com cobertura
pytest tests/ -v --cov=src
```

**28 testes** cobrindo: configuracao, schemas, rules engine, ClickUp client, briefing analyzer, bot responses, FastAPI health, e integracao end-to-end.

## Documentacao

- **Design completo:** `docs/plans/2026-02-20-marketing-briefing-bot-design.md`
- **Plano de implementacao:** `docs/plans/2026-02-20-marketing-briefing-bot-implementation.md`
- **Fluxograma original:** `Fluxograma Social Media.pdf`

## Evolucoes Futuras

1. Mais fluxos: Trafego pago, branding, video
2. Conversacao multi-turno (bot faz follow-up)
3. Webhooks ClickUp (reagir a mudancas de status)
4. Dashboard de monitoramento
5. Integracao com Google Drive e MLabs
6. Deploy AWS (ECS/Lambda + RDS + API Gateway)

---

Desenvolvido por [MyOrg AI](https://github.com/MyOrg-AI) para a Agencia Agency.
