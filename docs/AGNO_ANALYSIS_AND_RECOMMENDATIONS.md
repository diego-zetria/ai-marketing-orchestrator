# Analise Profunda do Framework Agno e Recomendacoes para Agencia Agency

> Documento gerado em 2026-02-22 | Baseado na analise de 9 projetos + documentacao oficial

---

## INDICE

1. [Resumo Executivo](#1-resumo-executivo)
2. [Estado Atual do marketing-bot](#2-estado-atual-do-marketing-bot)
3. [Licoes do agno-backend (Projeto Referencia)](#3-licoes-do-agno-backend-projeto-referencia)
4. [Melhores Praticas dos Repositorios Externos](#4-melhores-praticas-dos-repositorios-externos)
5. [Features do Agno Nao Utilizadas](#5-features-do-agno-nao-utilizadas)
6. [Recomendacoes de Implementacao](#6-recomendacoes-de-implementacao)
7. [Roadmap de Evolucao](#7-roadmap-de-evolucao)

---

## 1. RESUMO EXECUTIVO

### O que temos hoje
O **Marketing Briefing Bot** e um sistema de automacao para agencia de marketing com **4 agentes Agno** conectados via Telegram Bot + ClickUp. Usa structured output (Pydantic), OpenRouter como provedor LLM, e PostgreSQL para persistencia.

### O que estamos subutilizando
O framework Agno oferece 15+ funcionalidades que **NAO estao sendo usadas** no marketing-bot:

| Categoria | Feature | Impacto |
|-----------|---------|---------|
| **Critico** | Agent Tools (`@tool`) | Agentes nao executam acoes autonomamente |
| **Critico** | Teams (coordinate/route/broadcast/tasks) | Sem orquestracao nativa de multi-agentes |
| **Alto** | Memory (agentic memory) | Sem aprendizado de preferencias de clientes |
| **Alto** | Knowledge (vector DB + RAG) | Brand guidelines carregadas como texto bruto |
| **Alto** | Workflows (Step/Steps/Workflow) | Workflow manual via handlers Python |
| **Medio** | Structured Output com Teams | So em agentes individuais |
| **Medio** | Human-in-the-Loop | Implementado manualmente |
| **Medio** | Guardrails | Sem validacao de seguranca/PII |
| **Baixo** | Observability (Langfuse) | Apenas token count |
| **Baixo** | AgentOS | API manual via FastAPI |

### O que os outros projetos nos ensinam

| Projeto | Licao Principal |
|---------|-----------------|
| **agno-backend** | Hierarquia de times, model tiering, circuit breaker, fallback multi-provedor |
| **ai-blog-generator** | Workflow class com 3 agentes + response_model + retry pattern |
| **mcp-server-mas** | 6 agentes especializados por perspectiva cognitiva + routing por complexidade |
| **agentic-ai (Level 5)** | Team mode=route com 10+ agentes + Knowledge base + cache SQLite |
| **Agno Cookbook** | 4 TeamModes, Distributed RAG, Human-in-the-Loop, Guardrails, Workflows |

---

## 2. ESTADO ATUAL DO AGENCIA-Agency

### 2.1 Agentes Implementados

```
briefing_analyzer  --> Parseia briefings em BriefingAnalysis (Pydantic)
content_reviewer   --> Revisa conteudo contra brand guidelines
schedule_generator --> Gera cronograma mensal de posts
summary_generator  --> Gera resumos diarios/semanais
```

### 2.2 Padrao de Criacao de Agentes (Atual)

```python
Agent(
    name="briefing_analyzer",
    model=OpenRouter(id=model_id, api_key=api_key, max_tokens=4096,
                     retries=2, delay_between_retries=1, exponential_backoff=True),
    instructions=[...],          # Instrucoes em PT-BR
    output_schema=BriefingAnalysis,  # Pydantic schema
    use_json_mode=True,
    markdown=False,
)
```

### 2.3 Workflow Atual (Manual)

```
Telegram Message/PDF
    |
    v
BriefingHandler.handle_message()
    |
    v
[Agent 1] briefing_analyzer.arun(text) --> BriefingAnalysis
    |
    v
RulesEngine.get_assignment() --> assignees, list_id
    |
    v
ClickUpClient.create_task() --> main card
    |
    v (opcional)
[Agent 3] schedule_generator.arun() --> PostSchedule
    |
    v
[User Reviews via Telegram]
    |
    v
Create ClickUp subtasks
    |
    v (webhook)
[Agent 2] content_reviewer triggered on "revisao" status
    |
    v (scheduled)
[Agent 4] summary_generator on cron jobs
```

### 2.4 Pontos Fortes
- Structured output com Pydantic (excelente)
- Brand guidelines em Markdown (extensivel)
- Rules engine em YAML (sem code changes)
- Event-driven (webhooks + scheduled jobs)
- Type safety consistente
- 28 testes pytest

### 2.5 Lacunas Criticas
- **ZERO tools** nos agentes (eles nao podem executar acoes)
- **ZERO memory** (cada chamada e stateless)
- **ZERO knowledge base** (guidelines carregadas como string)
- **ZERO teams** (orquestracao manual)
- **ZERO workflows** nativos do Agno
- Single model para todos os agentes
- Sem observability
- Sem guardrails

---

## 3. LICOES DO AGNO-BACKEND (PROJETO REFERENCIA)

O agno-backend e um sistema **production-grade** com 15+ agentes, 50+ tools, 80+ routers. Aqui estao os padroes que devemos adotar:

### 3.1 Model Tiering (Critico para Custo)

```python
# Em vez de um unico modelo para tudo:
CLASSIFIER_MODEL = "claude-haiku-4-5"     # Rapido/barato - classificacao
WORKER_MODEL = "claude-haiku-4-5"         # Workers simples
CONTENT_MODEL = "claude-sonnet-4-5"       # Conteudo de qualidade
LEADER_MODEL = "claude-sonnet-4-5"        # Lider de time
EXPERT_MODEL = "claude-opus-4-5"          # Tarefas complexas (raro)
```

**Impacto no Agency**: Hoje usamos o mesmo modelo para tudo. Classificar urgencia nao precisa de Sonnet; gerar cronograma pode usar Haiku.

### 3.2 Factory Pattern para Agentes

```python
def create_researcher(db=None) -> Agent:
    return Agent(id="researcher", model=get_model(ModelTier.FAST), ...)

def create_team(db=None) -> Team:
    researcher = create_researcher(db)
    writer = create_writer(db)
    return Team(members=[researcher, writer], ...)
```

### 3.3 LLM Fallback com Circuit Breaker

```
Claude (Primary)
  | (fails: 5xx, rate limit)
Groq (Fast Llama)
  | (fails)
OpenAI (GPT-4)
  | (fails)
Ollama (Local - free)
```

### 3.4 Intent Classification + Fast-Path

```python
# Classificacao rapida com Haiku
intent = await intent_classifier.classify(message)

if intent in [Intent.GREET, Intent.THANKS]:
    response = await quick_agent.run(message)  # <3s, barato
else:
    response = await full_team.run(message)    # ~20s, completo
```

### 3.5 AgentOS para API Automatica

```python
from agno.os import AgentOS

agent_os = AgentOS(
    agents=[agent1, agent2, ...],
    teams=[team1, team2],
    workflows=[workflow1],
    knowledge=[knowledge],
    auto_provision_dbs=True,
)
app = agent_os.get_app()
# Auto-gera: /agents/{id}/run, /teams/{id}/run, etc.
```

### 3.6 Agentic Memory

```python
agent = Agent(
    db=PostgresDb(db_url=db_url),
    enable_agentic_memory=True,  # Aprende sobre usuarios automaticamente
)
# Agent 1: "O cliente ClientAlpha prefere tom sofisticado"
# Agent 2: Ja sabe das preferencias do ClientAlpha!
```

### 3.7 Context Compression

```python
# Quando context > 100K tokens, comprimir com Haiku
COMPRESSION_ENABLED = True
COMPRESSION_MODEL = "claude-haiku-4-5"
COMPRESSION_TOKEN_LIMIT = 100000
```

### 3.8 Observability com Langfuse

```python
# Tracing automatico de todas as decisoes dos agentes
OBSERVABILITY_ENABLED = True
LANGFUSE_HOST = "http://localhost:3000"
```

---

## 4. MELHORES PRATICAS DOS REPOSITORIOS EXTERNOS

### 4.1 ai-blog-generator - Workflow Pattern

**Padrao**: Workflow class que orquestra agentes especializados com retry e cache.

```python
class BlogPostGenerator(Workflow):
    def __init__(self, blog_agents):
        self.searcher = blog_agents.searcher_agent       # DuckDuckGoTools
        self.article_scraper = blog_agents.article_scraper_agent  # Newspaper4kTools
        self.writer = blog_agents.writer_agent            # No tools, pure generation

    def run(self, topic):
        search_results = self.get_search_results(topic, num_attempts=3)
        scraped = self.scrape_articles(topic, search_results)
        yield from self.writer.run(json.dumps(scraped), stream=True)
```

**Aplicacao Agency**: Briefing workflow deveria ser um `Workflow` do Agno, nao codigo imperativo.

### 4.2 mcp-server-mas - Agentes por Perspectiva Cognitiva

**Padrao**: 6 agentes, cada um com uma perspectiva diferente:
- Factual Agent (evidencia objetiva)
- Emotional Agent (intuicao)
- Critical Agent (riscos e problemas)
- Optimistic Agent (oportunidades)
- Creative Agent (ideias inovadoras)
- Process Agent (estrutura e metodologia)

**Aplicacao Agency**: Para content review, ter multiplas perspectivas:
- `BrandComplianceAgent` (compliance)
- `CreativeQualityAgent` (criatividade)
- `EngagementAnalysisAgent` (potencial de engajamento)

### 4.3 agentic-ai Level 5 - Team Route + Knowledge + Cache

**Padrao**: Team com `mode="route"`, 10+ agentes especializados, Knowledge base com ChromaDB, e cache SQLite.

```python
Team(
    name="MultiSource Processor",
    mode="route",
    model=Gemini(),
    enable_agentic_context=True,
    monitoring=True,
    members=[url_handler, json_corrector, scraper, pdf_processor,
             youtube_processor, web_processor, text_processor, ...],
)
```

**Aplicacao Agency**: Usar `mode="route"` para direcionar briefings ao agente correto baseado no tipo.

### 4.4 Agno Cookbook - 4 TeamModes

| Mode | Quando Usar no Agency |
|------|---------------------|
| **coordinate** | Briefing analysis: Researcher busca, Writer estrutura |
| **route** | Tipo de conteudo: Instagram Agent, LinkedIn Agent, TikTok Agent |
| **broadcast** | Content review: Multiplos reviewers dao opiniao independente |
| **tasks** | Campanha completa: Planner -> Writer -> Designer -> Reviewer -> Publisher |

### 4.5 Agno Cookbook - Distributed RAG

```python
vector_knowledge = Knowledge(
    vector_db=PgVector(
        table_name="brand_guidelines_vector",
        db_url=db_url,
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
)

brand_specialist = Agent(
    name="Brand Specialist",
    knowledge=vector_knowledge,
    search_knowledge=True,
)
```

**Aplicacao Agency**: Brand guidelines, historico de posts aprovados, feedback de clientes - tudo em vector DB.

### 4.6 Agno Cookbook - Human-in-the-Loop

```python
@tool(requires_confirmation=True)
def publish_to_instagram(post_content: str, schedule_time: str) -> str:
    """Publica conteudo no Instagram. Requer confirmacao humana."""
    ...

team = Team(members=[...], tools=[publish_to_instagram])
response = team.run("Publique o post")

if response.is_paused:
    for req in response.requirements:
        if req.needs_confirmation:
            req.confirm()  # Humano confirma
    response = team.continue_run(response)
```

### 4.7 Agno Cookbook - Guardrails

```python
# PII Detection - Proteger dados de clientes
# Prompt Injection - Prevenir manipulacao
# Moderation - Filtrar conteudo inadequado
```

### 4.8 Agno Cookbook - Workflows com Steps

```python
from agno.workflow.step import Step
from agno.workflow.steps import Steps
from agno.workflow.workflow import Workflow

research_step = Step(name="research", agent=researcher)
writing_step = Step(name="writing", agent=writer)
editing_step = Step(name="editing", agent=editor)

article_creation = Steps(
    name="article_creation",
    steps=[research_step, writing_step, editing_step],
)

workflow = Workflow(
    name="Article Creation Workflow",
    steps=[article_creation],
)

workflow.print_response(input="Write about renewable energy", markdown=True)
```

---

## 5. FEATURES DO AGNO NAO UTILIZADAS

### 5.1 Tools (@tool decorator)

```python
from agno.tools import Toolkit, tool

class ClickUpTools(Toolkit):
    def __init__(self, api_token: str):
        super().__init__(name="clickup")
        self.client = ClickUpAsyncClient(api_token)

    @tool
    async def get_task(self, task_id: str) -> str:
        """Busca detalhes de uma task no ClickUp."""
        task = await self.client.get_task(task_id)
        return json.dumps(task)

    @tool
    async def create_subtask(self, list_id: str, name: str, due_date: str) -> str:
        """Cria subtask no ClickUp."""
        result = await self.client.create_task(list_id, {"name": name, "due_date": due_date})
        return f"Subtask criada: {result['id']}"

    @tool
    async def update_task_status(self, task_id: str, status: str) -> str:
        """Atualiza status de uma task."""
        await self.client.update_task(task_id, {"status": status})
        return f"Task {task_id} atualizada para {status}"
```

### 5.2 Built-in Tools Uteis

```python
from agno.tools.duckduckgo import DuckDuckGoTools     # Pesquisa web
from agno.tools.tavily import TavilyTools             # Pesquisa AI-optimized
from agno.tools.exa import ExaTools                   # Pesquisa semantica
from agno.tools.newspaper4k import Newspaper4kTools   # Extracao de artigos
from agno.tools.crawl4ai import Crawl4aiTools         # Web scraping
from agno.tools.dalle import DalleTools               # Geracao de imagens
from agno.tools.clickup import ClickUpTools           # ClickUp nativo!
from agno.tools.csv import CsvTools                   # Analise CSV
from agno.tools.calculator import CalculatorTools     # Calculos
```

**NOTA**: O Agno ja tem `ClickUpTools` built-in! Nao precisamos criar o nosso.

### 5.3 KnowledgeTools

```python
from agno.tools.knowledge import KnowledgeTools

knowledge_tools = KnowledgeTools(
    knowledge=brand_knowledge,
    think=True,      # Raciocinar antes de buscar
    search=True,     # Buscar na base
    analyze=True,    # Analisar resultados
    add_few_shot=True,  # Exemplos automaticos
)
```

### 5.4 Team Modes

```python
from agno.team.mode import TeamMode

# COORDINATE: Lider escolhe membros e sintetiza respostas
# ROUTE: Lider direciona ao especialista correto
# BROADCAST: Todos respondem e lider sintetiza
# TASKS: Lider decompoe em tarefas com dependencias
```

### 5.5 Conditional Workflow Execution

```python
from agno.workflow.workflow import Workflow
from agno.workflow.step import Step

# Workflow com condicoes e paralelismo
# Se urgente -> fast track
# Se normal -> full review pipeline
# Paralelo: design + copy simultaneos
```

### 5.6 Session State e Storage

```python
from agno.storage.postgres import PostgresStorage

storage = PostgresStorage(
    db_url="postgresql+psycopg://...",
    table_name="app_sessions",
)

team = Team(
    storage=storage,  # Persiste estado entre sessoes
    ...
)
```

---

## 6. RECOMENDACOES DE IMPLEMENTACAO

### FASE 1: Quick Wins (1-2 semanas)

#### 1.1 Adicionar ClickUpTools aos Agentes

```python
from agno.tools.clickup import ClickUpTools

clickup_tools = ClickUpTools(
    api_token=settings.clickup_api_token,
    workspace_id=settings.clickup_team_id,
)

briefing_agent = Agent(
    name="briefing_analyzer",
    model=OpenRouter(id=model_id, ...),
    tools=[clickup_tools],  # NOVO: Agente pode criar tasks autonomamente
    instructions=[
        "Analise o briefing e crie as tasks no ClickUp automaticamente.",
        "Use a tool create_task para cada post identificado.",
        ...
    ],
    output_schema=BriefingAnalysis,
)
```

#### 1.2 Model Tiering

```python
# config/settings.py
FAST_MODEL = "anthropic/claude-haiku"        # Classificacao, routing
BALANCED_MODEL = "anthropic/claude-sonnet-4"  # Default
PREMIUM_MODEL = "anthropic/claude-opus-4"     # Reviews complexas

# Usar Haiku para summary_generator (simples, alto volume)
# Usar Sonnet para briefing_analyzer e content_reviewer
# Manter schedule_generator com Sonnet
```

#### 1.3 Adicionar DuckDuckGoTools ao Summary Generator

```python
summary_agent = Agent(
    name="summary_generator",
    tools=[DuckDuckGoTools()],  # Para buscar tendencias do mercado
    instructions=[
        "Inclua tendencias relevantes do mercado no resumo semanal.",
        ...
    ],
)
```

### FASE 2: Teams e Workflows (2-4 semanas)

#### 2.1 Team para Briefing Analysis

```python
from agno.team.team import Team
from agno.team.mode import TeamMode

# Agentes especializados por plataforma
instagram_agent = Agent(
    name="Instagram Specialist",
    role="Especialista em conteudo para Instagram",
    instructions=["Formate posts para Instagram: carrossel, reels, stories..."],
)

linkedin_agent = Agent(
    name="LinkedIn Specialist",
    role="Especialista em conteudo corporativo para LinkedIn",
    instructions=["Formate posts para LinkedIn: artigos, posts, newsletters..."],
)

tiktok_agent = Agent(
    name="TikTok Specialist",
    role="Especialista em conteudo para TikTok",
    instructions=["Formate conteudo para TikTok: trends, sons, formatos..."],
)

briefing_team = Team(
    name="Agency Briefing Team",
    mode=TeamMode.route,  # Direciona ao especialista da plataforma
    model=OpenRouter(id="anthropic/claude-haiku"),  # Router rapido
    members=[instagram_agent, linkedin_agent, tiktok_agent],
    instructions=[
        "Analise o briefing e direcione ao especialista da plataforma correta.",
        "Instagram -> Instagram Specialist",
        "LinkedIn -> LinkedIn Specialist",
        "TikTok -> TikTok Specialist",
    ],
)
```

#### 2.2 Team para Content Review (Broadcast Mode)

```python
content_review_team = Team(
    name="Agency Review Team",
    mode=TeamMode.broadcast,  # Todos revisam independentemente
    model=OpenRouter(id="anthropic/claude-sonnet-4"),
    members=[
        Agent(name="Brand Compliance", role="Verifica compliance com guidelines da marca"),
        Agent(name="Grammar Expert", role="Verifica ortografia e gramatica em PT-BR"),
        Agent(name="Engagement Analyst", role="Avalia potencial de engajamento"),
    ],
    output_schema=ContentReview,
    instructions=[
        "Sintetize as avaliacoes de todos os revisores.",
        "A nota final e a media ponderada das notas individuais.",
        "Liste issues combinados de todos os revisores.",
    ],
)
```

#### 2.3 Workflow Nativo do Agno

```python
from agno.workflow.step import Step
from agno.workflow.steps import Steps
from agno.workflow.workflow import Workflow

# Steps do briefing workflow
analyze_step = Step(name="analyze", agent=briefing_agent, description="Analisa briefing")
schedule_step = Step(name="schedule", agent=schedule_agent, description="Gera cronograma")
review_step = Step(name="review", agent=review_agent, description="Revisa conteudo")

briefing_workflow = Workflow(
    name="Agency Briefing Workflow",
    steps=[Steps(
        name="briefing_pipeline",
        steps=[analyze_step, schedule_step, review_step],
    )],
)

# Executar
result = await briefing_workflow.arun(input=briefing_text)
```

### FASE 3: Knowledge e Memory (3-5 semanas)

#### 3.1 Knowledge Base para Brand Guidelines

```python
from agno.knowledge.knowledge import Knowledge
from agno.knowledge.embedder.openai import OpenAIEmbedder
from agno.vectordb.pgvector import PgVector, SearchType

brand_knowledge = Knowledge(
    vector_db=PgVector(
        db_url=settings.database_url,
        table_name="app_brand_knowledge",
        search_type=SearchType.hybrid,
        embedder=OpenAIEmbedder(id="text-embedding-3-small"),
    ),
)

# Inserir guidelines
brand_knowledge.insert(name="ClientAlpha Guidelines", text_content=client_alpha_md_content)
brand_knowledge.insert(name="ClientDelta Guidelines", text_content=client_delta_md_content)
brand_knowledge.insert(name="Default Guidelines", text_content=default_md_content)

# Inserir historico de posts aprovados
brand_knowledge.insert(name="Posts Aprovados ClientAlpha", text_content=approved_posts_text)

# Agente usa knowledge automaticamente
review_agent = Agent(
    knowledge=brand_knowledge,
    search_knowledge=True,  # Busca automatica
    tools=[KnowledgeTools(knowledge=brand_knowledge, think=True, search=True)],
)
```

#### 3.2 Agentic Memory para Preferencias de Clientes

```python
from agno.db.postgres import PostgresDb

db = PostgresDb(db_url=settings.database_url)

briefing_agent = Agent(
    db=db,
    enable_agentic_memory=True,
    user_id_field="client_name",  # Agrupa memorias por cliente
    instructions=[
        "Lembre das preferencias anteriores deste cliente.",
        "Se o cliente ja pediu algo similar, use o padrao anterior.",
        ...
    ],
)
# Apos algumas interacoes:
# ClientAlpha: "Prefere carrosseis com 5 slides, tom premium, hashtags discretas"
# ClientDelta: "Prefere reels com transicoes rapidas, CTAs diretos"
```

#### 3.3 Shared Memory entre Agentes

```python
# Todos os agentes compartilham memoria sobre clientes
db = PostgresDb(db_url=settings.database_url)

briefing_agent = Agent(db=db, enable_agentic_memory=True)
schedule_agent = Agent(db=db, enable_agentic_memory=True)
review_agent = Agent(db=db, enable_agentic_memory=True)

# briefing_agent aprende: "ClientAlpha postou 12 posts/mes nos ultimos 3 meses"
# schedule_agent ja sabe: "Para ClientAlpha, sugerir 12 posts/mes"
```

### FASE 4: Novos Agentes (4-8 semanas)

#### 4.1 Content Generation Agent

```python
content_generator = Agent(
    name="content_generator",
    model=OpenRouter(id="anthropic/claude-sonnet-4"),
    tools=[DuckDuckGoTools(), TavilyTools()],
    knowledge=brand_knowledge,
    search_knowledge=True,
    instructions=[
        "Gere copy para posts de redes sociais.",
        "Busque tendencias atuais relevantes para o segmento.",
        "Siga as guidelines da marca do cliente.",
        "Inclua: caption, hashtags, CTA, sugestao de visual.",
    ],
    output_schema=GeneratedContent,
)
```

#### 4.2 Analytics Agent

```python
from agno.tools.csv import CsvTools

analytics_agent = Agent(
    name="analytics_agent",
    tools=[CsvTools()],
    instructions=[
        "Analise metricas de performance de posts anteriores.",
        "Identifique: melhor horario, tipo mais engajado, hashtags top.",
        "Sugira otimizacoes baseadas em dados.",
    ],
    output_schema=AnalyticsReport,
)
```

#### 4.3 Competitor Analysis Agent

```python
competitor_agent = Agent(
    name="competitor_analyst",
    tools=[DuckDuckGoTools(), Crawl4aiTools(), ExaTools()],
    instructions=[
        "Monitore concorrentes do cliente nas redes sociais.",
        "Identifique tendencias, formatos e estrategias de sucesso.",
        "Sugira oportunidades de diferenciacao.",
    ],
)
```

#### 4.4 Human-in-the-Loop para Publicacao

```python
@tool(requires_confirmation=True)
async def publish_to_social_media(platform: str, content: str, schedule: str) -> str:
    """Publica conteudo em rede social. Requer confirmacao humana."""
    # Integrar com API da plataforma
    return f"Publicado em {platform} agendado para {schedule}"

publication_team = Team(
    members=[content_generator, schedule_agent],
    tools=[publish_to_social_media],
)
```

### FASE 5: Producao e Observabilidade (6-10 semanas)

#### 5.1 AgentOS

```python
from agno.os import AgentOS

agent_os = AgentOS(
    id="marketing-briefing-bot",
    name="Agency Marketing Agency",
    agents=[briefing_agent, review_agent, schedule_agent, summary_agent,
            content_generator, analytics_agent, competitor_agent],
    teams=[briefing_team, content_review_team, publication_team],
    workflows=[briefing_workflow],
    knowledge=[brand_knowledge],
    auto_provision_dbs=True,
)

app = agent_os.get_app()
# Auto-gera endpoints para todos os agentes, times e workflows
```

#### 5.2 Guardrails

```python
# PII Detection - Proteger dados de clientes
# Prompt Injection Prevention
# Content Moderation
```

#### 5.3 Langfuse Tracing

```python
# Observar: Qual agente e mais lento? Qual consome mais tokens?
# Rastrear: Decisoes do lider do team, routing choices
# Alertar: Falhas, timeouts, outputs invalidos
```

---

## 7. ROADMAP DE EVOLUCAO

### Fase 1: Quick Wins (Semanas 1-2)
- [ ] Adicionar ClickUpTools built-in aos agentes
- [ ] Implementar model tiering (Haiku/Sonnet/Opus)
- [ ] Adicionar DuckDuckGoTools ao summary_generator
- [ ] Configurar retry com fallback de modelo

### Fase 2: Teams e Workflows (Semanas 3-6)
- [ ] Criar briefing_team com TeamMode.route por plataforma
- [ ] Criar review_team com TeamMode.broadcast (3 revisores)
- [ ] Migrar workflow manual para Workflow/Steps do Agno
- [ ] Implementar session storage com PostgresStorage

### Fase 3: Knowledge e Memory (Semanas 7-10)
- [ ] Configurar PgVector para brand guidelines
- [ ] Inserir historico de posts aprovados na knowledge base
- [ ] Ativar agentic memory por cliente
- [ ] Compartilhar memoria entre agentes via PostgresDb

### Fase 4: Novos Agentes (Semanas 11-16)
- [ ] Content Generation Agent (copy + hashtags + CTAs)
- [ ] Analytics Agent (metricas + insights)
- [ ] Competitor Analysis Agent (monitoramento)
- [ ] Human-in-the-Loop para publicacao

### Fase 5: Producao (Semanas 17-20)
- [ ] Migrar para AgentOS
- [ ] Implementar guardrails (PII, moderation)
- [ ] Configurar Langfuse tracing
- [ ] Implementar circuit breaker + fallback multi-provedor
- [ ] Dashboard de metricas e custos

---

## ANEXO: COMPARATIVO DE FEATURES

### marketing-bot vs agno-backend

| Feature | marketing-bot | agno-backend |
|---------|-------------|--------------|
| Agentes | 4 | 15+ |
| Tools | 0 | 50+ |
| Teams | 0 | 3+ |
| Workflows | 0 (manual) | 2+ |
| Memory | 0 | Agentic + User + Culture |
| Knowledge | Markdown files | PgVector + Neo4j + RAG |
| Models | 1 (OpenRouter) | 4 tiers + fallback chain |
| Storage | PostgreSQL (basico) | PostgreSQL + Redis + S3 |
| Observability | Token count | Langfuse v3 + OpenTelemetry |
| Authentication | Telegram user IDs | Clerk OAuth |
| API | FastAPI (3 endpoints) | 80+ routers |
| Deployment | AWS ECS | Docker Compose + Multi-stage |

### TeamMode Decision Matrix para Agency

| Caso de Uso Agency | TeamMode Recomendado | Porque |
|------------------|----------------------|--------|
| Briefing por plataforma | `route` | Cada plataforma tem especialista |
| Content review | `broadcast` | Multiplas perspectivas independentes |
| Campanha completa | `tasks` | Pipeline com dependencias |
| Pesquisa + Redacao | `coordinate` | Lider orquestra sequencia |
| Analise competitiva | `coordinate` | Pesquisa + Analise + Relatorio |

---

*Documento preparado como referencia para evolucao do sistema Marketing Briefing Bot*
