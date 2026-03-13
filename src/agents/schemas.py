from __future__ import annotations

from pydantic import BaseModel, Field, computed_field


class PostTask(BaseModel):
    title: str = Field(..., description="Titulo do post, ex: 'Post 1 - Promocao Verao'")
    description: str = Field(..., description="Detalhes extraidos do briefing para este post")
    service_type: str = Field(
        ..., description="Tipo de servico: 'design' | 'copy' | 'design+copy'"
    )


class BriefingAnalysis(BaseModel):
    is_valid_briefing: bool = Field(
        ...,
        description=(
            "True se a mensagem contem um briefing de marketing valido com informacoes "
            "suficientes (cliente, rede social, tipo de conteudo). "
            "False se for uma saudacao, mensagem casual, pergunta generica, "
            "conteudo sem relacao com briefing, ou informacoes insuficientes."
        ),
    )
    rejection_message: str = Field(
        default="",
        description=(
            "Quando is_valid_briefing=False, uma resposta amigavel e util em portugues "
            "explicando por que a mensagem nao pode ser processada como briefing "
            "e orientando o usuario sobre o que incluir. "
            "Vazio quando is_valid_briefing=True."
        ),
    )
    client_name: str = Field(
        default="", description="Nome do cliente identificado no briefing"
    )
    social_network: str = Field(
        default="",
        description="Rede social: 'instagram' | 'facebook' | 'tiktok' | 'linkedin' | 'multi'",
    )
    month: str = Field(default="", description="Mes de referencia da campanha")
    year: str = Field(default="", description="Ano de referencia")
    project_summary: str = Field(default="", description="Resumo do projeto/campanha")
    posts: list[PostTask] = Field(
        default_factory=list, description="Lista de posts a serem criados como subtasks"
    )
    urgency: str = Field(default="normal", description="Urgencia: 'normal' | 'urgent'")
    observations: str = Field(
        default="", description="Alertas, duvidas ou observacoes da IA sobre o briefing"
    )

    @computed_field
    @property
    def card_title(self) -> str:
        network = self.social_network.capitalize()
        client = self.client_name.title()
        month = self.month.capitalize()
        return f"{network} - {client} - {month} {self.year}"


class ScheduledPost(BaseModel):
    date: str = Field(..., description="Data do post no formato DD/MM")
    post_type: str = Field(
        ..., description="Tipo: 'POST' | 'CARROSSEL' | 'REELS' | 'STORY'"
    )
    title: str = Field(..., description="Titulo descritivo do post")
    platform: str = Field(
        ..., description="Plataforma: 'instagram' | 'linkedin' | 'tiktok' | 'whatsapp'"
    )
    notes: str = Field(default="", description="Observacoes opcionais da AI")

    @computed_field
    @property
    def task_name(self) -> str:
        return f"{self.date} - {self.post_type} {self.title}"


class DailySummary(BaseModel):
    resumo: str = Field(..., description="Texto em linguagem natural gerado pela IA")
    total_ativas: int = Field(..., description="Total de tasks ativas")
    total_concluidas: int = Field(..., description="Total de tasks concluidas")
    total_atrasadas: int = Field(..., description="Total de tasks atrasadas")
    gargalos: list[str] = Field(default_factory=list, description="Descricoes de tasks paradas")
    deadlines_proximos: list[str] = Field(
        default_factory=list, description="Tasks com prazo nas proximas 48h"
    )


class ContentReview(BaseModel):
    """AI review of a ClickUp task's content."""
    checklist: list[str] = Field(..., description="Items checked (e.g., 'tom de voz adequado')")
    issues: list[str] = Field(..., description="Problems found")
    suggestions: list[str] = Field(..., description="Improvement suggestions")
    overall_score: int = Field(..., description="Quality score 1-10")
    summary: str = Field(..., description="2-3 sentence summary of the review")
    approved: bool = Field(..., description="AI recommendation: approve or not")


