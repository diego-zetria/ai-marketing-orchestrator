# Agencia Agency -- Arquitetura AWS Consolidada

> **Documento Executivo de Arquitetura** | 2026-02-22
> **Baseado em:** 4 documentos de pesquisa AWS (Serverless, Bedrock, Step Functions, Architecture Patterns)
> **Decisao-chave:** AWS nativo. Zero n8n/Make/Zapier.
> **Stack atual:** Python + Telegram Bot + ClickUp API + Agno Framework + OpenRouter + PostgreSQL

---

## Indice

1. [Resumo Executivo](#1-resumo-executivo)
2. [Decisoes Arquiteturais Consolidadas](#2-decisoes-arquiteturais-consolidadas)
3. [Arquitetura Recomendada](#3-arquitetura-recomendada)
4. [Servicos AWS -- Mapa Completo](#4-servicos-aws--mapa-completo)
5. [Workflows com Step Functions](#5-workflows-com-step-functions)
6. [Estrategia Bedrock](#6-estrategia-bedrock)
7. [Estimativa de Custos](#7-estimativa-de-custos)
8. [Stack de Observabilidade](#8-stack-de-observabilidade)
9. [Seguranca](#9-seguranca)
10. [Roadmap de Implementacao](#10-roadmap-de-implementacao)
11. [Indice de Fontes](#11-indice-de-fontes)

---

## 1. Resumo Executivo

### O Que Este Documento Resolve

Este documento consolida 4 pesquisas tecnicas independentes em um unico plano de acao para migrar o sistema da Agencia Agency para AWS nativo. Cada recomendacao aqui mapeia diretamente para uma necessidade real do sistema: receber briefings via Telegram, gerar conteudo com IA, obter aprovacao humana, agendar publicacoes e integrar com ClickUp.

### Decisoes Fundamentais

| Decisao | Escolha | Razao Principal |
|---------|---------|-----------------|
| **Orquestracao de workflows** | Step Functions (nao n8n/Make/Zapier) | Human-in-the-loop nativo, paralelismo de 10.000, zero custo em idle |
| **Orquestracao de agentes IA** | Manter Agno Framework | Mais flexivel e Pythonico que Bedrock Agents |
| **Provedor LLM** | Bedrock SDK direto (eliminar OpenRouter) | Elimina fee de 5.5%, habilita Intelligent Routing |
| **Modelo para geracao** | Multi-modelo (Nova Micro/Pro + Claude) | 70% das chamadas no modelo barato, 30-60% economia |
| **Compute principal** | Lambda (Fargate so para bot e batch) | Pay-per-use real, free tier generoso |
| **Banco de dados estado** | DynamoDB (manter PostgreSQL via RDS para dados relacionais) | Serverless, TTL automatico, performance em ms |
| **Seguranca LLM** | Bedrock Guardrails | LGPD compliance plug-and-play, custo de $0.60/mes |
| **RAG para brand guidelines** | Bedrock Knowledge Bases + S3 Vectors | 90% mais barato que vector DB tradicional |
| **IaC** | CDK Python | Time ja usa Python, mais expressivo que SAM/Terraform |

### Custo Total Estimado

| Fase | Clientes | Custo Mensal AWS | Custo Equivalente n8n/Zapier |
|------|----------|-----------------|------------------------------|
| **MVP** | 1-5 | **~$25-35/mes** | $50-150/mes |
| **Producao** | 10 | **~$45-65/mes** | $100-300/mes |
| **Escala** | 50 | **~$80-120/mes** | $300-800/mes |

### Por que AWS Nativo e Nao n8n/Make/Zapier

Os 4 documentos de pesquisa convergem nos mesmos pontos:

1. **Custo em escala**: AWS serverless e pay-per-use real. n8n/Make/Zapier cobram planos fixos que escalam linearmente.
2. **Human-in-the-loop**: Step Functions tem `waitForTaskToken` nativo -- o workflow pausa sem consumir recursos por ate 1 ano. n8n tem Wait Node limitado (1h gratis, 7 dias no Pro) e perde estado se reiniciar.
3. **Paralelismo**: Step Functions Map State gera 12 posts em paralelo em 15 segundos. n8n `Split In Batches` e sequencial, leva 2-3 minutos.
4. **Bedrock direto**: Step Functions invoca Bedrock sem Lambda intermediario. n8n precisa de HTTP Request para APIs de IA.
5. **Retry inteligente**: Backoff exponencial com jitter, fallback para modelo alternativo, DLQ. n8n tem retry simples on/off.
6. **Observabilidade**: CloudWatch + X-Ray com GenAI Observability nativo. n8n tem logs basicos.
7. **Seguranca**: IAM least-privilege, VPC, Secrets Manager, Bedrock Guardrails. n8n tem seguranca basica.

---

## 2. Decisoes Arquiteturais Consolidadas

### 2.1 O Que Todos os 4 Documentos Concordam

Apos cruzar os 4 documentos de pesquisa, estas sao as conclusoes unanimes:

| Topico | Consenso | Fonte |
|--------|----------|-------|
| Lambda e suficiente para 90% dos workloads Agency | Briefings, geracao, notificacao -- tudo cabe em Lambda | Doc 1, 3, 4 |
| Step Functions e o coracao da orquestracao | Substitui n8n/Make para fluxos internos | Doc 1, 3 |
| Bedrock para infra de IA, Agno para logica | Nao migrar agentes para Bedrock Agents | Doc 2, 4 |
| SQS como buffer obrigatorio | Nunca chamar Lambda direto; SQS absorve picos e garante retry | Doc 1, 3, 4 |
| EventBridge Scheduler para agendamentos | Substitui cron do n8n/Make com timezone nativa | Doc 1, 3 |
| DynamoDB para estado de workflows | Serverless, TTL, GSI para consultas por cliente | Doc 1, 4 |
| S3 para midias e conteudo gerado | Lifecycle policies para arquivamento automatico | Doc 1, 4 |
| CDK Python para IaC | Time ja usa Python; CDK e mais expressivo | Doc 3, 4 |
| Lambdas fora da VPC para APIs externas | Elimina NAT Gateway ($33/mes), maior economia de custo fixo | Doc 4 |
| ARM/Graviton em tudo | 20% mais barato que x86 em Lambda e Fargate | Doc 4 |

### 2.2 Bedrock: O Que Usar vs O Que Pular

Baseado exclusivamente no documento de pesquisa Bedrock (Doc 2):

| Feature Bedrock | Usar? | Razao | Prioridade |
|----------------|-------|-------|------------|
| **Model Access (SDK direto)** | SIM | Elimina OpenRouter e fee de 5.5% | P1 |
| **Intelligent Prompt Routing** | SIM | 30-60% economia automatica entre Haiku/Sonnet | P1 |
| **Guardrails** | SIM | LGPD compliance + brand safety por $0.60/mes | P1 |
| **Knowledge Bases + S3 Vectors** | SIM | RAG gerenciado para brand guidelines | P2 |
| **Batch Inference** | SIM | 50% desconto para geracao em massa mensal | P2 |
| **Evaluations** | SIM | Escolher modelo otimo por tarefa | P3 |
| **Bedrock Agents** | NAO | Agno e mais flexivel e Pythonico | -- |
| **Bedrock Flows** | NAO | Python workflows do Agno sao superiores | -- |
| **AgentCore** | NAO (avaliar em 6 meses) | Volume insuficiente atualmente | -- |
| **Multi-Agent Collaboration** | NAO (avaliar em 6 meses) | Agency ainda nao usa Teams do Agno | -- |
| **Prompt Management** | OPCIONAL | Util se time nao-tecnico editar prompts | P3 |

### 2.3 Step Functions: Quando Usar vs Lambda Direto

| Cenario | Solucao | Motivo |
|---------|---------|--------|
| Pipeline completo briefing -> publicacao | **Step Functions Standard** | Precisa de waitForTaskToken para aprovacao humana |
| Geracao de 12 posts em paralelo | **Step Functions Map State** | Paralelismo nativo de ate 10.000 |
| Aprovacao humana via Telegram | **Step Functions Standard** | Token persiste por ate 1 ano sem custo |
| Publicacao agendada de posts | **Step Functions + EventBridge** | Cron com timezone + orquestracao |
| Analise simples de um briefing | **Lambda direto (via SQS)** | Rapido (<15s), sem necessidade de orquestracao |
| Webhook do Telegram | **Lambda via API Gateway** | Fire-and-forget, sem estado |
| Notificacao no Telegram | **Lambda direto** | Fire-and-forget, poucos segundos |
| Integracao com ClickUp | **Lambda direto** | Chamada de API simples |
| Processamento de video em lote | **ECS Fargate task** | Excede 15 min do Lambda |

### 2.4 ECS Fargate vs Lambda: Matriz de Decisao

| Criterio | Lambda | ECS Fargate | Decisao Agency |
|----------|--------|-------------|-------------|
| Duracao | Ate 15 min | Ilimitado | Lambda para 95% dos casos |
| Memoria | Ate 10 GB | Ate 120 GB | Lambda suficiente |
| Cold start | 1-16s (SnapStart: 1.6s) | Nenhum (always-on) | Lambda com SnapStart |
| Custo idle | $0 (scale-to-zero) | $7-14/mes (minimo) | Lambda para event-driven |
| Bot Telegram | Webhook mode (Lambda) | Polling mode (ECS) | **Lambda webhook no MVP, ECS na Fase 2** |
| Batch content | Lambda se < 15 min | ECS se > 15 min | Lambda primeiro, ECS se necessario |
| Custo break-even | Vence ate ~40% utilizacao | Vence acima de ~50% | Lambda no MVP |

**Decisao final:** Lambda para tudo no MVP. ECS Fargate apenas na Fase 2 se o bot precisar de conexao persistente ou para processamento de video/batch longo.

---

## 3. Arquitetura Recomendada

### 3.1 Diagrama Completo da Arquitetura

```
          AGENCIA Agency -- ARQUITETURA AWS NATIVA CONSOLIDADA
          ==================================================

  CAMADA DE ENTRADA
  =================

  +------------------+         +------------------+         +------------------+
  |   Telegram Bot   |--POST-->|   API Gateway    |-------->|    Lambda:       |
  |   (Briefings,    |         |   (REST API)     |         |    WebhookRouter |
  |    Aprovacoes,   |         |   + Authorizer   |         |    - Classifica  |
  |    Comandos)     |         +------------------+         |    - Roteia      |
  +------------------+                                      +--------+---------+
                                                                     |
                         +-------------------------------------------+
                         |                     |                     |
                         v                     v                     v
  +------------------+  +------------------+  +------------------+
  | SQS:             |  | SQS:             |  | Lambda:          |
  | briefing-queue   |  | approval-queue   |  | ProcessApproval  |
  | (buffer + retry) |  | (callbacks)      |  | (SF callback)    |
  +--------+---------+  +--------+---------+  +------------------+
           |                     |
           v                     v

  CAMADA DE ORQUESTRACAO
  ======================

  +-----------------------------------------------------------------------+
  |                    STEP FUNCTIONS: Content Pipeline                     |
  |                                                                        |
  |  [Validar]-->[Classificar]-->[Gerar Cronograma]-->[MAP: 12 posts]     |
  |  (Lambda)    (Bedrock       (Bedrock              (Bedrock paralelo)  |
  |              Nova Micro)     Nova Pro)                    |            |
  |                                                          v            |
  |                                           [Salvar S3 + DynamoDB]      |
  |                                                          |            |
  |                                           [Notificar Telegram]        |
  |                                           (SNS -> Lambda)             |
  |                                                          |            |
  |                                           [Wait: Aprovacao Humana]    |
  |                                           (waitForTaskToken)          |
  |                                                          |            |
  |                                           [Choice: Aprovado?]         |
  |                                            /            \             |
  |                                     [Agendar]      [Revisar]          |
  |                                     (EventBridge)  (Loop back)        |
  +-----------------------------------------------------------------------+

  CAMADA DE IA (Bedrock)
  ======================

  +------------------+  +------------------+  +------------------+
  | Intelligent      |  | Guardrails       |  | Knowledge Bases  |
  | Prompt Routing   |  | - PII/LGPD       |  | - Brand Guide    |
  | Haiku <-> Sonnet |  | - Content Safety |  | - Tom de Voz     |
  | Nova Lite <-> Pro|  | - Brand Terms    |  | - Historico Camp.|
  | 30-60% economia  |  | $0.60/mes        |  | S3 Vectors       |
  +------------------+  +------------------+  +------------------+

  CAMADA DE ARMAZENAMENTO
  =======================

  +------------------+  +------------------+  +------------------+
  |  S3 Buckets      |  |  DynamoDB        |  |  RDS PostgreSQL  |
  |  - briefings/    |  |  - BriefingState |  |  - Dados relac.  |
  |  - content/      |  |  - ContentCache  |  |  - Historico     |
  |  - templates/    |  |  - ClientConfig  |  |  - Analytics     |
  |  - media/        |  |  - AgentMemory   |  |  (Alembic)       |
  |  - analytics/    |  |  - PublishSched. |  +------------------+
  +------------------+  +------------------+

  CAMADA DE SAIDA
  ===============

  +------------------+         +------------------+
  | EventBridge      |-------->| Lambda:          |
  | Scheduler        |         | PublishContent   |
  | - Posts agendados|         | - Instagram API  |
  | - Analytics      |         | - Facebook API   |
  | - Relatorios     |         | - LinkedIn API   |
  +------------------+         +--------+---------+
                                        |
  +------------------+                  v
  | SNS Topics       |  +------------------+  +------------------+
  | - content-review |  | Lambda:          |  | Lambda:          |
  | - published      |  | ClickUpCreator   |  | TelegramNotifier |
  | - errors         |  | (cria tasks)     |  | (notifica equipe)|
  | - daily-digest   |  +------------------+  +------------------+
  +------------------+

  CAMADA DE OBSERVABILIDADE
  =========================

  +-----------------------------------------------------------------------+
  | CloudWatch                                                             |
  | - Logs centralizados (Lambda, Step Functions)                         |
  | - Metricas customizadas: tokens, latencia, pipeline duration          |
  | - Alarmes: DLQ > 0, erro > 5%, latencia > 30s, custo Bedrock > $50   |
  | - Dashboard operacional: Agency-Marketing-Ops                            |
  | - GenAI Observability (GA Out/2025): dashboards pre-construidos IA    |
  | - X-Ray: tracing distribuido end-to-end                               |
  +-----------------------------------------------------------------------+
```

### 3.2 Fluxo End-to-End: Telegram -> Processamento -> ClickUp

```
1. Cliente envia briefing via Telegram
   |
2. API Gateway recebe webhook POST -> Lambda WebhookRouter
   |
3. WebhookRouter classifica tipo (briefing / aprovacao / comando)
   |
4. Se briefing:
   |  -> Salva em DynamoDB (status: received)
   |  -> Envia para SQS briefing-queue
   |  -> SQS dispara Step Functions Content Pipeline
   |
5. Step Functions executa pipeline:
   |  5a. Lambda valida briefing
   |  5b. Bedrock Nova Micro classifica tipo de conteudo
   |  5c. Bedrock Nova Pro gera cronograma de 12 posts
   |  5d. Lambda parseia cronograma em array
   |  5e. MAP STATE: 12 chamadas paralelas ao Bedrock
   |      - Cada post: Bedrock gera texto + hashtags + CTA
   |      - Bedrock Guardrails valida cada output
   |      - Salva em S3 + DynamoDB (status: generated)
   |  5f. SNS notifica equipe via Telegram com preview
   |
6. Step Functions PAUSA (waitForTaskToken) -- zero custo
   |
7. Equipe revisa via Telegram Bot (botoes inline: Aprovar/Rejeitar/Revisar)
   |
8. Lambda ProcessApproval recebe callback -> SendTaskSuccess/Failure
   |
9. Step Functions RESUME:
   |  Se aprovado -> EventBridge Scheduler agenda publicacao
   |  Se revisao  -> Loop back para geracao com feedback
   |
10. Na hora agendada:
    |  -> Lambda PublishContent publica via API da plataforma
    |  -> Lambda ClickUpCreator cria/atualiza task
    |  -> Lambda TelegramNotifier confirma publicacao
    |  -> DynamoDB atualizado (status: published)
    |
11. CloudWatch registra todas as metricas e logs
```

---

## 4. Servicos AWS -- Mapa Completo

### 4.1 Tabela de Todos os Servicos Recomendados

| Servico AWS | Proposito no Agency | Custo Mensal (50 cli) | Prioridade | Substitui do n8n/Make/Zapier |
|-------------|-----------------|----------------------|------------|------------------------------|
| **Lambda** | Processar briefings, gerar conteudo, notificar, publicar | ~$2.00 | P1 (MVP) | Nodes de execucao |
| **API Gateway** | Webhook do Telegram, REST API | ~$0.20 | P1 (MVP) | Webhook trigger nodes |
| **Step Functions** | Pipeline de conteudo, aprovacao, agendamento | ~$0.05 | P1 (MVP) | Workflow engine inteiro |
| **SQS** | Buffer de briefings, retry automatico, DLQ | ~$0.00 | P1 (MVP) | Queue nodes (limitados) |
| **SNS** | Fan-out de notificacoes (Telegram + email + Slack) | ~$0.00 | P1 (MVP) | Notification nodes |
| **EventBridge** | Event bus + agendamento de publicacoes | ~$0.00 | P1 (MVP) | Scheduler/Cron nodes |
| **DynamoDB** | Estado de briefings, cache, config de clientes | ~$0.50 | P1 (MVP) | Database nodes (Airtable, Sheets) |
| **S3** | Midias, conteudo gerado, templates, backups | ~$1.42 | P1 (MVP) | File storage nodes |
| **Bedrock** | LLM multi-modelo (Nova, Claude), geracao de conteudo | ~$8-15 | P1 (MVP) | OpenAI/AI nodes |
| **Bedrock Guardrails** | PII/LGPD, content safety, brand protection | ~$0.60 | P1 (MVP) | Nao existe equivalente |
| **Secrets Manager** | API keys (Telegram, ClickUp, Bedrock) | ~$2.00 | P1 (MVP) | Credentials storage (basico) |
| **CloudWatch** | Logs, metricas, alarmes, dashboards | ~$8.30 | P1 (MVP) | Execution logs (basicos) |
| **Bedrock Knowledge Bases** | RAG com brand guidelines, historico de campanhas | ~$10.00 | P2 | Nao existe equivalente |
| **Bedrock Intelligent Routing** | Roteamento automatico Haiku <-> Sonnet | Incluso | P2 | Nao existe equivalente |
| **X-Ray** | Tracing distribuido end-to-end | ~$1.00 | P2 | Nao existe equivalente |
| **RDS PostgreSQL** | Dados relacionais, migrations (Alembic) | ~$12-25 | P2 | Nao existe equivalente |
| **ECS Fargate** | Bot Telegram always-on, batch processing | ~$7-14 | P2 | Nao existe equivalente |
| **SES** | Email marketing, relatorios para clientes | ~$0.10 | P3 | Email nodes |
| **Nova Canvas** | Geracao de imagens de marketing | ~$4.00 | P3 | DALL-E/Midjourney nodes |
| **Nova Reel** | Videos curtos para Reels/TikTok | Sob demanda | P3 | Nao existe equivalente |
| **Bedrock Batch Inference** | Geracao em massa mensal (50% desconto) | Variavel | P3 | Nao existe equivalente |

### 4.2 O Que Cada Servico Substitui do Stack Anterior

```
ANTES (n8n/Make/Zapier + OpenRouter)          DEPOIS (AWS Nativo)
==========================================    ==========================================
Workflow engine (n8n/Make)                --> Step Functions + EventBridge
Webhook triggers                          --> API Gateway + Lambda
HTTP Request nodes (APIs)                 --> Lambda functions
Schedule/Cron nodes                       --> EventBridge Scheduler
OpenRouter (LLM proxy + 5.5% fee)         --> Bedrock SDK direto (0% fee)
Claude via OpenRouter                     --> Claude via Bedrock + Intelligent Routing
Nenhum (gap)                              --> Bedrock Guardrails (LGPD)
Nenhum (gap)                              --> Bedrock Knowledge Bases (RAG)
Google Sheets/Airtable                    --> DynamoDB
File storage manual                       --> S3 com lifecycle
Logs basicos                              --> CloudWatch + X-Ray
Sem retry robusto                         --> SQS + DLQ + backoff exponencial
Sem human-in-the-loop nativo              --> Step Functions waitForTaskToken
Paralelismo limitado (~3-5)               --> Map State (ate 10.000 paralelos)
```

---

## 5. Workflows com Step Functions

### 5.1 Workflow 1: Content Pipeline (Principal)

Este e o workflow mais importante do sistema. Cobre o fluxo completo desde receber um briefing ate publicar conteudo.

```
[Receber Briefing] --> [Validar] --> [Classificar Tipo] --> [Gerar Cronograma]
    (Input)          (Lambda)     (Bedrock Nova Micro)    (Bedrock Nova Pro)
                                                                |
                                                    [Parsear Cronograma]
                                                         (Lambda)
                                                                |
                                                    [MAP: Gerar 12 Posts]
                                                    (Bedrock x12 paralelo)
                                                        |           |
                                                [Guardrails]  [Salvar S3]
                                                (Brand check)  (+ DynamoDB)
                                                        |
                                                [Notificar Revisao]
                                                (SNS -> Telegram)
                                                        |
                                                [Aguardar Aprovacao]  <-- Pausa sem custo
                                                (waitForTaskToken)       ate 48h (config.)
                                                        |
                                                [Choice: Aprovado?]
                                                /               \
                                        [Agendar]           [Revisar]
                                        (EventBridge)        (Loop back)
```

**Numeros-chave:**
- ~60 transicoes por execucao de pipeline
- 10 campanhas/mes = 600 transicoes = **$0.015/mes** em Step Functions
- 12 posts paralelos gerados em ~15 segundos (vs 2-3 min no n8n)
- Timeout de aprovacao: 48h (configuravel ate 1 ano)

### 5.2 Workflow 2: Human-in-the-Loop (Aprovacao via Telegram)

```
Step Functions                    Lambda                       Telegram
===============                   ======                       ========

[Estado anterior]
       |
       v
[Solicitar Aprovacao]   --->  [Lambda: Envia msg]  --->  [Bot envia msg com
 (.waitForTaskToken)          [Salva token no DDB]        botoes inline:
                                                          Aprovar / Rejeitar
 PAUSA SEM CUSTO...                                       / Pedir Revisao]
 (ate 48h)
                                                          Usuario clica
                                                               |
                              [Lambda: Callback   ]  <--- [Telegram Callback
                              [Handler busca token]        Query]
                              [SendTaskSuccess]
       |
 ...RESUME
       |
       v
[Choice: aprovado / rejeitado / revisao]
```

**Diferencial vs n8n:**
- Step Functions: Token persiste ate 1 ano, zero custo durante espera, estado duravel
- n8n: Wait Node limitado (1h gratis, 7 dias Pro), webhook precisa estar online, perde estado se reiniciar

### 5.3 Workflow 3: Geracao Paralela (Map State)

```
[Input: Array de 12 posts]
          |
          v
[MAP STATE: max_concurrency=12]
  |           |           |        ...       |
  v           v           v                  v
[Post 1]   [Post 2]   [Post 3]          [Post 12]
  |           |           |                  |
[Bedrock]  [Bedrock]  [Bedrock]          [Bedrock]   <-- 12 chamadas paralelas
  |           |           |                  |
[DDB Put]  [DDB Put]  [DDB Put]          [DDB Put]   <-- Salvar cada resultado
  |           |           |                  |
          [Output: Array de 12 conteudos]
```

**Retry inteligente por post:**
- ThrottlingException: espera 30s, 5 tentativas, backoff x2, jitter FULL
- TaskFailed: espera 5s, 3 tentativas, backoff x2
- Timeout: espera 60s, 2 tentativas, backoff x1.5
- Apos todos os retries: Catch -> tentar modelo alternativo (Haiku como fallback)
- Apos fallback falhar: salvar erro no DynamoDB + notificar via SNS

### 5.4 Workflow 4: Campanhas Agendadas (EventBridge + Step Functions)

```
[EventBridge Scheduler]
  |
  |-- Cron: 9h seg-sex (BRT) --> [SF: Buscar posts do dia -> MAP: Publicar cada -> Notificar]
  |-- Cron: 14h quartas       --> [SF: Publicar conteudo aprofundado]
  |-- Cron: 10h dia 1 do mes  --> [SF: Gerar relatorio mensal -> Email SES]
  |-- One-time: data/hora     --> [SF: Publicar post especifico agendado]
```

**EventBridge Scheduler resolve:**
- Timezone nativa (America/Sao_Paulo)
- Janela flexivel de entrega (15 min)
- Retry automatico (3 tentativas, 1h max age)
- Custo: $0.00 (paga apenas os targets)

### 5.5 Express vs Standard: Quando Usar Cada

| Workflow | Tipo | Motivo |
|----------|------|--------|
| Pipeline completo | **Standard** | Precisa de waitForTaskToken (aprovacao humana) |
| Aprovacao humana | **Standard** | Token duravel, longa duracao |
| Publicacao agendada | **Standard** | Precisa de .sync para APIs externas |
| Geracao de 1 post individual | Express | Rapido (<5min), alto volume |
| Analise de briefing simples | Express | Rapido, stateless |
| Webhook de evento | Express | Alto throughput, idempotente |

**Padrao hibrido recomendado:** Standard orquestra o pipeline geral e delega para Express sub-workflows para geracao rapida de posts individuais.

---

## 6. Estrategia Bedrock

### 6.1 Abordagem Hibrida: Agno + Bedrock

A pesquisa de Bedrock (Doc 2) e clara: **nao migrar a orquestracao de agentes para Bedrock Agents**. O Agno e mais flexivel e Pythonico. Usar Bedrock exclusivamente como infraestrutura de IA.

```
STACK HIBRIDO (Recomendado)
============================

[Telegram Bot]
    |
    v
[Agno Agent Team - Python]    <-- Orquestracao flexivel (manter)
    |
    |-- [AWS Bedrock]
    |     |-- Model Access (SDK direto, sem OpenRouter)
    |     |-- Intelligent Routing (Haiku <-> Sonnet automatico)
    |     |-- Knowledge Bases (brand guidelines via S3 Vectors)
    |     |-- Guardrails API (PII/LGPD, content safety)
    |     |-- Batch Inference (geracao em massa, 50% desconto)
    |
    |-- [Agno Nativo]
    |     |-- Agent definitions (Python)
    |     |-- Team coordination
    |     |-- Workflow logic
    |     |-- Memory (PostgreSQL)
    |     |-- Structured output (Pydantic)
    |
    v
[ClickUp API] + [Step Functions]
```

### 6.2 Intelligent Routing: Economia de 30-60%

O Agency hoje usa um unico modelo (Claude Sonnet via OpenRouter) para todos os agentes. Isso e desperdicio.

**Situacao atual:**
```
briefing_analyzer   --> Claude Sonnet (complexo -- justificado)
content_reviewer    --> Claude Sonnet (medio -- poderia ser Haiku)
schedule_generator  --> Claude Sonnet (simples -- desperdicio)
summary_generator   --> Claude Sonnet (medio -- poderia ser Haiku)
```

**Com Intelligent Routing:**
```
briefing_analyzer   --> Router decide: Sonnet (complexo)     = mesmo custo
content_reviewer    --> Router decide: Haiku (padrao)        = 73% economia
schedule_generator  --> Router decide: Haiku (simples)       = 73% economia
summary_generator   --> Router decide: Haiku (simples)       = 73% economia
```

**Economia estimada: 40-60% no custo de tokens, automaticamente, sem mudar codigo.**

Familias suportadas: Haiku 3.5 <-> Sonnet 3.5, Llama 3.1 8B <-> 70B, Nova Lite <-> Pro.

### 6.3 Estrategia Multi-Modelo: Custo vs Qualidade

```
TRIAGEM/RAPIDO              GERACAO PADRAO              PREMIUM/CRITICO
Nova Micro / Nova Lite      Nova Pro                    Claude Sonnet 4.5
$0.035-0.24/1M tokens       $0.80-3.20/1M tokens        $3.00-15.00/1M tokens

- Classificar briefing      - Posts Instagram            - Estrategia de campanha
- Extrair dados             - Copys de ads               - Conteudo premium
- Gerar hashtags            - Email marketing            - Analise critica
- Validacoes rapidas        - Captions e scripts         - Revisao final
- Resumos                   - Blog posts                 - Copywriting sofisticado

~70% das chamadas           ~25% das chamadas            ~5% das chamadas
Custo: ~$0.50/mes           Custo: ~$5.00/mes            Custo: ~$3.00/mes
```

### 6.4 Knowledge Bases: RAG para Brand Guidelines

Este e o **maior gap do Agency atual** segundo o Doc 2. Hoje, brand guidelines sao texto bruto injetado no prompt. Com Knowledge Bases:

| Cenario Agency | Hoje | Com Bedrock KB |
|-------------|------|----------------|
| Brand guidelines | Texto bruto no prompt | RAG com documentos completos |
| Campanhas anteriores | Sem historico | KB com historico indexado |
| Manuais de estilo | Nao disponivel | Documentos no S3 indexados |
| Tom de voz do cliente | Hardcoded nas instrucoes | Retrieval dinamico por cliente |

**Custo:** S3 Vectors (novo, Dez 2025) = ~$10/mes para PME. 90% mais barato que OpenSearch Serverless (~$100/mes).

**Pipeline automatico:** S3 (upload doc) -> Chunking -> Embedding (Titan) -> S3 Vectors -> Retrieval -> LLM

### 6.5 Guardrails: LGPD e Brand Safety

A pesquisa de Bedrock identifica Guardrails como o **feature com melhor custo-beneficio**. Preco: $0.60/mes para o volume do Agency.

| Protecao | Funcao | Uso no Agency |
|----------|--------|------------|
| **PII Filters** | Detecta/mascara CPF, email, telefone | LGPD compliance obrigatorio |
| **Content Filters** | Bloqueia conteudo violento, odioso, sexual | Brand safety |
| **Denied Topics** | Bloqueia temas fora do escopo | Foco da marca |
| **Word Filters** | Bloqueia termos proibidos | Termos proibidos pela marca |
| **Contextual Grounding** | Detecta alucinacoes | Fidelidade ao briefing |
| **Prompt Attacks** | Detecta injection/jailbreak | Seguranca do bot Telegram |

**Implementacao:** Mesmo usando Agno para orquestracao, Guardrails funciona como API standalone via `ApplyGuardrail`.

### 6.6 Eliminar OpenRouter: Economia de 5.5%

| Item | OpenRouter | Bedrock Direto | Economia |
|------|-----------|----------------|----------|
| Claude Sonnet Input/MTok | $3.00 + 5.5% = $3.165 | $3.00 | $0.165/MTok |
| Claude Sonnet Output/MTok | $15.00 + 5.5% = $15.825 | $15.00 | $0.825/MTok |
| Claude Haiku Input/MTok | $0.80 + 5.5% = $0.844 | $0.80 | $0.044/MTok |
| Fee mensal estimada | ~$1-5/mes | $0 | 100% |
| Batch Inference | Nao disponivel | 50% desconto | Exclusivo Bedrock |

**Migracao:** 1-2 dias de trabalho. Trocar `openrouter` por `boto3.client('bedrock-runtime')` no provider do Agno.

---

## 7. Estimativa de Custos

### 7.1 MVP: 1-5 Clientes (Semanas 1-4)

Arquitetura: Full Serverless (Lambda para tudo, sem ECS, sem ALB).

| Servico | Uso | Custo/Mes |
|---------|-----|-----------|
| Lambda (5 funcoes) | ~2.000 invocacoes, 512MB, 5s media | $0.05 |
| API Gateway | ~2.000 requests (webhook Telegram) | $0.00 |
| Step Functions | ~50 execucoes, ~60 transicoes cada | $0.08 |
| SQS + SNS | ~5.000 mensagens + notificacoes | $0.00 |
| EventBridge | ~500 eventos + schedulers | $0.00 |
| DynamoDB | ~50K operacoes, <1 GB | $0.25 |
| S3 | ~5 GB | $0.12 |
| Bedrock (multi-modelo) | ~50 geracoes, roteamento inteligente | $3.00 |
| Bedrock Guardrails | PII + Content filter | $0.15 |
| Secrets Manager | 3 secrets | $1.20 |
| CloudWatch | Logs basicos + alarmes | $3.00 |
| RDS PostgreSQL | db.t4g.micro (Free Tier) | $0.00 |
| | | |
| **TOTAL MVP (com Free Tier)** | | **~$7.85/mes** |
| **TOTAL MVP (sem Free Tier RDS)** | | **~$20.26/mes** |

**Nota:** Este custo assume Lambda fora da VPC para APIs externas (eliminando NAT Gateway de $33/mes).

### 7.2 Producao: 10 Clientes (Semanas 5-8)

Arquitetura: Hibrida (ECS Bot + Lambda tasks + Step Functions).

| Servico | Uso | Custo/Mes |
|---------|-----|-----------|
| ECS Fargate (Bot) | 0.25 vCPU, 0.5GB, ARM, 24/7 | $7.11 |
| Lambda (5 funcoes) | ~10.000 invocacoes | $0.20 |
| API Gateway | ~10.000 requests | $0.04 |
| Step Functions | ~100 execucoes de pipeline | $0.15 |
| SQS + SNS | ~20.000 mensagens | $0.00 |
| EventBridge | ~5.000 eventos | $0.00 |
| DynamoDB | ~200K operacoes, 2 GB | $0.50 |
| S3 | ~20 GB | $0.50 |
| Bedrock (multi-modelo) | ~240 chamadas (120 posts x 2) | $8.10 |
| Bedrock Guardrails | PII + Content + Brand | $0.60 |
| Bedrock Knowledge Bases | S3 Vectors | $10.00 |
| Secrets Manager | 5 secrets | $2.00 |
| CloudWatch + X-Ray | Logs + metricas + tracing | $8.30 |
| RDS PostgreSQL | db.t4g.small | $24.82 |
| ALB | Load balancer para ECS | $18.00 |
| | | |
| **TOTAL PRODUCAO** | | **~$80.32/mes** |

**Nota:** O maior custo fixo e RDS ($24.82) + ALB ($18). Sem ALB (usando API Gateway direto), cai para ~$62/mes.

### 7.3 Escala: 50 Clientes (Semanas 9-12)

| Servico | Custo/Mes |
|---------|-----------|
| ECS Fargate (Bot, 0.5 vCPU) | $14.22 |
| Lambda (todas as funcoes) | $2.08 |
| Step Functions | $0.03 |
| EventBridge + SQS + SNS | $0.00 |
| DynamoDB | $0.50 |
| S3 (50 GB) | $1.42 |
| Bedrock (200 geracoes, multi-modelo) | $8.10 |
| Bedrock Guardrails | $0.60 |
| Bedrock Knowledge Bases | $10.00 |
| Secrets Manager | $2.00 |
| CloudWatch + X-Ray | $8.30 |
| API Gateway | $0.18 |
| RDS PostgreSQL (db.t4g.medium) | $49.64 |
| ALB | $18.00 |
| ECS Fargate (batch, sob demanda) | $0.65 |
| | |
| **TOTAL ESCALA** | **~$115.72/mes** |

### 7.4 Comparacao com n8n/Make/Zapier

| Volume | AWS Nativo | n8n Cloud | Make (Pro) | Zapier (Pro) |
|--------|-----------|-----------|------------|--------------|
| 5 clientes / 50 posts | **~$20** | $50 | $29-99 | $49-149 |
| 10 clientes / 120 posts | **~$80** | $99 | $99-199 | $149-399 |
| 50 clientes / 600 posts | **~$116** | $199+ | $199-399 | $399-799 |
| 100 clientes / 1200 posts | **~$180** | $499+ | Custom | Custom |
| 500 clientes / 6000 posts | **~$400** | Enterprise | Enterprise | Enterprise |

**Conclusao:** AWS fica progressivamente mais vantajoso conforme o volume aumenta. A diferenca principal esta no custo de infraestrutura de orquestracao (quase zero na AWS vs planos fixos crescentes).

### 7.5 Onde Esta o Dinheiro: Top 5 Custos

| Posicao | Servico | Custo (Prod 10 cli) | % do Total | Como Otimizar |
|---------|---------|--------------------:|----------:|---------------|
| 1 | RDS PostgreSQL | $24.82 | 31% | Reserved Instance (-40%), ou migrar para DynamoDB |
| 2 | ALB | $18.00 | 22% | Usar API Gateway direto (elimina ALB) |
| 3 | Bedrock Knowledge Bases | $10.00 | 12% | S3 Vectors (ja o mais barato) |
| 4 | CloudWatch | $8.30 | 10% | Reduzir retencao de logs |
| 5 | Bedrock (tokens) | $8.10 | 10% | Intelligent Routing (-40%) |

---

## 8. Stack de Observabilidade

### 8.1 CloudWatch: Metricas e Dashboards

```
DASHBOARD: Agency-Marketing-Ops
==============================

+-------------------+-------------------+-------------------+-------------------+
| Briefings         | Erros             | Latencia LLM      | Tokens Usados     |
| Processados (5min)| (5min)            | Media (ms)         | (1h)              |
|       42          |        1          |      3,200         |     45,000        |
+-------------------+-------------------+-------------------+-------------------+

+--------------------------------------+--------------------------------------+
| Briefings por Hora                   | Latencia LLM (p50, p90, p99)        |
|  ___    ___                          |                    __                |
| |   |__|   |__                       |  ___         _____|  |               |
| |              |___                  | |   |_______|                        |
+--------------------------------------+--------------------------------------+

+--------------------------------------+--------------------------------------+
| Custo Bedrock Acumulado (Mes)        | Pipeline Duration (Media)            |
| $3.20 / $50.00 budget                | 45s (geracao) + 12h (aprovacao)      |
+--------------------------------------+--------------------------------------+
```

**Metricas customizadas no namespace `AgenciaAgency/Marketing`:**

| Metrica | Tipo | Alarme |
|---------|------|--------|
| BriefingsReceived | Count | - |
| BriefingsProcessed | Count | - |
| BriefingsError | Count | > 5 em 15 min |
| ContentGenerated | Count | - |
| ContentApproved | Count | - |
| ContentPublished | Count | - |
| BedrockTokensUsed | Count (por modelo) | > 1M tokens/dia |
| PipelineDuration | Seconds | > 5 min |
| ApprovalWaitTime | Seconds | > 48h |
| LLMLatencyMs | Milliseconds | > 30.000ms |
| ClickUpCalls | Count | - |
| ClickUpErrors | Count | > 3 em 15 min |
| DLQMessageCount | Count | > 0 (critico) |

### 8.2 X-Ray: Tracing Distribuido

```
Trace: Briefing br_20260222_001
=================================

[API Gateway]    2ms
    |
[Lambda: WebhookRouter]    15ms
    |
[SQS: briefing-queue]    ~0ms (async)
    |
[Step Functions: ContentPipeline]    total: 47s
    |
    +-- [Lambda: ValidarBriefing]    120ms
    |
    +-- [Bedrock: Nova Micro (classificar)]    1.2s
    |       annotation: model=nova-micro, tokens=350
    |
    +-- [Bedrock: Nova Pro (cronograma)]    4.8s
    |       annotation: model=nova-pro, tokens=2100
    |
    +-- [Lambda: ParsearCronograma]    85ms
    |
    +-- [MAP: 12 posts paralelos]    12.5s
    |       +-- [Bedrock: Nova Pro (post 1)]    3.2s
    |       +-- [Bedrock: Nova Pro (post 2)]    2.8s
    |       +-- ...
    |       +-- [Bedrock: Nova Pro (post 12)]    3.5s
    |
    +-- [DynamoDB: SaveContent]    25ms
    |
    +-- [SNS: NotifyReview]    45ms
    |
    +-- [WAIT: Aprovacao]    12h 34min (zero custo)
    |
    +-- [Lambda: ProcessApproval]    80ms
    |
    +-- [EventBridge: SchedulePublish]    15ms
```

### 8.3 Alarmes Criticos

| Alarme | Condicao | Acao |
|--------|----------|------|
| DLQ > 0 mensagens | Qualquer mensagem na DLQ | SNS -> Telegram Admin |
| Taxa de erro > 5% | 5+ erros em 15 minutos | SNS -> Telegram Admin + Slack |
| Latencia LLM > 30s | Media > 30s por 10 min | SNS -> Telegram Admin |
| Custo Bedrock > $50/dia | Tokens > 1M/dia | SNS -> Email equipe |
| Step Function falhou | Qualquer falha | SNS -> Telegram Admin |
| ClickUp errors > 3 | 3+ erros em 15 min | SNS -> Telegram Admin |

---

## 9. Seguranca

### 9.1 Secrets Manager: API Keys

| Secret | Servico | Rotacao |
|--------|---------|---------|
| `app/api-keys.TELEGRAM_BOT_TOKEN` | Telegram Bot API | Manual (raro) |
| `app/api-keys.CLICKUP_API_TOKEN` | ClickUp API v2 | A cada 90 dias |
| `app/database` | RDS PostgreSQL | Automatica via Secrets Manager |
| `app/api-keys.TELEGRAM_WEBHOOK_SECRET` | Validacao de webhook | Auto-gerado |

**Regras:**
- Nunca hardcode de secrets no codigo
- Lambda busca secrets na inicializacao e cacheia com `@lru_cache`
- ECS Fargate injeta secrets como variaveis de ambiente via task definition
- Custo: $0.40/secret/mes + $0.05/10K chamadas API

### 9.2 IAM: Least Privilege

```
IAM Roles por Servico
======================

Lambda: AI Analyzer
  - secretsmanager:GetSecretValue (app/api-keys)
  - bedrock:InvokeModel (modelos especificos)
  - sqs:ReceiveMessage (briefing-queue)
  - sqs:DeleteMessage (briefing-queue)
  - dynamodb:PutItem (BriefingState)
  - cloudwatch:PutMetricData (AgenciaAgency/*)
  - AWSLambdaBasicExecutionRole
  - AWSXRayDaemonWriteAccess

Lambda: ClickUp Creator
  - secretsmanager:GetSecretValue (app/api-keys)
  - dynamodb:UpdateItem (BriefingState)
  - cloudwatch:PutMetricData (AgenciaAgency/*)
  - AWSLambdaBasicExecutionRole

Lambda: Telegram Notifier
  - secretsmanager:GetSecretValue (app/api-keys)
  - AWSLambdaBasicExecutionRole

Step Functions:
  - lambda:InvokeFunction (funcoes especificas)
  - bedrock:InvokeModel (modelos especificos)
  - dynamodb:PutItem, UpdateItem (tabelas especificas)
  - sns:Publish (topicos especificos)
  - sqs:SendMessage (filas especificas)
  - s3:PutObject, GetObject (bucket especifico)

ECS Fargate (Bot):
  - secretsmanager:GetSecretValue (app/api-keys, app/database)
  - sqs:SendMessage (briefing-queue)
  - events:PutEvents (app-events)
  - cloudwatch:PutMetricData (AgenciaAgency/*)
```

### 9.3 VPC: Layout de Rede

```
VPC: 10.0.0.0/16
|
+-- Public Subnets (2 AZs)
|   +-- 10.0.1.0/24 (us-east-1a) - ALB, NAT Gateway
|   +-- 10.0.2.0/24 (us-east-1b) - ALB
|
+-- Private Subnets (2 AZs)
|   +-- 10.0.10.0/24 (us-east-1a) - ECS Fargate
|   +-- 10.0.11.0/24 (us-east-1b) - ECS Fargate
|
+-- Isolated Subnets (2 AZs)
    +-- 10.0.20.0/24 (us-east-1a) - RDS
    +-- 10.0.21.0/24 (us-east-1b) - RDS

Security Groups:
  sg-alb:     443 (HTTPS) from 0.0.0.0/0
  sg-ecs:     8000 from sg-alb
  sg-lambda:  outbound 443 to 0.0.0.0/0
  sg-rds:     5432 from sg-ecs, sg-lambda
```

**Decisao critica:** Lambdas que chamam APIs externas (OpenRouter/Bedrock, ClickUp, Telegram) ficam **FORA da VPC**. Apenas o Lambda Logger (que acessa RDS) fica dentro da VPC. Isso elimina o NAT Gateway ($33/mes).

VPC Endpoints recomendados para servicos AWS:
- `com.amazonaws.us-east-1.s3` (Gateway -- gratuito)
- `com.amazonaws.us-east-1.secretsmanager` (Interface -- $7.30/mes, se necessario)

### 9.4 LGPD Compliance via Guardrails

| Tipo de Dado | Acao Guardrails | Configuracao |
|-------------|-----------------|--------------|
| CPF | ANONYMIZE (mascara: ***.***.***-**) | PII Filter, tipo: BR_CPF |
| Email pessoal | ANONYMIZE | PII Filter, tipo: EMAIL |
| Telefone | ANONYMIZE | PII Filter, tipo: PHONE |
| Endereco | ANONYMIZE | PII Filter, tipo: ADDRESS |
| Nome completo no output | NONE (registra, nao bloqueia) | PII Filter, tipo: NAME |
| Prompt injection via Telegram | BLOCK | Prompt Attack Detection |

**Custo:** 1.000 briefings/mes x 2 text units x 2 policies = ~$0.60/mes. Negligivel.

---

## 10. Roadmap de Implementacao

### Fase 1: MVP (Semanas 1-4)

**Objetivo:** Sistema funcional end-to-end com custo minimo.
**Custo estimado:** ~$20-35/mes

| Semana | Entrega | Servicos AWS |
|--------|---------|--------------|
| 1 | Setup CDK base + Lambda webhook + API Gateway | Lambda, API Gateway, CDK |
| 1 | Bedrock SDK direto (substituir OpenRouter) + Guardrails PII | Bedrock |
| 2 | SQS para buffer + DLQ + Lambda AI Analyzer | SQS, Lambda |
| 2 | DynamoDB para estado + S3 para midias | DynamoDB, S3 |
| 3 | Step Functions: pipeline basico (briefing -> geracao -> revisao) | Step Functions |
| 3 | Human-in-the-loop: aprovacao via Telegram com waitForTaskToken | Step Functions |
| 4 | SNS para notificacoes + EventBridge Scheduler para agendamento | SNS, EventBridge |
| 4 | CloudWatch: logs, metricas basicas, alarmes criticos | CloudWatch |

**Stack da Fase 1:**
```
Telegram -> API Gateway -> Lambda -> SQS -> Step Functions -> Bedrock -> DynamoDB
                                                          -> S3
                                                          -> SNS -> Telegram
                                                          -> EventBridge -> Lambda (publicar)
```

### Fase 2: Orquestracao (Semanas 5-8)

**Objetivo:** Pipeline robusto com RAG, multi-modelo e observabilidade completa.
**Custo estimado:** ~$60-80/mes

| Semana | Entrega | Servicos AWS |
|--------|---------|--------------|
| 5 | Intelligent Prompt Routing (Haiku <-> Sonnet automatico) | Bedrock Routing |
| 5 | Multi-modelo: Nova Micro para triagem, Nova Pro para geracao | Bedrock |
| 6 | Knowledge Bases com S3 Vectors para brand guidelines | Bedrock KB |
| 6 | MAP State: geracao paralela de 12 posts | Step Functions |
| 7 | ECS Fargate para bot Telegram always-on + RDS PostgreSQL | ECS, RDS |
| 7 | X-Ray tracing distribuido | X-Ray |
| 8 | Dashboard CloudWatch operacional + alarmes completos | CloudWatch |
| 8 | Lambda ClickUpCreator com integracao bidirecional | Lambda |

### Fase 3: Escala (Semanas 9-12)

**Objetivo:** Suportar 50+ clientes com eficiencia.
**Custo estimado:** ~$100-120/mes

| Semana | Entrega | Servicos AWS |
|--------|---------|--------------|
| 9 | Bedrock Batch Inference para geracoes mensais (50% desconto) | Bedrock Batch |
| 9 | Nova Canvas para geracao de imagens | Bedrock |
| 10 | Fan-out/Fan-in: revisao paralela (gramatical + tom + SEO + humana) | Step Functions |
| 10 | Guardrails avancados: Content Safety + Denied Topics + Contextual Grounding | Bedrock Guardrails |
| 11 | ECS Fargate tasks para processamento de video (Nova Reel) | ECS, Bedrock |
| 11 | Analytics: coleta semanal + relatorio mensal automatico | EventBridge, Lambda |
| 12 | Multi-ambiente (dev/staging/prod) via CDK contexts | CDK |
| 12 | CI/CD completo com GitHub Actions | GitHub Actions |

### Fase 4: Inteligencia (Semanas 13-16)

**Objetivo:** Otimizacao e features avancadas.
**Custo estimado:** ~$120-150/mes

| Semana | Entrega | Servicos AWS |
|--------|---------|--------------|
| 13 | Bedrock Evaluations: A/B testing de modelos por tipo de tarefa | Bedrock Evaluations |
| 13 | Inline Agents: agentes customizados por cliente em runtime | Bedrock Inline |
| 14 | Prompt Management: versionamento de prompts no Bedrock | Bedrock PM |
| 14 | Multimodal retrieval em Knowledge Bases (imagem + texto) | Bedrock KB |
| 15 | WhatsApp Business como canal adicional | API Gateway + Lambda |
| 15 | Dashboard web para clientes (Cognito + API Gateway) | Cognito |
| 16 | Otimizacao: Reserved Instances, Savings Plans, Fargate Spot | Billing |
| 16 | Documentacao e runbooks operacionais | -- |

### Riscos e Mitigacoes

| Risco | Probabilidade | Impacto | Mitigacao |
|-------|--------------|---------|-----------|
| Custo Bedrock acima do esperado | Media | Medio | Alarmes CloudWatch + budget limits + Intelligent Routing |
| Cold start Lambda afetando UX | Baixa | Baixo | SnapStart para Python (16.5s -> 1.6s) + Provisioned Concurrency |
| Falha em APIs de redes sociais | Media | Alto | SQS retry + DLQ + fallback para modelo alternativo |
| Curva de aprendizado AWS (ASL/CDK) | Media | Medio | CDK Python abstrai ASL; documentacao interna |
| Vendor lock-in AWS | Baixa | Medio | IaC documenta tudo; Lambda portavel; Agno e open-source |
| NAT Gateway custando mais que esperado | Baixa | Baixo | Lambda fora da VPC + VPC Endpoints |
| Limite 256KB payload Step Functions | Baixa | Baixo | S3 para payloads grandes |

---

## 11. Indice de Fontes

### Documentos de Pesquisa Internos

Estes sao os 4 documentos que alimentaram este consolidado:

| # | Documento | Foco Principal | Localizacao |
|---|-----------|---------------|-------------|
| 1 | AWS Serverless & Event-Driven para Marketing | Lambda, Step Functions, SQS, SNS, EventBridge, S3, DynamoDB, CloudWatch, custos, arquitetura completa | `docs/research/aws-serverless-ai-marketing.md` |
| 2 | AWS Bedrock para Sistemas Multi-Agente | Bedrock Agents, Knowledge Bases, Guardrails, Intelligent Routing, precos, comparativo com Agno | `docs/research/aws-bedrock-ai-agents.md` |
| 3 | AWS Step Functions como Engine de Orquestracao | 6 padroes de workflow (pipeline, human-in-the-loop, paralelo, retry, agendamento, fan-out), CDK Python, custos | `docs/research/aws-step-functions-workflows.md` |
| 4 | Padroes de Arquitetura AWS para Agentes IA | Event-driven pipeline, ECS vs Lambda, VPC, seguranca, observabilidade, CDK, roadmap de evolucao | `docs/research/aws-architecture-patterns-ai.md` |

### Documentacao Oficial AWS (Principais)

- [AWS Prescriptive Guidance - Agentic AI Patterns](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-patterns/introduction.html)
- [AWS Prescriptive Guidance - Serverless AI Architectures](https://docs.aws.amazon.com/prescriptive-guidance/latest/agentic-ai-serverless/introduction.html)
- [AWS Well-Architected - Generative AI Lens](https://docs.aws.amazon.com/wellarchitected/latest/generative-ai-lens/generative-ai-lens.html)
- [Amazon Bedrock Pricing](https://aws.amazon.com/bedrock/pricing/)
- [AWS Step Functions - Bedrock Integration](https://docs.aws.amazon.com/step-functions/latest/dg/connect-bedrock.html)
- [Amazon CloudWatch - GenAI Observability](https://docs.aws.amazon.com/AmazonCloudWatch/latest/monitoring/GenAI-observability.html)
- [AWS Decision Guide - Fargate or Lambda](https://docs.aws.amazon.com/decision-guides/latest/fargate-or-lambda/fargate-or-lambda.html)

### Blog Posts AWS (Mais Relevantes)

- [Orchestrate GenAI Workflows with Bedrock and Step Functions](https://aws.amazon.com/blogs/machine-learning/orchestrate-generative-ai-workflows-with-amazon-bedrock-and-aws-step-functions/)
- [Deliver Personalized Marketing with Amazon Bedrock Agents](https://aws.amazon.com/blogs/machine-learning/deliver-personalized-marketing-with-amazon-bedrock-agents/)
- [Build a Multimodal Social Media Content Generator](https://aws.amazon.com/blogs/machine-learning/build-a-multimodal-social-media-content-generator-using-amazon-bedrock/)
- [Reduce Costs with Intelligent Prompt Routing](https://aws.amazon.com/blogs/aws/reduce-costs-and-latency-with-amazon-bedrock-intelligent-prompt-routing-and-prompt-caching-preview/)
- [Effectively Building AI Agents on AWS Serverless](https://aws.amazon.com/blogs/compute/effectively-building-ai-agents-on-aws-serverless/)

### Comparativos

- [AWS Step Functions vs n8n](https://www.movestax.com/post/aws-step-functions-vs-n8n-workflow-automation-comparison)
- [AWS Bedrock vs OpenAI](https://www.pump.co/blog/aws-bedrock-vs-openai)
- [OpenAI vs Azure vs Bedrock: Enterprise Comparison 2026](https://reintech.io/blog/openai-api-vs-azure-openai-vs-aws-bedrock-enterprise-llm-comparison-2026)

---

> **Documento consolidado em:** 2026-02-22
> **Baseado em:** 4 documentos de pesquisa totalizando ~8.000 linhas
> **Proximo passo:** Iniciar Fase 1 (MVP) -- setup CDK + Lambda webhook + Bedrock SDK
> **Versao:** 1.0
