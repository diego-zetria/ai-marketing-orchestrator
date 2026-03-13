"""Tests for the approval portal Pydantic request/response schemas.

Verifies:
1. All request schemas validate correctly
2. Request validation rejects invalid input
3. All response schemas can be created from attributes
4. from_attributes works (simulating ORM model serialization)
5. JSON serialization works for all schemas
"""

import json
import uuid
from datetime import datetime, timezone
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from src.approval.schemas import (
    AddCommentRequest,
    ApproveRequest,
    AssetDetailResponse,
    AssetResponse,
    AuthValidateResponse,
    ClientResponse,
    CommentResponse,
    DecisionResponse,
    DecisionResultResponse,
    RequestChangesRequest,
    VersionResponse,
)

# ---------------------------------------------------------------------------
# Helpers — fake ORM objects using SimpleNamespace
# ---------------------------------------------------------------------------

def _make_client(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        name="client_alpha",
        slug="client_alpha",
        logo_url="https://example.com/client_alpha.png",
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_version(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        version_number=1,
        file_type="image",
        file_format="png",
        media_url="https://cdn.example.com/image.png",
        thumbnail_url="https://cdn.example.com/thumb.png",
        file_size_bytes=2048576,
        width=1920,
        height=1080,
        duration_seconds=None,
        uploaded_by="Pedro Eger",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_comment(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        author_type="client",
        author_name="Maria Souza",
        content="Precisa ajustar as cores do logo",
        created_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_decision(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        decision="approved",
        comment=None,
        decided_by="Maria Souza",
        decided_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


def _make_asset(**overrides):
    defaults = dict(
        id=uuid.uuid4(),
        title="Instagram Post - ClientAlpha - Fevereiro 2026",
        description="Post promocional para campanha de verao",
        status="pending_review",
        current_version=1,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


# ===========================================================================
# Request Schemas — Valid Input
# ===========================================================================


class TestApproveRequest:
    """ApproveRequest: optional comment."""

    def test_approve_without_comment(self):
        req = ApproveRequest()
        assert req.comment is None

    def test_approve_with_comment(self):
        req = ApproveRequest(comment="Looks great!")
        assert req.comment == "Looks great!"

    def test_approve_with_empty_string_comment(self):
        req = ApproveRequest(comment="")
        assert req.comment == ""

    def test_approve_json_round_trip(self):
        req = ApproveRequest(comment="Aprovado!")
        data = json.loads(req.model_dump_json())
        assert data["comment"] == "Aprovado!"

    def test_approve_from_dict(self):
        req = ApproveRequest.model_validate({"comment": "Ok"})
        assert req.comment == "Ok"

    def test_approve_from_dict_empty(self):
        req = ApproveRequest.model_validate({})
        assert req.comment is None


class TestRequestChangesRequest:
    """RequestChangesRequest: required comment with min_length=10, max_length=2000."""

    def test_valid_comment(self):
        req = RequestChangesRequest(comment="Preciso mudar as cores do logo principal")
        assert req.comment == "Preciso mudar as cores do logo principal"

    def test_comment_exactly_10_chars(self):
        req = RequestChangesRequest(comment="1234567890")
        assert len(req.comment) == 10

    def test_comment_exactly_2000_chars(self):
        comment = "a" * 2000
        req = RequestChangesRequest(comment=comment)
        assert len(req.comment) == 2000

    def test_rejects_missing_comment(self):
        with pytest.raises(ValidationError) as exc_info:
            RequestChangesRequest()
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" for e in errors)

    def test_rejects_comment_too_short(self):
        with pytest.raises(ValidationError) as exc_info:
            RequestChangesRequest(comment="curto")
        errors = exc_info.value.errors()
        assert any("string_too_short" in e["type"] for e in errors)

    def test_rejects_comment_9_chars(self):
        with pytest.raises(ValidationError):
            RequestChangesRequest(comment="123456789")

    def test_rejects_comment_too_long(self):
        with pytest.raises(ValidationError) as exc_info:
            RequestChangesRequest(comment="x" * 2001)
        errors = exc_info.value.errors()
        assert any("string_too_long" in e["type"] for e in errors)

    def test_json_round_trip(self):
        req = RequestChangesRequest(comment="Alterar texto do titulo principal")
        data = json.loads(req.model_dump_json())
        restored = RequestChangesRequest.model_validate(data)
        assert restored.comment == req.comment


class TestAddCommentRequest:
    """AddCommentRequest: required content with min_length=1, max_length=5000."""

    def test_valid_content(self):
        req = AddCommentRequest(content="Gostei da proposta")
        assert req.content == "Gostei da proposta"

    def test_content_exactly_1_char(self):
        req = AddCommentRequest(content="A")
        assert req.content == "A"

    def test_content_exactly_5000_chars(self):
        content = "b" * 5000
        req = AddCommentRequest(content=content)
        assert len(req.content) == 5000

    def test_rejects_missing_content(self):
        with pytest.raises(ValidationError) as exc_info:
            AddCommentRequest()
        errors = exc_info.value.errors()
        assert any(e["type"] == "missing" for e in errors)

    def test_rejects_empty_content(self):
        with pytest.raises(ValidationError) as exc_info:
            AddCommentRequest(content="")
        errors = exc_info.value.errors()
        assert any("string_too_short" in e["type"] for e in errors)

    def test_rejects_content_too_long(self):
        with pytest.raises(ValidationError) as exc_info:
            AddCommentRequest(content="c" * 5001)
        errors = exc_info.value.errors()
        assert any("string_too_long" in e["type"] for e in errors)

    def test_json_round_trip(self):
        req = AddCommentRequest(content="Comentario do cliente")
        data = json.loads(req.model_dump_json())
        restored = AddCommentRequest.model_validate(data)
        assert restored.content == req.content


# ===========================================================================
# Response Schemas — Direct Construction
# ===========================================================================


class TestClientResponse:
    def test_creation(self):
        cid = uuid.uuid4()
        resp = ClientResponse(
            id=cid, name="client_alpha", slug="client_alpha", logo_url="https://example.com/logo.png"
        )
        assert resp.id == cid
        assert resp.name == "client_alpha"
        assert resp.slug == "client_alpha"
        assert resp.logo_url == "https://example.com/logo.png"

    def test_logo_url_none(self):
        resp = ClientResponse(id=uuid.uuid4(), name="client_delta", slug="client_delta", logo_url=None)
        assert resp.logo_url is None

    def test_from_attributes(self):
        obj = _make_client()
        resp = ClientResponse.model_validate(obj, from_attributes=True)
        assert resp.id == obj.id
        assert resp.name == obj.name
        assert resp.slug == obj.slug
        assert resp.logo_url == obj.logo_url

    def test_json_serialization(self):
        resp = ClientResponse(
            id=uuid.uuid4(), name="test", slug="test", logo_url=None
        )
        data = json.loads(resp.model_dump_json())
        assert "id" in data
        assert data["name"] == "test"
        assert data["logo_url"] is None

    def test_from_attributes_config(self):
        assert ClientResponse.model_config.get("from_attributes") is True


class TestVersionResponse:
    def test_creation_full(self):
        vid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        resp = VersionResponse(
            id=vid,
            version_number=2,
            file_type="video",
            file_format="mp4",
            media_url="https://cdn.example.com/video.mp4",
            thumbnail_url="https://cdn.example.com/thumb.jpg",
            file_size_bytes=10485760,
            width=1920,
            height=1080,
            duration_seconds=30.5,
            uploaded_by="Paul",
            created_at=now,
        )
        assert resp.version_number == 2
        assert resp.file_type == "video"
        assert resp.duration_seconds == 30.5
        assert resp.created_at == now

    def test_optional_fields_none(self):
        resp = VersionResponse(
            id=uuid.uuid4(),
            version_number=1,
            file_type="image",
            file_format="png",
            file_size_bytes=None,
            width=None,
            height=None,
            duration_seconds=None,
            uploaded_by=None,
            created_at=datetime.now(timezone.utc),
        )
        assert resp.media_url is None
        assert resp.thumbnail_url is None
        assert resp.file_size_bytes is None
        assert resp.width is None
        assert resp.height is None
        assert resp.duration_seconds is None
        assert resp.uploaded_by is None

    def test_from_attributes(self):
        obj = _make_version()
        resp = VersionResponse.model_validate(obj, from_attributes=True)
        assert resp.id == obj.id
        assert resp.version_number == obj.version_number
        assert resp.file_type == obj.file_type
        assert resp.file_format == obj.file_format
        assert resp.media_url == obj.media_url
        assert resp.uploaded_by == obj.uploaded_by

    def test_json_serialization(self):
        resp = VersionResponse(
            id=uuid.uuid4(),
            version_number=1,
            file_type="image",
            file_format="jpg",
            file_size_bytes=1024,
            width=800,
            height=600,
            duration_seconds=None,
            uploaded_by="Designer A",
            created_at=datetime.now(timezone.utc),
        )
        data = json.loads(resp.model_dump_json())
        assert data["version_number"] == 1
        assert data["file_format"] == "jpg"
        assert data["width"] == 800

    def test_from_attributes_config(self):
        assert VersionResponse.model_config.get("from_attributes") is True


class TestCommentResponse:
    def test_creation(self):
        cid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        resp = CommentResponse(
            id=cid,
            author_type="client",
            author_name="Maria Souza",
            content="Ajustar as cores",
            created_at=now,
        )
        assert resp.id == cid
        assert resp.author_type == "client"
        assert resp.author_name == "Maria Souza"
        assert resp.content == "Ajustar as cores"
        assert resp.created_at == now

    def test_from_attributes(self):
        obj = _make_comment(author_type="team", author_name="Pedro")
        resp = CommentResponse.model_validate(obj, from_attributes=True)
        assert resp.author_type == "team"
        assert resp.author_name == "Pedro"

    def test_json_serialization(self):
        resp = CommentResponse(
            id=uuid.uuid4(),
            author_type="client",
            author_name="Test",
            content="Test content",
            created_at=datetime.now(timezone.utc),
        )
        data = json.loads(resp.model_dump_json())
        assert data["author_type"] == "client"
        assert "created_at" in data

    def test_from_attributes_config(self):
        assert CommentResponse.model_config.get("from_attributes") is True


class TestDecisionResponse:
    def test_creation_approved(self):
        did = uuid.uuid4()
        now = datetime.now(timezone.utc)
        resp = DecisionResponse(
            id=did,
            decision="approved",
            comment=None,
            decided_by="Maria Souza",
            decided_at=now,
        )
        assert resp.decision == "approved"
        assert resp.comment is None
        assert resp.decided_by == "Maria Souza"

    def test_creation_changes_requested(self):
        resp = DecisionResponse(
            id=uuid.uuid4(),
            decision="changes_requested",
            comment="Alterar texto principal",
            decided_by="Cliente ClientAlpha",
            decided_at=datetime.now(timezone.utc),
        )
        assert resp.decision == "changes_requested"
        assert resp.comment == "Alterar texto principal"

    def test_from_attributes(self):
        obj = _make_decision(decision="changes_requested", comment="Fix colors")
        resp = DecisionResponse.model_validate(obj, from_attributes=True)
        assert resp.decision == "changes_requested"
        assert resp.comment == "Fix colors"

    def test_json_serialization(self):
        resp = DecisionResponse(
            id=uuid.uuid4(),
            decision="approved",
            comment=None,
            decided_by="Test",
            decided_at=datetime.now(timezone.utc),
        )
        data = json.loads(resp.model_dump_json())
        assert data["decision"] == "approved"
        assert data["comment"] is None

    def test_from_attributes_config(self):
        assert DecisionResponse.model_config.get("from_attributes") is True


class TestAssetResponse:
    def test_creation(self):
        aid = uuid.uuid4()
        now = datetime.now(timezone.utc)
        resp = AssetResponse(
            id=aid,
            title="Instagram Post - ClientAlpha",
            description="Campanha de verao",
            status="pending_review",
            current_version=1,
            created_at=now,
            updated_at=now,
        )
        assert resp.id == aid
        assert resp.title == "Instagram Post - ClientAlpha"
        assert resp.status == "pending_review"
        assert resp.current_version == 1

    def test_description_none(self):
        now = datetime.now(timezone.utc)
        resp = AssetResponse(
            id=uuid.uuid4(),
            title="Test",
            description=None,
            status="approved",
            current_version=2,
            created_at=now,
            updated_at=now,
        )
        assert resp.description is None

    def test_from_attributes(self):
        obj = _make_asset()
        resp = AssetResponse.model_validate(obj, from_attributes=True)
        assert resp.id == obj.id
        assert resp.title == obj.title
        assert resp.status == obj.status

    def test_json_serialization(self):
        now = datetime.now(timezone.utc)
        resp = AssetResponse(
            id=uuid.uuid4(),
            title="Test",
            description=None,
            status="pending_review",
            current_version=1,
            created_at=now,
            updated_at=now,
        )
        data = json.loads(resp.model_dump_json())
        assert data["status"] == "pending_review"
        assert data["current_version"] == 1
        assert "created_at" in data
        assert "updated_at" in data

    def test_from_attributes_config(self):
        assert AssetResponse.model_config.get("from_attributes") is True


# ===========================================================================
# Composite Response Schemas
# ===========================================================================


class TestAssetDetailResponse:
    def _build_detail(self, **overrides):
        defaults = dict(
            asset=AssetResponse.model_validate(_make_asset(), from_attributes=True),
            client=ClientResponse.model_validate(_make_client(), from_attributes=True),
            current_version=VersionResponse.model_validate(
                _make_version(), from_attributes=True
            ),
            versions=[
                VersionResponse.model_validate(_make_version(), from_attributes=True),
            ],
            comments=[
                CommentResponse.model_validate(_make_comment(), from_attributes=True),
            ],
            decisions=[
                DecisionResponse.model_validate(_make_decision(), from_attributes=True),
            ],
        )
        defaults.update(overrides)
        return AssetDetailResponse(**defaults)

    def test_full_creation(self):
        detail = self._build_detail()
        assert detail.asset is not None
        assert detail.client is not None
        assert detail.current_version is not None
        assert len(detail.versions) == 1
        assert len(detail.comments) == 1
        assert len(detail.decisions) == 1

    def test_current_version_none(self):
        detail = self._build_detail(current_version=None)
        assert detail.current_version is None

    def test_empty_lists(self):
        detail = self._build_detail(versions=[], comments=[], decisions=[])
        assert detail.versions == []
        assert detail.comments == []
        assert detail.decisions == []

    def test_json_serialization(self):
        detail = self._build_detail()
        data = json.loads(detail.model_dump_json())
        assert "asset" in data
        assert "client" in data
        assert "current_version" in data
        assert isinstance(data["versions"], list)
        assert isinstance(data["comments"], list)
        assert isinstance(data["decisions"], list)

    def test_nested_fields_serialized(self):
        detail = self._build_detail()
        data = json.loads(detail.model_dump_json())
        assert "id" in data["asset"]
        assert "slug" in data["client"]
        assert "version_number" in data["current_version"]
        assert "author_name" in data["comments"][0]
        assert "decided_by" in data["decisions"][0]

    def test_from_attributes_config(self):
        assert AssetDetailResponse.model_config.get("from_attributes") is True


class TestAuthValidateResponse:
    def test_creation(self):
        detail = AssetDetailResponse(
            asset=AssetResponse.model_validate(_make_asset(), from_attributes=True),
            client=ClientResponse.model_validate(_make_client(), from_attributes=True),
            current_version=None,
            versions=[],
            comments=[],
            decisions=[],
        )
        resp = AuthValidateResponse(jwt="eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.test", asset=detail)
        assert resp.jwt.startswith("eyJ")
        assert resp.asset.client.slug == "client_alpha"

    def test_json_serialization(self):
        detail = AssetDetailResponse(
            asset=AssetResponse.model_validate(_make_asset(), from_attributes=True),
            client=ClientResponse.model_validate(_make_client(), from_attributes=True),
            current_version=None,
            versions=[],
            comments=[],
            decisions=[],
        )
        resp = AuthValidateResponse(jwt="test-jwt-token", asset=detail)
        data = json.loads(resp.model_dump_json())
        assert data["jwt"] == "test-jwt-token"
        assert "asset" in data["asset"]
        assert "client" in data["asset"]

    def test_from_attributes_config(self):
        assert AuthValidateResponse.model_config.get("from_attributes") is True


class TestDecisionResultResponse:
    def test_creation(self):
        decision = DecisionResponse.model_validate(
            _make_decision(decision="approved"), from_attributes=True
        )
        asset = AssetResponse.model_validate(
            _make_asset(status="approved"), from_attributes=True
        )
        resp = DecisionResultResponse(decision=decision, asset=asset)
        assert resp.decision.decision == "approved"
        assert resp.asset.status == "approved"

    def test_changes_requested(self):
        decision = DecisionResponse.model_validate(
            _make_decision(decision="changes_requested", comment="Fix layout"),
            from_attributes=True,
        )
        asset = AssetResponse.model_validate(
            _make_asset(status="changes_requested"), from_attributes=True
        )
        resp = DecisionResultResponse(decision=decision, asset=asset)
        assert resp.decision.comment == "Fix layout"
        assert resp.asset.status == "changes_requested"

    def test_json_serialization(self):
        decision = DecisionResponse.model_validate(
            _make_decision(), from_attributes=True
        )
        asset = AssetResponse.model_validate(_make_asset(), from_attributes=True)
        resp = DecisionResultResponse(decision=decision, asset=asset)
        data = json.loads(resp.model_dump_json())
        assert "decision" in data
        assert "asset" in data
        assert "decided_by" in data["decision"]
        assert "title" in data["asset"]

    def test_from_attributes_config(self):
        assert DecisionResultResponse.model_config.get("from_attributes") is True


# ===========================================================================
# Cross-cutting concerns
# ===========================================================================


class TestAllResponseFromAttributes:
    """Every response schema must have from_attributes=True."""

    @pytest.mark.parametrize(
        "schema",
        [
            ClientResponse,
            VersionResponse,
            CommentResponse,
            DecisionResponse,
            AssetResponse,
            AssetDetailResponse,
            AuthValidateResponse,
            DecisionResultResponse,
        ],
    )
    def test_from_attributes_enabled(self, schema):
        assert schema.model_config.get("from_attributes") is True, (
            f"{schema.__name__} must have from_attributes=True"
        )


class TestJsonRoundTrip:
    """All schemas must survive JSON serialization -> deserialization."""

    def test_approve_request(self):
        original = ApproveRequest(comment="Ok")
        restored = ApproveRequest.model_validate_json(original.model_dump_json())
        assert restored.comment == original.comment

    def test_request_changes_request(self):
        original = RequestChangesRequest(comment="Mudar as cores do fundo e tipografia")
        restored = RequestChangesRequest.model_validate_json(original.model_dump_json())
        assert restored.comment == original.comment

    def test_add_comment_request(self):
        original = AddCommentRequest(content="Boa proposta")
        restored = AddCommentRequest.model_validate_json(original.model_dump_json())
        assert restored.content == original.content

    def test_client_response(self):
        original = ClientResponse(
            id=uuid.uuid4(), name="client_delta", slug="client_delta", logo_url=None
        )
        restored = ClientResponse.model_validate_json(original.model_dump_json())
        assert restored.id == original.id
        assert restored.name == original.name

    def test_version_response(self):
        original = VersionResponse(
            id=uuid.uuid4(),
            version_number=1,
            file_type="image",
            file_format="png",
            file_size_bytes=1024,
            width=800,
            height=600,
            duration_seconds=None,
            uploaded_by="Pedro",
            created_at=datetime.now(timezone.utc),
        )
        restored = VersionResponse.model_validate_json(original.model_dump_json())
        assert restored.version_number == original.version_number

    def test_asset_detail_response(self):
        detail = AssetDetailResponse(
            asset=AssetResponse.model_validate(_make_asset(), from_attributes=True),
            client=ClientResponse.model_validate(_make_client(), from_attributes=True),
            current_version=VersionResponse.model_validate(
                _make_version(), from_attributes=True
            ),
            versions=[],
            comments=[],
            decisions=[],
        )
        restored = AssetDetailResponse.model_validate_json(detail.model_dump_json())
        assert restored.asset.title == detail.asset.title
        assert restored.client.slug == detail.client.slug
        assert restored.current_version is not None
