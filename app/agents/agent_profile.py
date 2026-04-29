from dataclasses import dataclass, asdict
from typing import Any, Dict, List, Optional


def _to_text(value: Any, default: str = "") -> str:
    if value is None:
        return default
    if isinstance(value, str):
        return value.strip()
    return str(value).strip()


def _to_float(value: Any, default: float) -> float:
    try:
        if value is None or value == "":
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _to_int(value: Any, default: int) -> int:
    try:
        if value is None or value == "":
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _to_optional_int(value: Any) -> Optional[int]:
    """IDs desde la API pueden venir como str; unificamos a int para comparaciones."""
    try:
        if value is None or value == "":
            return None
        return int(value)
    except (TypeError, ValueError):
        return None


def _normalize_string_list(value: Any) -> List[str]:
    if value is None:
        return []

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        parts = [item.strip() for item in value.split(",")]
        return [item for item in parts if item]

    return []


@dataclass
class AgentProfile:
    id: Optional[int]
    name: str
    user_id: Optional[int]
    personality: str
    trending: str
    format_markdown: str
    writing_style: str
    tone: str
    target_audience: str
    preferred_categories: List[str]
    example_article: str
    forbidden_topics: List[str]
    temperature: float
    max_tokens: int
    created_at: str
    updated_at: str
    published_at: str

    @classmethod
    def from_api_payload(cls, agent_item: Dict[str, Any]) -> "AgentProfile":
        attributes = agent_item.get("attributes", {}) if isinstance(agent_item, dict) else {}
        user_data = attributes.get("user", {})
        user_id = None

        if isinstance(user_data, dict) and "data" in user_data:
            user_id = user_data.get("data", {}).get("id")
        elif isinstance(user_data, dict) and "id" in user_data:
            user_id = user_data.get("id")

        # Cuenta bajo la que debe publicarse en fin.guru (perfil del agente). Si existe en CMS,
        # tiene prioridad sobre `user`, que suele ser el admin/creador del registro.
        publish_user = _to_optional_int(
            attributes.get("publishedAsUserId")
            or attributes.get("publisherUserId")
            or attributes.get("publisher_user_id")
            or attributes.get("authorUserId")
        )
        if publish_user is not None:
            user_id = publish_user

        return cls.from_flat_payload(
            {
                "id": agent_item.get("id"),
                "name": attributes.get("name"),
                "userId": user_id,
                "personality": attributes.get("personality"),
                "trending": attributes.get("trending"),
                "format_markdown": attributes.get("format_markdown"),
                "writing_style": attributes.get("writing_style"),
                "tone": attributes.get("tone"),
                "target_audience": attributes.get("target_audience"),
                "preferred_categories": attributes.get("preferred_categories"),
                "example_article": attributes.get("example_article"),
                "forbidden_topics": attributes.get("forbidden_topics"),
                "temperature": attributes.get("temperature"),
                "max_tokens": attributes.get("max_tokens"),
                "createdAt": attributes.get("createdAt"),
                "updatedAt": attributes.get("updatedAt"),
                "publishedAt": attributes.get("publishedAt"),
            }
        )

    @classmethod
    def from_flat_payload(cls, payload: Dict[str, Any]) -> "AgentProfile":
        temperature = _to_float(payload.get("temperature"), 0.6)
        if temperature < 0.0:
            temperature = 0.0
        if temperature > 1.5:
            temperature = 1.5

        max_tokens = _to_int(payload.get("max_tokens"), 1400)
        if max_tokens < 256:
            max_tokens = 256
        if max_tokens > 3500:
            max_tokens = 3500

        publisher_override = _to_optional_int(
            payload.get("publishedAsUserId")
            or payload.get("publisherUserId")
            or payload.get("publisher_user_id")
            or payload.get("authorUserId")
        )
        fallback_uid = _to_optional_int(payload.get("userId"))
        effective_uid = publisher_override if publisher_override is not None else fallback_uid

        return cls(
            id=_to_optional_int(payload.get("id")),
            name=_to_text(payload.get("name"), "default-agent"),
            user_id=effective_uid,
            personality=_to_text(
                payload.get("personality"),
                "Eres un periodista especializado en tendencias de Argentina que debe crear contenido en Markdown",
            ),
            trending=_to_text(
                payload.get("trending"),
                "Considera: - Relevancia para Argentina - Potencial de generar interés - Actualidad e importancia - Impacto social, económico o cultural",
            ),
            format_markdown=_to_text(payload.get("format_markdown"), ""),
            writing_style=_to_text(payload.get("writing_style"), "periodistico"),
            tone=_to_text(payload.get("tone"), "neutral"),
            target_audience=_to_text(payload.get("target_audience"), "audiencia general argentina"),
            preferred_categories=_normalize_string_list(payload.get("preferred_categories")),
            example_article=_to_text(payload.get("example_article"), ""),
            forbidden_topics=_normalize_string_list(payload.get("forbidden_topics")),
            temperature=temperature,
            max_tokens=max_tokens,
            created_at=_to_text(payload.get("createdAt"), ""),
            updated_at=_to_text(payload.get("updatedAt"), ""),
            published_at=_to_text(payload.get("publishedAt"), ""),
        )

    def to_agent_dict(self) -> Dict[str, Any]:
        data = asdict(self)
        return {
            "id": data["id"],
            "name": data["name"],
            "userId": data["user_id"],
            "personality": data["personality"],
            "trending": data["trending"],
            "format_markdown": data["format_markdown"],
            "writing_style": data["writing_style"],
            "tone": data["tone"],
            "target_audience": data["target_audience"],
            "preferred_categories": data["preferred_categories"],
            "example_article": data["example_article"],
            "forbidden_topics": data["forbidden_topics"],
            "temperature": data["temperature"],
            "max_tokens": data["max_tokens"],
            "createdAt": data["created_at"],
            "updatedAt": data["updated_at"],
            "publishedAt": data["published_at"],
        }