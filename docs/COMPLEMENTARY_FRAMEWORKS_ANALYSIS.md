# Analise de Frameworks Complementares para o Sistema Multi-Agentes Agency

> Documento gerado em 2026-02-22 | Analise de 4 frameworks para melhorias no marketing-bot

---

## 1. BMAD-METHOD (Breakthrough Method of Agile AI Driven Development)

**Repo**: https://github.com/bmad-code-org/BMAD-METHOD
**Tipo**: Framework de desenvolvimento agil orientado a IA com agentes especializados

### O Que E
Framework completo de desenvolvimento que define **12+ agentes especializados** (PM, Architect, Dev, QA, UX, Scrum Master, Analyst, Tech Writer) com personas YAML, workflows estruturados, e um sistema de "Party Mode" onde multiplos agentes colaboram numa mesma sessao.

### Padroes Relevantes para Agency

#### 1.1 Definicao de Agentes em YAML
```yaml
agent:
  metadata:
    id: "_bmad/bmm/agents/pm.md"
    name: John
    title: Product Manager
    icon: "\U0001F4CB"
  persona:
    role: Product Manager specializing in collaborative PRD creation
    identity: Product management veteran with 8+ years
    communication_style: "Asks 'WHY?' relentlessly. Direct and data-sharp."
    principles: |
      - PRDs emerge from user interviews, not template filling
      - Ship the smallest thing that validates the assumption
  menu:
    - trigger: CP
      exec: "workflow-create-prd.md"
      description: "[CP] Create PRD"
```

**Aplicacao Agency**: Definir cada agente do sistema (briefing_analyzer, content_reviewer, etc.) com persona YAML rica incluindo identity, communication_style, e principles. Isso torna os agentes mais consistentes e permite configuracao sem alterar codigo Python.

#### 1.2 Teams com Party Mode
```yaml
bundle:
  name: Team Plan and Architect
  agents:
    - analyst
    - architect
    - pm
    - sm
    - ux-designer
  party: "./default-party.csv"
```

**Aplicacao Agency**: Criar "Marketing Party" onde Briefing Analyst + Schedule Generator + Content Reviewer discutem o briefing juntos antes de cada um executar sua parte.

#### 1.3 Workflows Estruturados em Fases
```
1-analysis/     → Analise e pesquisa
2-plan-workflows/ → Planejamento (PRD, specs)
3-solutioning/  → Solucao (epics, stories, arquitetura)
4-implementation/ → Implementacao
```

**Aplicacao Agency**: Organizar workflows do sistema em fases claras:
- Fase 1: Analise de Briefing
- Fase 2: Planejamento (Schedule + Guidelines)
- Fase 3: Producao (Content Generation)
- Fase 4: Revisao e Publicacao

#### 1.4 Scale-Domain-Adaptive
O sistema ajusta a profundidade do planejamento baseado na complexidade do projeto. Bug fix = workflow simples; sistema enterprise = workflow completo.

**Aplicacao Agency**: Para briefings simples (1 post), workflow rapido. Para campanhas completas (12+ posts), workflow completo com todas as fases.

---

## 2. RALPH (Autonomous AI Agent Loop)

**Repo**: https://github.com/snarktank/ralph
**Tipo**: Loop autonomo de execucao baseado em PRD JSON

### O Que E
Ralph e um loop autonomo que executa um AI coding tool (Claude Code ou Amp) repetidamente ate que todos os itens de um PRD estejam completos. Cada iteracao e uma instancia fresca com contexto limpo. Memoria persiste via git history, `progress.txt`, e `prd.json`.

### Padroes Relevantes para Agency

#### 2.1 PRD-Driven Execution (Execucao Orientada a PRD)
```json
{
  "project": "Agency Campaign",
  "branchName": "ralph/campanha-client_alpha-marco",
  "description": "Campanha Instagram ClientAlpha Marco 2026",
  "userStories": [
    {
      "id": "US-001",
      "title": "Analisar briefing do cliente",
      "acceptanceCriteria": [
        "BriefingAnalysis retorna client_name=ClientAlpha",
        "Identificados 12 posts",
        "social_network=instagram"
      ],
      "priority": 1,
      "passes": false
    }
  ]
}
```