class BrandViolation(BaseModel):
    """A single brand guideline violation detected by the Brand Compliance agent."""
    rule: str = Field(..., description="The brand rule that was violated")
    severity: str = Field(
        ..., description="Severity: 'critical' | 'warning' | 'info'"
    )
    detail: str = Field(..., description="Explanation of how the rule was violated")


class BrandComplianceResult(BaseModel):
    """Result of brand compliance check."""
    violations: list[BrandViolation] = Field(
        default_factory=list, description="List of brand rule violations"
    )
    compliance_score: int = Field(
        ..., description="Compliance score 1-10 (10 = fully compliant)"
    )
    passed: bool = Field(
        ..., description="True if content passes brand compliance"
    )
    summary: str = Field(
        ..., description="1-2 sentence summary of compliance check"
    )


class CombinedReviewResult(BaseModel):
    """Combined result from ReviewTeam (quality + brand compliance)."""
    quality: ContentReview = Field(..., description="Quality review from content reviewer")
    compliance: BrandComplianceResult = Field(
        ..., description="Brand compliance check result"
    )

    @computed_field
    @property
    def overall_approved(self) -> bool:
        return self.quality.approved and self.compliance.passed

    @computed_field
    @property
    def combined_summary(self) -> str:
        parts = [f"Qualidade: {self.quality.summary}"]
        if not self.compliance.passed:
            parts.append(f"Marca: {self.compliance.summary}")
        return " | ".join(parts)


class PostSchedule(BaseModel):
    posts: list[ScheduledPost] = Field(..., min_length=1, description="Lista de posts agendados")
    month: str = Field(..., description="Mes de referencia")
    year: str = Field(..., description="Ano de referencia")
    platform: str = Field(..., description="Plataforma principal")
    observations: str = Field(..., description="Observacoes gerais da AI sobre o cronograma")

    @computed_field
    @property
    def formatted_text(self) -> str:
        lines = []
        for i, post in enumerate(self.posts, 1):
            lines.append(f"{i}. {post.task_name}")
        if self.observations:
            lines.append(f"\nObs: {self.observations}")
        return "\n".join(lines)


class ApprovalMetrics(BaseModel):
    """Metrics for client approval workflow in a given period."""

    first_approval_rate: float = Field(
        default=0.0, description="Percentage of assets approved without changes (0.0-1.0)"
    )
    avg_review_days: float = Field(
        default=0.0, description="Average days from send to client decision"
    )
    total_alterations: int = Field(
        default=0, description="Total change requests in the period"
    )
    total_assets_reviewed: int = Field(
        default=0, description="Total assets sent for client review"
    )


class MonthlyReport(BaseModel):
    """AI-generated monthly client report for F5.3."""

    period: str = Field(..., description="Report period, e.g. 'Fevereiro 2026'")
    client_name: str = Field(..., description="Client name")
    resumo_executivo: str = Field(
        ..., description="AI narrative summary in PT-BR"
    )
    total_tasks_created: int = Field(
        default=0, description="Total tasks created in the period"
    )
    total_tasks_completed: int = Field(
        default=0, description="Total tasks completed in the period"
    )
    on_time_rate: float = Field(
        default=0.0, description="Percentage of tasks delivered on time (0.0-1.0)"
    )
    tasks_by_status: dict[str, int] = Field(
        default_factory=dict, description="Task count by status, e.g. {'aprovado': 15, 'em criacao': 3}"
    )
    approval_metrics: ApprovalMetrics = Field(
        default_factory=ApprovalMetrics, description="Client approval workflow metrics"
    )
    time_per_status: dict[str, float] = Field(
        default_factory=dict, description="Average hours spent per status, e.g. {'planejamento': 24.5}"
    )
    bottlenecks: list[str] = Field(
        default_factory=list, description="AI-identified bottlenecks and issues"
    )
    recommendations: list[str] = Field(
        default_factory=list, description="AI suggestions for the next month"
    )
    highlights: list[str] = Field(
        default_factory=list, description="Top achievements of the period"
    )
    instagram_metrics: InstagramMonthlyMetrics | None = Field(
        default=None, description="Instagram metrics for the period (if available)"
    )


