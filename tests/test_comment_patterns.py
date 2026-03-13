"""Tests for comment intent detection (A1)."""
from src.bot.comment_patterns import CommentIntent, detect_intent

# === Approval patterns ===

class TestApprovalDetection:
    def test_detects_aprovado(self):
        result = detect_intent("aprovado", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"
        assert result.target_status == "aprovado"

    def test_detects_aprovado_case_insensitive(self):
        result = detect_intent("Aprovado!", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_detects_por_mim_ok(self):
        result = detect_intent("por mim ok", "content_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_detects_por_mim_okk(self):
        result = detect_intent("por mim okk", "content_reviewer", "revisao")
        assert result is not None

    def test_detects_tudo_aprovado(self):
        result = detect_intent("tudo aprovado, pode seguir", "strategy_reviewer", "revisao")
        assert result is not None

    def test_detects_amassou(self):
        result = detect_intent("amassou!", "content_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_detects_aprovo(self):
        result = detect_intent("aprovo esse material", "strategy_reviewer", "revisao")
        assert result is not None

    def test_rejects_wrong_role_for_approval(self):
        result = detect_intent("aprovado", "designer", "revisao")
        assert result is None

    def test_rejects_wrong_status_for_approval(self):
        result = detect_intent("aprovado", "strategy_reviewer", "desenvolvimento")
        assert result is None

    def test_aprovado_in_longer_text(self):
        text = "Olhei o material e esta tudo aprovado, muito bom trabalho"
        result = detect_intent(text, "strategy_reviewer", "revisao")
        assert result is not None


# === Delivery patterns ===

class TestDeliveryDetection:
    def test_detects_segue_para_aprovacao(self):
        result = detect_intent("segue para aprovacao", "designer", "em criacao")
        assert result is not None
        assert result.intent_type == "delivery"
        assert result.target_status == "revisao"

    def test_detects_segue_para_aprovacao_cedilha(self):
        result = detect_intent("segue para aprovação", "designer", "em criacao")
        assert result is not None

    def test_detects_finalizado(self):
        result = detect_intent("Finalizado!", "designer", "alteracao")
        assert result is not None
        assert result.intent_type == "delivery"

    def test_detects_captado(self):
        result = detect_intent("captado", "designer", "em criacao")
        assert result is not None

    def test_detects_entrega_finalizada(self):
        result = detect_intent("entrega finalizada", "designer", "em criacao")
        assert result is not None

    def test_rejects_reviewer_delivering(self):
        result = detect_intent("finalizado", "strategy_reviewer", "em criacao")
        assert result is None

    def test_rejects_wrong_status(self):
        result = detect_intent("finalizado", "designer", "revisao")
        assert result is None


# === Alteration done patterns ===

class TestAlterationDoneDetection:
    def test_detects_alterado(self):
        result = detect_intent("alterado", "designer", "alteracao")
        assert result is not None
        assert result.intent_type == "alteration_done"
        assert result.target_status == "revisao"

    def test_detects_alteracao_feita(self):
        result = detect_intent("alteracao feita", "designer", "alteracao")
        assert result is not None

    def test_detects_alteracao_feita_cedilha(self):
        result = detect_intent("alteração feita", "designer", "alteracao")
        assert result is not None

    def test_detects_atualizei(self):
        result = detect_intent("atualizei o banner", "designer", "alteracao")
        assert result is not None

    def test_detects_ajustado(self):
        result = detect_intent("ajustado conforme pedido", "designer", "alteracao")
        assert result is not None

    def test_detects_corrigido(self):
        result = detect_intent("corrigido", "designer", "alteracao")
        assert result is not None

    def test_rejects_reviewer_altering(self):
        result = detect_intent("alterado", "strategy_reviewer", "alteracao")
        assert result is None


# === Edge cases ===

class TestEdgeCases:
    def test_empty_text_returns_none(self):
        assert detect_intent("", "designer", "alteracao") is None

    def test_whitespace_only_returns_none(self):
        assert detect_intent("   ", "designer", "alteracao") is None

    def test_no_matching_pattern(self):
        assert detect_intent("boa tarde, como vai?", "designer", "alteracao") is None

    def test_none_role_still_matches_pattern(self):
        """With role=None, role check is skipped (lenient)."""
        result = detect_intent("aprovado", None, "revisao")
        assert result is not None

    def test_none_status_still_matches_pattern(self):
        """With status=None, status check is skipped (lenient)."""
        result = detect_intent("aprovado", "strategy_reviewer", None)
        assert result is not None

    def test_false_positive_aprovado_in_word(self):
        """'aprovado' as a substring of another word — regex uses \\b boundary."""
        result = detect_intent("desaprovado", "strategy_reviewer", "revisao")
        assert result is None

    def test_priority_approval_over_delivery(self):
        """If both approval and delivery match, approval wins (checked first)."""
        text = "aprovado, segue para aprovacao"
        result = detect_intent(text, "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_intent_dataclass_is_frozen(self):
        intent = CommentIntent(
            intent_type="approval",
            target_status="aprovado",
            matched_pattern="aprovado",
            confidence=1.0,
        )
        try:
            intent.intent_type = "delivery"  # type: ignore
            assert False, "Should have raised"
        except AttributeError:
            pass


# === Internal approved patterns ===

class TestInternalApprovedDetection:
    def test_detects_aprovado_internamente(self):
        result = detect_intent("aprovado internamente", "strategy_reviewer", "aprovado")
        assert result is not None
        assert result.intent_type == "internal_approved"
        assert result.target_status == "revisao_cliente"

    def test_detects_segue_para_cliente(self):
        result = detect_intent("segue para o cliente", "account", "aprovado")
        assert result is not None
        assert result.intent_type == "internal_approved"
        assert result.target_status == "revisao_cliente"

    def test_detects_segue_para_cliente_without_article(self):
        result = detect_intent("segue para cliente", "account", "aprovado")
        assert result is not None
        assert result.intent_type == "internal_approved"

    def test_content_reviewer_can_approve_internally(self):
        result = detect_intent("aprovado internamente", "content_reviewer", "aprovado")
        assert result is not None
        assert result.intent_type == "internal_approved"

    def test_wrong_status_falls_through_to_approval(self):
        """From 'revisao', 'aprovado internamente' matches generic approval instead."""
        result = detect_intent("aprovado internamente", "strategy_reviewer", "revisao")
        assert result is not None
        assert result.intent_type == "approval"

    def test_rejects_designer_role(self):
        """Designers cannot trigger internal_approved."""
        result = detect_intent("segue para cliente", "designer", "aprovado")
        assert result is None