**Aplicacao Agency**: Converter briefings de clientes em formato JSON estruturado similar ao prd.json, onde cada "user story" e uma tarefa do workflow (analise, schedule, criacao, revisao, publicacao). O sistema pode executar iterativamente ate todas as tarefas passarem.

#### 2.2 Fresh Context Per Iteration
Cada iteracao do Ralph e uma instancia fresca - sem "memory leak" de contexto. A memoria persiste apenas via:
- `prd.json` (estado das tarefas)
- `progress.txt` (log do que foi feito)
- Git history (codigo)

**Aplicacao Agency**: Para tarefas longas (campanha completa), executar cada agente com contexto fresco, passando apenas o necessario via structured data (Pydantic schemas). Evita confusao de contexto em workflows multi-step.

#### 2.3 Story Sizing Rules
"Cada story deve ser completavel em UMA iteracao (uma context window)."

Regras de sizing:
- Se nao descreve a mudanca em 2-3 frases, e grande demais
- Schema/database primeiro, depois backend, depois UI
- Criterios de aceitacao devem ser VERIFICAVEIS

**Aplicacao Agency**: Ao decompor campanhas em tarefas, cada tarefa deve ser auto-contida e verificavel:
- "Gerar copy para post 1 de ClientAlpha com hashtags e CTA" (verificavel)
- "Fazer toda a campanha" (grande demais - split)

#### 2.4 Progress Tracking
```
# Progress Log
Started: 2026-02-22
---
Iteration 1: US-001 PASSED - Briefing analisado
Iteration 2: US-002 PASSED - Schedule gerado
Iteration 3: US-003 FAILED - Content review score < 7
Iteration 4: US-003 PASSED - Content ajustado e aprovado
```

**Aplicacao Agency**: Implementar logging estruturado de progresso para cada campanha no PostgreSQL.

---

## 3. SUPERPOWERS (Skills for Coding Agents)

**Repo**: https://github.com/obra/superpowers
**Tipo**: Biblioteca de skills composiveis para agentes de desenvolvimento

### O Que E
Sistema de "superpowers" que funciona como skills automaticas para agentes. Quando o agente detecta uma situacao relevante, a skill correspondente e ativada automaticamente. Enfatiza processos rigidos: brainstorming obrigatorio antes de implementar, TDD, debugging sistematico.

### Padroes Relevantes para Agency

#### 3.1 Brainstorming Obrigatorio (HARD-GATE)
```markdown
<HARD-GATE>
Do NOT invoke any implementation skill, write any code, or take any action
until you have presented a design and the user has approved it.
</HARD-GATE>

Checklist:
1. Explore project context
2. Ask clarifying questions (one at a time)
3. Propose 2-3 approaches with trade-offs
4. Present design in sections, get approval
5. Write design doc
6. Transition to implementation
```

**Aplicacao Agency**: Antes de gerar qualquer conteudo, o sistema deve:
1. Analisar briefing completamente
2. Identificar ambiguidades e perguntar (via Telegram)
3. Propor 2-3 abordagens para a campanha
4. Apresentar plano ao usuario para aprovacao
5. SO ENTAO executar geracao de conteudo

#### 3.2 Subagent-Driven Development com Two-Stage Review
```
Per Task:
1. Dispatch implementer subagent
2. Implementer executes + self-reviews
3. Dispatch spec reviewer subagent → Spec compliance check
4. Dispatch code quality reviewer → Quality check
5. Mark task complete
```

**Aplicacao Agency**: Para content creation:
1. Dispatch `content_generator` subagent (gera copy)
2. Dispatch `brand_compliance_reviewer` (verifica guidelines)
3. Dispatch `engagement_quality_reviewer` (verifica qualidade)
4. Marcar tarefa como completa
5. Proximo post...

#### 3.3 Verification Before Completion
"Rodar comandos de verificacao e confirmar output ANTES de declarar que algo esta pronto."

**Aplicacao Agency**: Antes de marcar uma review como "aprovada", o sistema deve:
- Confirmar que score >= threshold
- Confirmar que nao ha issues criticos
- Confirmar que brand guidelines foram atendidas
- Somente entao mover status no ClickUp

