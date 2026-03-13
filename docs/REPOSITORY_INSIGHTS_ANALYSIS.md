# Analise de Repositorios: Insights Arquiteturais para Agencia-Agency

> Documento gerado em 2026-02-22 | Analise de 8 repositorios open-source
> Complementa: AGNO_ANALYSIS_AND_RECOMMENDATIONS.md e COMPLEMENTARY_FRAMEWORKS_ANALYSIS.md

---

## REPOSITORIOS ANALISADOS

| # | Repositorio | Tipo | Relevancia |
|---|-------------|------|------------|
| 1 | [SynkraAI/aios-core](https://github.com/SynkraAI/aios-core) | Meta-framework de orquestracao IA | Alta |
| 2 | [rowboatlabs/rowboat](https://github.com/rowboatlabs/rowboat) | Multi-agent orchestration platform | Alta |
| 3 | [BloopAI/vibe-kanban](https://github.com/BloopAI/vibe-kanban) | Kanban board com agentes IA | Media |
| 4 | [nibzard/awesome-agentic-patterns](https://github.com/nibzard/awesome-agentic-patterns) | Catalogo de padroes agenticos | Alta |
| 5 | [qwibitai/nanoclaw](https://github.com/qwibitai/nanoclaw) | Lightweight agent framework | Media |
| 6 | [f/prompts.chat](https://github.com/f/prompts.chat) | Biblioteca de prompts/personas | Media |
| 7 | [JoshuaC215/agent-service-toolkit](https://github.com/JoshuaC215/agent-service-toolkit) | Production agent service template | Alta |
| 8 | [Canner/WrenAI](https://github.com/Canner/WrenAI) | AI data pipeline com multi-step | Media |

---

## 1. PADROES DE ORQUESTRACAO

### 1.1 Agent Registry (aios-core, agent-service-toolkit)

**Conceito**: Registro centralizado onde agentes sao declarados com metadados, capabilities e configuracoes. Permite discovery dinamico e instanciacao sob demanda.

```python
# Padrao observado em aios-core
class AgentRegistry:
    _agents: dict[str, AgentConfig] = {}

    @classmethod
    def register(cls, name: str, config: AgentConfig):
        cls._agents[name] = config

    @classmethod
    def get(cls, name: str) -> Agent:
        config = cls._agents[name]
        return config.factory()

    @classmethod
    def list_capabilities(cls) -> list[str]:
        return [a.capabilities for a in cls._agents.values()]
```

**Aplicacao Agency**: Substituir a instanciacao manual dos 4 agentes em `main.py` por um registry que carregue agentes a partir de configuracao YAML. Permite adicionar novos agentes (trend_researcher, image_generator) sem alterar codigo.

### 1.2 Event Bus / Pub-Sub (aios-core, rowboat)

**Conceito**: Sistema de eventos desacoplado onde agentes publicam e assinam eventos. Elimina dependencias diretas entre componentes.

```python
# Padrao observado
class EventBus:
    _subscribers: dict[str, list[Callable]] = defaultdict(list)

    async def publish(self, event_type: str, data: dict):
        for handler in self._subscribers[event_type]:
            await handler(data)

    def subscribe(self, event_type: str, handler: Callable):
        self._subscribers[event_type].append(handler)

# Uso
bus.subscribe("briefing.analyzed", schedule_generator.on_briefing_ready)
bus.subscribe("briefing.analyzed", notification_service.notify_team)
await bus.publish("briefing.analyzed", {"analysis": result})
```

**Aplicacao Agency**: Desacoplar o fluxo linear atual (analyze → schedule → review) para um modelo baseado em eventos. Permite adicionar side-effects (notificacoes, logging, metricas) sem modificar o fluxo principal.

### 1.3 Workflow State Machine (rowboat, WrenAI)

**Conceito**: Workflows definidos como maquinas de estado com transicoes explicitas, guards e rollback.

```python
# Padrao observado
class WorkflowState(Enum):
    RECEIVED = "received"
    ANALYZING = "analyzing"
    AWAITING_APPROVAL = "awaiting_approval"
    SCHEDULING = "scheduling"
    GENERATING = "generating"
    REVIEWING = "reviewing"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"

TRANSITIONS = {
    WorkflowState.RECEIVED: [WorkflowState.ANALYZING],
    WorkflowState.ANALYZING: [WorkflowState.AWAITING_APPROVAL, WorkflowState.FAILED],
    WorkflowState.AWAITING_APPROVAL: [WorkflowState.SCHEDULING, WorkflowState.ANALYZING],
    WorkflowState.SCHEDULING: [WorkflowState.GENERATING, WorkflowState.FAILED],
    # ...
}
```

**Aplicacao Agency**: O fluxo atual no `handlers.py` e imperativo e linear. Uma state machine permitiria pausar (aguardar aprovacao do usuario), retomar, retry em caso de falha, e visualizar o estado de cada campanha no backoffice.

### 1.4 Task-Type Routing (rowboat)

**Conceito**: Router inteligente que direciona tarefas para o agente mais adequado baseado em classificacao do input.

**Aplicacao Agency**: Quando o bot recebe uma mensagem, classificar a intencao antes de processar:
- Briefing novo → `briefing_analyzer`
- Pedido de alteracao → `content_editor`
- Pergunta sobre status → `status_reporter`
- Feedback sobre conteudo → `content_reviewer`

---

## 2. PADROES DE EXECUCAO

### 2.1 Action Chain Pipeline (vibe-kanban)

**Conceito**: Cadeia de acoes onde cada step recebe o output do anterior, com possibilidade de interceptacao e transformacao entre steps.

```python
# Padrao
class Pipeline:
    steps: list[PipelineStep]

    async def execute(self, input_data: dict) -> dict:
        result = input_data
        for step in self.steps:
            result = await step.run(result)
            if step.should_halt(result):
                break
        return result

# Uso para Agency
briefing_pipeline = Pipeline(steps=[
    ValidateInputStep(),       # Valida formato do input
    AnalyzeBriefingStep(),     # Agente analisa briefing
    ApprovalGateStep(),        # Aguarda aprovacao (HARD-GATE)
    GenerateScheduleStep(),    # Gera cronograma
    CreateClickUpTasksStep(),  # Cria tasks no ClickUp
])
```

**Aplicacao Agency**: Substituir o fluxo procedural em `_process_briefing()` por um pipeline composivel. Cada step e testavel isoladamente e novos steps podem ser adicionados sem modificar os existentes.

### 2.2 Lane-Based Execution Queuing (vibe-kanban)

**Conceito**: Filas de execucao por "lane" (ex: por cliente, por tipo de task) para controlar concorrencia e prioridade.

**Aplicacao Agency**: Quando multiplos clientes enviam briefings simultaneamente, processar em filas separadas por cliente. Evita que um briefing grande de um cliente bloqueie briefings menores de outros.

### 2.3 Wave-Based Parallel Execution (aios-core)

**Conceito**: Agrupar tarefas independentes em "waves" que executam em paralelo, com sync points entre waves.

```
Wave 1 (paralelo): [Analisar Post 1] [Analisar Post 2] [Analisar Post 3]
         ↓ sync
Wave 2 (paralelo): [Gerar Copy 1] [Gerar Copy 2] [Gerar Copy 3]
         ↓ sync
Wave 3 (paralelo): [Review Copy 1] [Review Copy 2] [Review Copy 3]
```

**Aplicacao Agency**: Para campanhas com 12+ posts, executar geracao e revisao em waves paralelas em vez de sequencialmente. Reduz tempo total significativamente.

### 2.4 Background Task with Status Tracking (agent-service-toolkit, WrenAI)

**Conceito**: Tarefas longas executam em background com status tracking via polling ou SSE.

```python
# Padrao observado
class TaskTracker:
    async def submit(self, task: Task) -> str:
        task_id = str(uuid4())
        self._tasks[task_id] = TaskStatus(state="pending")
        asyncio.create_task(self._execute(task_id, task))
        return task_id

    async def get_status(self, task_id: str) -> TaskStatus:
        return self._tasks[task_id]
```

**Aplicacao Agency**: Briefings longos (campanhas completas) demoram varios minutos. Em vez de bloquear o chat do Telegram, submeter como background task e enviar atualizacoes periodicas ao usuario: "Analisando briefing... 30%", "Gerando cronograma... 60%".

---

## 3. PADROES DE QUALIDADE E RESILIENCIA

### 3.1 Approval Gate Service (vibe-kanban, awesome-agentic-patterns)

**Conceito**: Gates explicitos que pausam o workflow ate receber aprovacao humana ou automatica.

**Aplicacao Agency**: Ja identificado como "Brainstorming HARD-GATE" na analise anterior. Reforco: todo workflow deve ter pelo menos um gate antes da geracao de conteudo final.

### 3.2 Schema Validation Retry (awesome-agentic-patterns)

**Conceito**: Quando o LLM retorna output que nao valida contra o schema, reenviar com feedback especifico do erro de validacao.

```python
async def validated_agent_call(agent, prompt, max_retries=3):
    for attempt in range(max_retries):
        try:
            result = await agent.arun(prompt)
            return result.content  # Pydantic validation happens here
        except ValidationError as e:
            prompt = f"{prompt}\n\nERRO ANTERIOR: {e}\nPor favor corrija e retorne JSON valido."
    raise MaxRetriesExceeded()
```

**Aplicacao Agency**: O `briefing_analyzer.py` ja tem retry basico (max_retries=2). Melhorar passando o erro de validacao de volta ao LLM para auto-correcao direcionada.

### 3.3 Two-Stage Review (awesome-agentic-patterns)

**Conceito**: Revisao em 2 etapas independentes: compliance primeiro, qualidade depois.

**Aplicacao Agency**: Ja recomendado na analise de frameworks complementares. Stage 1: Brand compliance (guidelines do cliente). Stage 2: Quality/engagement (qualidade do conteudo).

### 3.4 Reflection Loop (awesome-agentic-patterns)

**Conceito**: Agente gera output, depois "reflete" sobre o proprio output buscando erros, inconsistencias ou melhorias antes de entregar.

```python
# Ciclo: Generate → Reflect → Improve → Deliver
content = await generator.arun(prompt)
reflection = await reflector.arun(
    f"Analise criticamente este conteudo:\n{content}\n\nIdentifique problemas."
)
if reflection.has_issues:
    content = await generator.arun(
        f"Melhore este conteudo:\n{content}\n\nProblemas:{reflection.issues}"
    )
```

**Aplicacao Agency**: Antes de entregar conteudo ao cliente, o agente de geracao deve fazer self-reflection para identificar problemas obvios (tom inadequado, informacao incorreta, hashtags repetidas).

### 3.5 LLM Fallback Chain (agent-service-toolkit, WrenAI)

**Conceito**: Cadeia de fallback entre modelos/provedores. Se o primario falha, tentar o secundario automaticamente.

```python
MODEL_CHAIN = [
    ("openrouter", "anthropic/claude-sonnet-4-20250514"),  # Primary
    ("openrouter", "google/gemini-2.0-flash"),    # Fallback 1
    ("groq", "llama-3.3-70b-versatile"),          # Fallback 2
]
```

**Aplicacao Agency**: Atualmente usa apenas OpenRouter. Implementar chain de fallback para resiliencia. Especialmente importante para o servico de audio (Groq → OpenAI) ja definido no design doc.

### 3.6 Auto-Correction Retry (WrenAI)

**Conceito**: Quando um agente falha, analisar o erro e tentar novamente com contexto corrigido. Diferente do retry simples: aqui o sistema entende o tipo de falha e ajusta a abordagem.

**Aplicacao Agency**: Se o schedule_generator falha porque o briefing tem datas ambiguas, em vez de retry cego, pedir ao briefing_analyzer que extraia as datas com mais contexto, depois tentar schedule novamente.

---

## 4. PADROES DE COMUNICACAO E UX

### 4.1 Progressive Elicitation (rowboat, aios-core)

**Conceito**: Em vez de pedir todas as informacoes de uma vez, solicitar progressivamente conforme o contexto se forma.

**Aplicacao Agency**: Quando um briefing esta incompleto, em vez de listar 5 perguntas de uma vez, perguntar uma por vez via Telegram:
1. "Qual a rede social?" → "Instagram"
2. "Quantos posts?" → "12"
3. "Periodo?" → "Marco inteiro"
4. (sistema ja tem contexto suficiente, nao precisa perguntar mais)

### 4.2 XML-Structured Messages (nanoclaw)

**Conceito**: Usar tags XML para estruturar mensagens internas entre agentes, mantendo clareza semantica.

```xml
<agent_message>
  <from>briefing_analyzer</from>
  <to>schedule_generator</to>
  <context>
    <client>ClientAlpha</client>
    <campaign>Marco 2026</campaign>
  </context>
  <payload>
    <analysis>...</analysis>
  </payload>
</agent_message>
```

**Aplicacao Agency**: Para comunicacao inter-agente (quando usar Teams do Agno), estruturar mensagens com XML tags para reduzir ambiguidade e melhorar parsing.

### 4.3 Chat Persona Builder (prompts.chat)

**Conceito**: Templates de persona ricos que definem tom, estilo, restricoes e exemplos para cada agente.

**Aplicacao Agency**: Ja recomendado como "Agent Persona YAML" (BMAD). O prompts.chat reforça com exemplos praticos de como estruturar personas com few-shot examples incluidos no system prompt.

### 4.4 SSE Streaming (agent-service-toolkit)

**Conceito**: Server-Sent Events para streaming de respostas em tempo real.

**Aplicacao Agency**: Para o backoffice admin, usar SSE para mostrar progresso de campanhas em tempo real sem polling.

---

## 5. PADROES DE INFRAESTRUTURA

### 5.1 Service Container / DI (aios-core, agent-service-toolkit)

**Conceito**: Container de injecao de dependencias para gerenciar lifecycle de servicos.

```python
class ServiceContainer:
    def __init__(self, settings: Settings):
        self._settings = settings
        self._services: dict[str, Any] = {}

    def get_clickup_client(self) -> ClickUpClient:
        if "clickup" not in self._services:
            self._services["clickup"] = ClickUpClient(self._settings.clickup_api_key)
        return self._services["clickup"]

    def get_agent(self, name: str) -> Agent:
        if name not in self._services:
            config = load_agent_config(name)
            self._services[name] = create_agent(config)
        return self._services[name]
```

**Aplicacao Agency**: Centralizar criacao de servicos (ClickUpClient, agentes, DB sessions) em um container. Facilita testes (mock do container) e evita instanciacao duplicada.

### 5.2 Feature Flags (agent-service-toolkit)

**Conceito**: Flags que permitem ativar/desativar funcionalidades sem deploy.

**Aplicacao Agency**: Util para rollout gradual de novas features:
- `ENABLE_AUDIO_BRIEFING=true` (feature nova de audio)
- `ENABLE_TWO_STAGE_REVIEW=false` (ainda em teste)
- `ENABLE_PARALLEL_GENERATION=false` (experimental)

### 5.3 TTLCache para Respostas (agent-service-toolkit)

**Conceito**: Cache com TTL para respostas frequentes de agentes, evitando chamadas redundantes ao LLM.

**Aplicacao Agency**: Cachear resultados de analise de guidelines do cliente (nao mudam frequentemente) e templates de conteudo. Reduz custos de API e latencia.

### 5.4 Context Injection with Token Budget (aios-core)

**Conceito**: Injetar contexto nos prompts dos agentes respeitando um budget de tokens, priorizando informacoes mais relevantes.

**Aplicacao Agency**: Quando passando guidelines do cliente para o agente de review, truncar/sumarizar guidelines longas para caber no budget de tokens do modelo, priorizando as regras mais relevantes para o tipo de post sendo revisado.

### 5.5 Provider Registry (WrenAI)

**Conceito**: Registry de provedores (LLM, STT, storage) com interface uniforme e configuracao via env vars.

```python
class ProviderRegistry:
    _providers = {
        "llm": {"openrouter": OpenRouterProvider, "groq": GroqProvider},
        "stt": {"groq": GroqSTTProvider, "openai": OpenAISTTProvider},
        "storage": {"s3": S3Provider, "local": LocalProvider},
    }

    def get(self, category: str, name: str) -> Provider:
        return self._providers[category][name]()
```

**Aplicacao Agency**: Unificar acesso a provedores de LLM, STT (audio), e storage sob uma interface comum. Permite trocar provedores via configuracao.

---

## 6. PADROES AGENTICOS AVANCADOS

### 6.1 Intent Classification (agent-service-toolkit)

**Conceito**: Classificar a intencao do usuario antes de rotear para o agente correto. Usa um modelo leve/rapido para classificacao.

```python
INTENTS = {
    "new_briefing": "Usuario quer enviar briefing novo",
    "edit_request": "Usuario quer alterar conteudo existente",
    "status_check": "Usuario quer saber status de campanha",
    "feedback": "Usuario esta dando feedback sobre conteudo",
    "question": "Usuario tem duvida sobre o sistema",
}
```

**Aplicacao Agency**: O handler atual assume que toda mensagem de texto e um briefing. Com intent classification, o bot pode responder adequadamente a diferentes tipos de mensagem.

### 6.2 Agent-as-Tool (rowboat)

**Conceito**: Expor agentes como tools para outros agentes, permitindo composicao dinamica.

**Aplicacao Agency**: O `content_reviewer` poderia chamar o `briefing_analyzer` como tool para re-analisar partes do briefing quando encontra inconsistencias no conteudo.

### 6.3 Map-Reduce para Campanhas (awesome-agentic-patterns)

**Conceito**: Dividir uma tarefa grande em sub-tarefas (map), executar em paralelo, e agregar resultados (reduce).

```
MAP:    Campanha 12 posts → [Post1, Post2, ..., Post12]
EXEC:   [Copy1, Copy2, ..., Copy12]  (paralelo)
REDUCE: [Review + Score consolidado] → Campanha final
```

**Aplicacao Agency**: Para geracao de conteudo de campanhas grandes, mapear cada post como tarefa independente, gerar em paralelo, e reduzir com revisao consolidada que verifica coerencia entre os posts.

### 6.4 Episodic Memory (awesome-agentic-patterns)

**Conceito**: Agentes manteem "memoria episodica" de interacoes passadas com cada cliente, influenciando comportamento futuro.

**Aplicacao Agency**: Armazenar no PostgreSQL:
- Feedbacks anteriores do cliente
- Tipos de conteudo que tiveram melhor performance
- Preferencias de linguagem/tom
- Erros anteriores para evitar repeticao

### 6.5 Prompt Builder DSL (nanoclaw)

**Conceito**: DSL (Domain-Specific Language) para construir prompts de forma programatica com composicao.

```python
prompt = (
    PromptBuilder()
    .system("Voce e um copywriter especializado em {niche}")
    .context("Guidelines do cliente:", client_guidelines)
    .context("Posts anteriores:", previous_posts)
    .task("Crie {count} posts para Instagram sobre {topic}")
    .constraints(["Max 2200 caracteres", "Incluir 5-10 hashtags"])
    .format("JSON com campos: copy, hashtags, cta")
    .build(niche="estetica", count=3, topic="lancamento produto")
)
```

**Aplicacao Agency**: Em vez de hardcodar prompts nas instructions dos agentes, usar um builder que compoe prompts dinamicamente com contexto do cliente, guidelines e tarefas especificas.

### 6.6 Quality Gates com Metricas (aios-core)

**Conceito**: Gates que verificam metricas quantitativas antes de permitir progresso no workflow.

```python
QUALITY_GATES = {
    "briefing_analysis": {
        "min_fields_extracted": 5,
        "confidence_threshold": 0.7,
    },
    "content_review": {
        "min_overall_score": 7,
        "max_critical_issues": 0,
        "required_checks": ["brand_compliance", "hashtag_count", "cta_present"],
    },
}
```

**Aplicacao Agency**: Formalizar os criterios de qualidade em configuracao. O review atual no `content_reviewer` usa score numerico mas sem gates formais.

---

## 7. MATRIZ DE PRIORIDADE

### Alta Prioridade (Implementar em Sprint 1-2)

| # | Padrao | Origem | Impacto | Complexidade |
|---|--------|--------|---------|--------------|
| 1 | Intent Classification | agent-service-toolkit | Alto | Baixa |
| 2 | Pipeline (Action Chain) | vibe-kanban | Alto | Media |
| 3 | Schema Validation Retry | awesome-agentic-patterns | Alto | Baixa |
| 4 | Background Task + Status | agent-service-toolkit | Alto | Media |
| 5 | Service Container / DI | aios-core | Alto | Media |
| 6 | Approval Gate Service | vibe-kanban | Alto | Baixa |

### Media Prioridade (Sprint 3-4)

| # | Padrao | Origem | Impacto | Complexidade |
|---|--------|--------|---------|--------------|
| 7 | Event Bus | aios-core | Medio | Media |
| 8 | Reflection Loop | awesome-agentic-patterns | Medio | Baixa |
| 9 | LLM Fallback Chain | agent-service-toolkit | Medio | Media |
| 10 | Wave-Based Parallel | aios-core | Medio | Alta |
| 11 | Workflow State Machine | rowboat | Medio | Alta |
| 12 | Progressive Elicitation | rowboat | Medio | Media |

### Baixa Prioridade (Sprint 5+)

| # | Padrao | Origem | Impacto | Complexidade |
|---|--------|--------|---------|--------------|
| 13 | Agent Registry | aios-core | Baixo | Media |
| 14 | Feature Flags | agent-service-toolkit | Baixo | Baixa |
| 15 | Map-Reduce Campanhas | awesome-agentic-patterns | Baixo | Alta |
| 16 | Episodic Memory | awesome-agentic-patterns | Baixo | Alta |
| 17 | Provider Registry | WrenAI | Baixo | Media |
| 18 | Prompt Builder DSL | nanoclaw | Baixo | Media |

---

## 8. RECOMENDACOES CONSOLIDADAS

### Top 5 Acoes Imediatas

1. **Intent Classification no Handler** — Classificar mensagens recebidas antes de processar. Evita tratar perguntas como briefings. Implementar com prompt simples usando modelo rapido (Groq llama).

2. **Pipeline Composivel** — Refatorar `_process_briefing()` em steps composiveis. Cada step (validate → analyze → gate → schedule → create_tasks) e um componente testavel e reutilizavel.

3. **Schema Validation com Feedback** — Melhorar retry do `briefing_analyzer` passando o erro de validacao Pydantic de volta ao LLM para auto-correcao direcionada.

4. **Background Processing + Status Updates** — Para briefings longos, processar em background e enviar atualizacoes de progresso via Telegram ("Analisando... 30%").

5. **Service Container** — Centralizar instanciacao de servicos em um container. Facilita testes e evita duplicacao de codigo em `main.py`.

### Padroes que Reforçam Recomendacoes Anteriores

Os seguintes padroes validam recomendacoes ja feitas nos documentos anteriores:

| Padrao (Novo) | Recomendacao Anterior | Documento |
|---------------|----------------------|-----------|
| Approval Gate Service | Brainstorming HARD-GATE | COMPLEMENTARY_FRAMEWORKS |
| Two-Stage Review | Two-Stage Review Pattern | COMPLEMENTARY_FRAMEWORKS |
| LLM Fallback Chain | Model Tiering + Failover | AGNO_ANALYSIS |
| Agent Registry | Agent Persona YAML | COMPLEMENTARY_FRAMEWORKS |
| Wave-Based Parallel | Parallel Agent Dispatching | COMPLEMENTARY_FRAMEWORKS |
| Quality Gates | Verification Before Completion | COMPLEMENTARY_FRAMEWORKS |

---

## 9. ARQUITETURA PROPOSTA (Combinando Todos os Insights)

```
┌─────────────────────────────────────────────────────────────┐
│                    TELEGRAM BOT LAYER                        │
│  ┌─────────┐  ┌──────────┐  ┌────────┐  ┌──────────────┐   │
│  │  Text   │  │  Audio   │  │  PDF   │  │  Callback    │   │
│  │ Handler │  │ Handler  │  │Handler │  │  Handler     │   │
│  └────┬────┘  └────┬─────┘  └───┬────┘  └──────────────┘   │
│       └────────────┼────────────┘                            │
│                    ▼                                          │
│          ┌─────────────────┐                                 │
│          │ Intent Classifier│  ← Modelo leve (Groq)          │
│          └────────┬────────┘                                 │
│     ┌─────────────┼─────────────┐                            │
│     ▼             ▼             ▼                             │
│ [Briefing]   [Status]    [Feedback]                          │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                   PIPELINE LAYER                             │
│                                                              │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐   │
│  │ Validate │→ │ Analyze  │→ │ Approval │→ │ Schedule  │   │
│  │  Input   │  │ Briefing │  │   Gate   │  │ Generate  │   │
│  └──────────┘  └──────────┘  └──────────┘  └─────┬─────┘   │
│                                                    │         │
│  ┌──────────────┐  ┌──────────────┐  ┌────────────┐│        │
│  │ Brand Review  │← │Content Gen   │← │ClickUp     ││        │
│  │ (Stage 1)     │  │ (Wave-based) │  │ Tasks      │┘        │
│  └──────┬───────┘  └──────────────┘  └────────────┘         │
│         ▼                                                    │
│  ┌──────────────┐                                            │
│  │Quality Review│                                            │
│  │ (Stage 2)    │                                            │
│  └──────────────┘                                            │
└─────────────────────────────────────────────────────────────┘
          │
          ▼
┌─────────────────────────────────────────────────────────────┐
│                 INFRASTRUCTURE LAYER                          │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Service    │  │   Provider   │  │  Background Task   │  │
│  │  Container  │  │   Registry   │  │  Tracker + Status  │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Event Bus  │  │  TTL Cache   │  │  Episodic Memory   │  │
│  └─────────────┘  └──────────────┘  └────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

*Documento complementar a AGNO_ANALYSIS_AND_RECOMMENDATIONS.md e COMPLEMENTARY_FRAMEWORKS_ANALYSIS.md*
*Baseado na analise de 8 repositorios open-source por 4 agentes de pesquisa paralelos*
*— Orion, orquestrando o sistema*
