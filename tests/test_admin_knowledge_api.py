from src.api.admin.knowledge import (
    KnowledgeDocumentCreate,
    KnowledgeDocumentResponse,
    KnowledgeDocumentUpdate,
)


def test_knowledge_create_schema():
    doc = KnowledgeDocumentCreate(
        title="Manual IV",
        category="marca",
        content="# Manual\nConteudo...",
        agent_access=["content_reviewer"],
    )
    assert doc.title == "Manual IV"
    assert len(doc.agent_access) == 1


def test_knowledge_response_schema():
    doc = KnowledgeDocumentResponse(
        id="abc",
        title="Test",
        category="geral",
        content="text",
        file_key=None,
        file_name=None,
        file_type=None,
        file_size=None,
        agent_access=[],
        is_active=True,
    )
    assert doc.id == "abc"


def test_knowledge_update_schema():
    update = KnowledgeDocumentUpdate(title="Novo Titulo")
    assert update.title == "Novo Titulo"
    assert update.category is None


def test_knowledge_update_agent_access():
    update = KnowledgeDocumentUpdate(agent_access=["briefing_analyzer", "content_reviewer"])
    assert len(update.agent_access) == 2