class ContentTheme(BaseModel):
    """A strategic content theme suggested by the Creative Director."""

    name: str = Field(..., description="Nome do tema, ex: 'Serie Educativa'")
    description: str = Field(..., description="Por que este tema funciona para o cliente")
    pillar: str = Field(
        ...,
        description=(
            "Pilar de conteudo: 'educativo' | 'promocional'"
            " | 'inspiracional' | 'entretenimento'"
        ),
    )
    subtopics: list[str] = Field(
        ..., description="3-5 ideias especificas de posts dentro do tema"
    )
    recommended_formats: list[str] = Field(
        ..., description="Formatos recomendados: 'carrossel', 'reels', 'post', 'story'"
    )
    platforms: list[str] = Field(
        ..., description="Plataformas: 'instagram', 'linkedin', 'tiktok'"
    )
    rationale: str = Field(
        ..., description="Justificativa baseada em dados ou historico"
    )


class SeasonalOpportunity(BaseModel):
    """A seasonal/commercial date opportunity for content."""

    date: str = Field(..., description="Data no formato DD/MM ou 'Semana de DD-DD/MM'")
    event: str = Field(..., description="Nome do evento, ex: 'Dia Internacional da Mulher'")
    suggestion: str = Field(..., description="Como o cliente pode aproveitar esta data")
    format: str = Field(..., description="Formato recomendado de conteudo")
    priority: str = Field(..., description="Prioridade: 'alta' | 'media' | 'baixa'")


class CreativeDirection(BaseModel):
    """AI-generated creative direction for a client's upcoming month. Output of F5.1."""

    client_name: str = Field(..., description="Nome do cliente")
    period: str = Field(..., description="Periodo, ex: 'Marco 2026'")
    resumo_estrategico: str = Field(
        ..., description="Narrativa estrategica da IA em PT-BR"
    )
    themes: list[ContentTheme] = Field(
        ..., min_length=1, description="3-5 temas estrategicos para o mes"
    )
    seasonal_opportunities: list[SeasonalOpportunity] = Field(
        default_factory=list, description="Datas sazonais/comerciais relevantes"
    )
    format_mix: dict[str, int] = Field(
        ..., description="Distribuicao recomendada, ex: {'carrossel': 4, 'reels': 3}"
    )
    tone_guidance: str = Field(
        ..., description="Orientacoes de tom para o mes"
    )
    avoid: list[str] = Field(
        default_factory=list, description="O que evitar (baseado em guidelines e tendencias)"
    )

    @computed_field
    @property
    def formatted_text(self) -> str:
        """Format creative direction for Telegram display."""
        lines = [
            f"Direcao Criativa - {self.client_name} - {self.period}",
            "",
            f"Estrategia: {self.resumo_estrategico}",
            "",
            "Temas:",
        ]
        for i, theme in enumerate(self.themes, 1):
            formats = ", ".join(theme.recommended_formats)
            lines.append(f"  {i}. {theme.name} ({theme.pillar})")
            lines.append(f"     Formatos: {formats}")
            lines.append(f"     Razao: {theme.rationale}")
            for sub in theme.subtopics:
                lines.append(f"     - {sub}")

        if self.seasonal_opportunities:
            lines.append("")
            lines.append("Oportunidades Sazonais:")
            for opp in self.seasonal_opportunities:
                lines.append(f"  {opp.date} - {opp.event} [{opp.priority}]")
                lines.append(f"     {opp.suggestion}")

        mix_str = ", ".join(f"{k}: {v}" for k, v in self.format_mix.items())
        lines.append("")
        lines.append(f"Mix de Formatos: {mix_str}")

        if self.avoid:
            lines.append("")
            lines.append("Evitar: " + "; ".join(self.avoid))

        return "\n".join(lines)