#### 3.4 Systematic Debugging (4 Phases)
1. Observe (coletar evidencias)
2. Hypothesize (formar hipoteses)
3. Test (validar hipoteses)
4. Fix (aplicar correcao)

**Aplicacao Agency**: Quando um briefing falha ou content review rejeita:
1. **Observar**: Que parte do output esta errada?
2. **Hipotizar**: Briefing ambiguo? Instructions insuficientes? Modelo errado?
3. **Testar**: Rerun com instrucoes ajustadas
4. **Corrigir**: Atualizar instructions ou guidelines

#### 3.5 Parallel Agent Dispatching
"Quando ha 3+ tarefas independentes, dispatch um agente por dominio. Cada agente tem escopo focado."

**Aplicacao Agency**: Para campanha com 12 posts:
- Agent A: Posts 1-4 (semana 1)
- Agent B: Posts 5-8 (semana 2)
- Agent C: Posts 9-12 (semana 3)
- Todos rodam em paralelo, sem interferencia

---

## 4. OPENCLAW (Personal AI Assistant)

**Repo**: https://github.com/openclaw/openclaw
**Tipo**: Assistente pessoal IA multi-canal (WhatsApp, Telegram, Slack, Discord, etc.)

### O Que E
OpenClaw e um assistente pessoal IA que funciona em multiplos canais de mensagem (WhatsApp, Telegram, Slack, Discord, Signal, iMessage, Teams, WebChat). Tem sistema de skills, identidade de agente, failover de modelos, e e single-user.

### Padroes Relevantes para Agency

#### 4.1 Multi-Channel Architecture
O OpenClaw se conecta a multiplos canais simultaneamente com um unico agente. O gateway unifica as mensagens.

**Aplicacao Agency**: Alem do Telegram, o sistema poderia aceitar briefings via:
- WhatsApp (mais usado por clientes brasileiros)
- Slack (integracao com time interno)
- Email (briefings formais)
- WebChat (interface dedicada)

#### 4.2 Model Failover e Rotation
```
Models config + CLI
Auth profile rotation (OAuth vs API keys) + fallbacks
Model failover (auto-switch when primary fails)
```

**Aplicacao Agency**: Ja recomendamos model tiering. OpenClaw reforça a necessidade de failover automatico entre provedores.

#### 4.3 Skills System
OpenClaw tem um sistema de skills configuravel onde cada skill:
- Tem trigger conditions
- Pode ser habilitada/desabilitada por agente
- Tem contexto isolado

**Aplicacao Agency**: Implementar skills para os agentes Agno:
- `skill_briefing_analysis`: Ativada quando recebe documento/texto
- `skill_content_review`: Ativada quando task muda para "revisao"
- `skill_schedule_generation`: Ativada quando briefing aprovado
- `skill_trend_research`: Ativada para campanhas de conteudo

#### 4.4 Security Defaults (DM Access)
"Treat inbound DMs as untrusted input."

**Aplicacao Agency**: Implementar guardrails:
- Validar que apenas usuarios autorizados podem submeter briefings
- Sanitizar input antes de passar ao agente
- Rate limiting por usuario
- PII detection em conteudo gerado

---

## 5. SINTESE: PADROES APLICAVEIS AO AGENCIA-Agency

### Matriz de Aplicabilidade

| Padrao | Origem | Prioridade | Complexidade | Impacto |
|--------|--------|------------|--------------|---------|
| Agent Persona YAML | BMAD | Alta | Baixa | Agentes mais consistentes |
| PRD-Driven Workflow | Ralph | Alta | Media | Workflows auto-executaveis |
| Brainstorming HARD-GATE | Superpowers | Alta | Baixa | Melhor qualidade de output |
| Two-Stage Review | Superpowers | Alta | Media | Content review mais robusto |
| Fresh Context Per Task | Ralph | Media | Baixa | Evita context pollution |
| Workflow Phases | BMAD | Media | Media | Organizacao clara |
| Multi-Channel | OpenClaw | Media | Alta | WhatsApp support |
| Story Sizing | Ralph | Media | Baixa | Tarefas auto-contidas |
| Parallel Dispatch | Superpowers | Media | Media | Posts em paralelo |
| Model Failover | OpenClaw | Baixa | Media | Resiliencia |
| Scale-Adaptive | BMAD | Baixa | Alta | Ajuste por complexidade |
| Security/Guardrails | OpenClaw | Baixa | Media | Protecao de dados |

