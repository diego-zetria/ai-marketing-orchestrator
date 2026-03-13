from src.db.admin_models import KnowledgeDocument


def test_knowledge_document_fields():
    doc = KnowledgeDocument(
        title="Manual de Identidade Visual",
        category="marca",
        content="# Manual\nConteudo aqui...",
        file_key="knowledge/client_delta/manual-iv.pdf",
        file_name="manual-iv.pdf",
        file_type="application/pdf",
        file_size=1024000,
        agent_access=["content_reviewer", "briefing_analyzer"],
        is_active=True,
    )
    assert doc.title == "Manual de Identidade Visual"
    assert doc.category == "marca"
    assert doc.file_type == "application/pdf"
    assert len(doc.agent_access) == 2


def test_knowledge_document_minimal():
    doc = KnowledgeDocument(
        title="Test",
        category="geral",
        content="test content",
        agent_access=[],
        is_active=True,
    )
    assert doc.file_key is None
    assert doc.file_name is None
    assert doc.file_size is None