class PostPerformance(BaseModel):
    """Performance data for a single Instagram post."""

    caption_preview: str = Field(..., description="Primeiros 50 caracteres da legenda")
    media_type: str = Field(..., description="IMAGE, VIDEO, CAROUSEL_ALBUM")
    published_at: str = Field(..., description="Data de publicacao DD/MM/YYYY")
    reach: int = Field(..., description="Contas unicas alcancadas")
    engagement_rate: float = Field(..., description="total_interactions / reach * 100")
    top_metric: str = Field(..., description="Metrica de destaque: saves, shares, likes, etc.")


class FormatStats(BaseModel):
    """Aggregated stats for a content format type."""

    count: int = Field(..., description="Numero de posts deste formato")
    avg_reach: float = Field(..., description="Alcance medio")
    avg_engagement_rate: float = Field(..., description="Taxa de engajamento media")


class AccountGrowth(BaseModel):
    """Instagram account growth metrics for a period."""

    followers_start: int = Field(..., description="Seguidores no inicio do periodo")
    followers_end: int = Field(..., description="Seguidores no final do periodo")
    followers_change: int = Field(..., description="Variacao de seguidores")
    avg_daily_reach: float = Field(..., description="Alcance diario medio")


class PerformanceInsight(BaseModel):
    """AI-generated Instagram performance insight for F5.2."""

    client_name: str = Field(..., description="Nome do cliente")
    period: str = Field(..., description="Periodo: 'Ultimos 30 dias' ou 'Fevereiro 2026'")
    resumo: str = Field(..., description="Narrativa da IA em PT-BR")
    top_posts: list[PostPerformance] = Field(
        ..., description="Top 3 posts por engajamento"
    )
    bottom_posts: list[PostPerformance] = Field(
        default_factory=list, description="Bottom 3 posts"
    )
    format_analysis: dict[str, FormatStats] = Field(
        ..., description="Metricas medias por formato (IMAGE, VIDEO, CAROUSEL_ALBUM)"
    )
    trends: list[str] = Field(..., description="Padroes identificados pela IA")
    recommendations: list[str] = Field(
        ..., description="Sugestoes acionaveis"
    )
    account_growth: AccountGrowth = Field(
        ..., description="Crescimento da conta no periodo"
    )

    @computed_field
    @property
    def formatted_text(self) -> str:
        """Format performance insight for Telegram display."""
        lines = [
            f"Performance {self.client_name} - {self.period}",
            "",
            f"Resumo: {self.resumo}",
            "",
        ]
        if self.top_posts:
            lines.append("Top Posts:")
            for i, p in enumerate(self.top_posts, 1):
                lines.append(
                    f"  {i}. \"{p.caption_preview}\" ({p.media_type})"
                    f" - {p.reach:,} alcance, {p.engagement_rate:.1f}% eng"
                )
        lines.append("")
        lines.append("Por Formato:")
        for fmt, stats in self.format_analysis.items():
            lines.append(
                f"  {fmt}: {stats.count} posts,"
                f" media {stats.avg_reach:,.0f} alcance,"
                f" {stats.avg_engagement_rate:.1f}% eng"
            )
        ag = self.account_growth
        sign = "+" if ag.followers_change >= 0 else ""
        lines.append("")
        lines.append(f"Crescimento: {sign}{ag.followers_change} seguidores")
        if self.recommendations:
            lines.append("")
            lines.append("Recomendacoes:")
            for r in self.recommendations:
                lines.append(f"  - {r}")
        return "\n".join(lines)


class InstagramMonthlyMetrics(BaseModel):
    """Optional Instagram metrics section for MonthlyReport enrichment."""

    total_posts_tracked: int = Field(..., description="Posts rastreados no mes")
    total_reach: int = Field(..., description="Alcance total")
    avg_engagement_rate: float = Field(..., description="Taxa media de engajamento")
    best_format: str = Field(..., description="Formato com melhor performance")
    follower_change: int = Field(..., description="Variacao de seguidores no mes")
    top_post_caption: str = Field(..., description="Legenda do melhor post")
    top_post_reach: int = Field(..., description="Alcance do melhor post")
