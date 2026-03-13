"""Comment intent detection for auto-status transitions (A1).

Detects approval, delivery, alteration-done, and client-approval intents from
ClickUp comments using regex patterns. Validates user role and current task
status before suggesting a status transition or triggering an action.

The ``client_approval`` intent does NOT change task status — it triggers
the approval email flow directly (EventBridge → ApprovalProcessor Lambda).
"""
import re
from dataclasses import dataclass

# --- Intent patterns (case-insensitive) ---

APPROVAL_PATTERNS = [
    re.compile(r"\baprovado\b", re.IGNORECASE),
    re.compile(r"\bpor mim okk?\b", re.IGNORECASE),
    re.compile(r"\btudo aprovado\b", re.IGNORECASE),
    re.compile(r"\bamassou\b", re.IGNORECASE),
    re.compile(r"\baprovo\b", re.IGNORECASE),
]

DELIVERY_PATTERNS = [
    re.compile(r"\bsegue para aprova[cç][aã]o\b", re.IGNORECASE),
    re.compile(r"\bfinalizado\b", re.IGNORECASE),
    re.compile(r"\bcaptado\b", re.IGNORECASE),
    re.compile(r"\bentrega finalizada\b", re.IGNORECASE),
]

ALTERATION_DONE_PATTERNS = [
    re.compile(r"\balterado\b", re.IGNORECASE),
    re.compile(r"\baltera[cç][aã]o feita\b", re.IGNORECASE),
    re.compile(r"\batualizei\b", re.IGNORECASE),
    re.compile(r"\bajustado\b", re.IGNORECASE),
    re.compile(r"\bcorrigido\b", re.IGNORECASE),
]

CLIENT_APPROVAL_PATTERNS = [
    re.compile(r"\baprova[cç][aã]o do cliente\b", re.IGNORECASE),
    re.compile(r"\benviar para (?:o )?cliente\b", re.IGNORECASE),
    re.compile(r"\bmandar para (?:o )?cliente\b", re.IGNORECASE),
    re.compile(r"\bcliente aprovar\b", re.IGNORECASE),
    re.compile(r"\bencaminhar para (?:o )?cliente\b", re.IGNORECASE),
    re.compile(r"\benviar ao cliente\b", re.IGNORECASE),
]

INTERNAL_APPROVED_PATTERNS = [
    re.compile(r"\baprovado internamente\b", re.IGNORECASE),
    re.compile(r"\bsegue para (?:o )?cliente\b", re.IGNORECASE),
]

# --- Intent types and their constraints ---

# Roles allowed to trigger each intent type
INTENT_ALLOWED_ROLES: dict[str, set[str]] = {
    "approval": {"strategy_reviewer", "content_reviewer", "admin"},
    "delivery": {"designer", "admin"},
    "alteration_done": {"designer", "admin"},
    "client_approval": {"account", "admin"},
    "internal_approved": {"strategy_reviewer", "content_reviewer", "account", "admin"},
}

# Valid source statuses for each intent type
INTENT_VALID_FROM: dict[str, set[str]] = {
    "approval": {"revisao"},
    "delivery": {"em criacao", "alteracao"},
    "alteration_done": {"alteracao"},
    "client_approval": {"aprovado"},
    "internal_approved": {"aprovado"},
}

# Target status for each intent type
# client_approval has no target — it triggers email flow, not a status change
INTENT_TARGET_STATUS: dict[str, str] = {
    "approval": "aprovado",
    "delivery": "revisao",
    "alteration_done": "revisao",
    "client_approval": "",
    "internal_approved": "revisao_cliente",
}


@dataclass(frozen=True)
class CommentIntent:
    """Detected intent from a ClickUp comment."""

    intent_type: str  # "approval", "delivery", "alteration_done"
    target_status: str  # The status to transition to
    matched_pattern: str  # The text that matched
    confidence: float  # 0.0 to 1.0


def _match_patterns(
    text: str,
    patterns: list[re.Pattern],
) -> str | None:
    """Return the first matched pattern text, or None."""
    for pattern in patterns:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def detect_intent(
    comment_text: str,
    user_role: str | None,
    current_status: str | None,
) -> CommentIntent | None:
    """Detect the intent of a ClickUp comment.

    Returns a CommentIntent if a known pattern matches AND the user's role
    and the task's current status are valid for that intent. Returns None
    if no intent is detected or validation fails.

    Args:
        comment_text: The raw comment text.
        user_role: The commenter's role from team_mapping (e.g. "designer").
        current_status: The task's current ClickUp status.
    """
    if not comment_text or not comment_text.strip():
        return None

    # Check each intent type in priority order
    # internal_approved checked FIRST so "segue para cliente" triggers status
    # change (Path B) rather than direct EventBridge (Path A)
    # client_approval checked BEFORE approval to avoid "aprovação do cliente"
    # matching generic "aprovado" pattern instead
    intent_checks: list[tuple[str, list[re.Pattern]]] = [
        ("internal_approved", INTERNAL_APPROVED_PATTERNS),
        ("client_approval", CLIENT_APPROVAL_PATTERNS),
        ("approval", APPROVAL_PATTERNS),
        ("delivery", DELIVERY_PATTERNS),
        ("alteration_done", ALTERATION_DONE_PATTERNS),
    ]

    for intent_type, patterns in intent_checks:
        matched = _match_patterns(comment_text, patterns)
        if matched is None:
            continue

        # Validate role
        allowed_roles = INTENT_ALLOWED_ROLES.get(intent_type, set())
        if user_role and user_role not in allowed_roles:
            continue

        # Validate current status
        valid_from = INTENT_VALID_FROM.get(intent_type, set())
        if current_status and current_status not in valid_from:
            continue

        return CommentIntent(
            intent_type=intent_type,
            target_status=INTENT_TARGET_STATUS[intent_type],
            matched_pattern=matched,
            confidence=1.0,
        )

    return None


def detect_intent_dynamic(
    rules_engine,
    comment_text: str,
    user_role: str | None,
    current_status: str | None,
) -> CommentIntent | None:
    """Detect intent using dynamic rules engine with fallback to hardcoded patterns."""
    if rules_engine and hasattr(rules_engine, 'detect_intent'):
        result = rules_engine.detect_intent(comment_text, user_role, current_status)
        if result is not None:
            return result
    return detect_intent(comment_text, user_role, current_status)