### Top 5 Recomendacoes Imediatas

1. **Brainstorming HARD-GATE** (Superpowers): Implementar gate obrigatorio no briefing flow. Antes de gerar qualquer conteudo, o agente DEVE confirmar entendimento com o usuario e propor abordagens.

2. **Two-Stage Review Pattern** (Superpowers): Para content review, usar 2 etapas:
   - Stage 1: Brand compliance check (verifica guidelines)
   - Stage 2: Quality/engagement check (verifica qualidade)

3. **PRD-JSON Task Format** (Ralph): Converter briefings em formato JSON estruturado com acceptance criteria verificaveis para cada tarefa.

4. **Agent Persona YAML** (BMAD): Mover definicoes de agentes de Python hardcoded para YAML com persona rica (identity, communication_style, principles).

5. **Workflow Phases** (BMAD): Organizar os workflows em fases claras: Analysis → Planning → Production → Review → Publication.

### Implementacao Sugerida

```python
# Combinando padroes dos 4 frameworks no Agno:

# 1. Agent Persona via YAML (BMAD pattern)
import yaml

def load_agent_config(agent_name: str) -> dict:
    with open(f"config/agents/{agent_name}.yaml") as f:
        return yaml.safe_load(f)

# 2. PRD-Driven Workflow (Ralph pattern)
class CampaignPRD(BaseModel):
    project: str
    client_name: str
    tasks: list[CampaignTask]

class CampaignTask(BaseModel):
    id: str
    title: str
    acceptance_criteria: list[str]
    priority: int
    passes: bool = False
    notes: str = ""

# 3. Two-Stage Review (Superpowers pattern)
async def two_stage_review(content: str, guidelines: str) -> ReviewResult:
    # Stage 1: Brand compliance
    brand_check = await brand_compliance_agent.arun(
        f"Verifique compliance:\n\nGuidelines:\n{guidelines}\n\nConteudo:\n{content}"
    )
    if not brand_check.content.approved:
        return ReviewResult(stage="brand", passed=False, issues=brand_check.content.issues)

    # Stage 2: Quality check
    quality_check = await quality_reviewer_agent.arun(
        f"Avalie qualidade e engajamento:\n\nConteudo:\n{content}"
    )
    return ReviewResult(
        stage="quality",
        passed=quality_check.content.overall_score >= 7,
        score=quality_check.content.overall_score
    )

# 4. Brainstorming HARD-GATE (Superpowers pattern)
async def handle_briefing_with_gate(briefing_text: str, chat_id: int):
    # HARD-GATE: Confirmar entendimento antes de executar
    analysis = await briefing_agent.arun(briefing_text)

    if analysis.content.observations:  # Se ha ambiguidades
        # Enviar perguntas ao usuario via Telegram
        questions = format_questions(analysis.content.observations)
        await bot.send_message(chat_id, f"Tenho algumas duvidas:\n{questions}")
        return  # HALT - aguardar resposta

    # Propor abordagem
    approaches = await propose_approaches(analysis.content)
    await bot.send_message(chat_id, f"Sugiro estas abordagens:\n{approaches}")
    # HALT - aguardar aprovacao

# 5. Fresh Context (Ralph pattern)
async def execute_campaign_tasks(prd: CampaignPRD):
    for task in sorted(prd.tasks, key=lambda t: t.priority):
        if task.passes:
            continue

        # Fresh agent per task (no context pollution)
        task_agent = create_fresh_agent(task_type=task.type)
        result = await task_agent.arun(json.dumps(task.model_dump()))

        # Verify acceptance criteria
        all_passed = verify_criteria(result, task.acceptance_criteria)
        task.passes = all_passed
        task.notes = result.content.summary

        # Log progress
        log_progress(task.id, task.passes, task.notes)
```

---

*Documento complementar a AGNO_ANALYSIS_AND_RECOMMENDATIONS.md*
*— Orion, orquestrando o sistema*
