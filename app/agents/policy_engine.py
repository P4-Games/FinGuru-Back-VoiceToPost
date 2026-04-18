import os
import re
from typing import Any, Dict, List


FINANCIAL_TITLE_KEYWORDS = {
    "dolar", "dólar", "blue", "mep", "ccl", "reservas", "bcra", "indec",
    "inflacion", "inflación", "tasa", "tasas", "deuda", "bono", "bonos",
    "acciones", "merval", "riesgo pais", "riesgo país", "banco", "bancos",
    "mercado", "mercados", "finanzas", "economia", "economía", "fiscal",
    "exportaciones", "importaciones", "comercio exterior", "superavit", "déficit",
    "superávit", "deficit", "pbi", "salario", "paritarias", "cedear", "cripto",
}

FINANCIAL_CATEGORY_HINTS = {
    "econom", "finanz", "negocios", "business", "markets", "mercados", "bank",
    "inversion", "inversión", "trading", "currenc", "moneda",
}

NON_FINANCIAL_HARD_BLOCKLIST = {
    "gran hermano", "reality show", "showmatch", "tinelli", "famosos",
    "chimentos", "escandalo", "escándalo", "boca river", "river boca",
    "furia", "eliminado", "gala", "rating tv",
}


class ProfilePolicyEngine:
    """Motor formal de políticas editoriales por perfil de agente."""

    @staticmethod
    def _normalize_list(values: Any) -> List[str]:
        if not values:
            return []
        if isinstance(values, list):
            return [str(v).strip().lower() for v in values if str(v).strip()]
        if isinstance(values, str):
            return [v.strip().lower() for v in values.split(",") if v.strip()]
        return []

    @staticmethod
    def _is_truthy_env(value: str) -> bool:
        return str(value).strip().lower() in {"1", "true", "yes", "y", "on"}

    @staticmethod
    def _normalize_categories(topic_categories: Any) -> List[str]:
        normalized: List[str] = []
        if not topic_categories:
            return normalized

        if isinstance(topic_categories, list):
            for item in topic_categories:
                if isinstance(item, dict):
                    candidate = item.get("name") or item.get("title") or item.get("category")
                    if candidate:
                        normalized.append(str(candidate).strip().lower())
                elif isinstance(item, str):
                    normalized.append(item.strip().lower())
        elif isinstance(topic_categories, str):
            normalized.append(topic_categories.strip().lower())

        return [token for token in normalized if token]

    def evaluate_financial_relevance(self, topic_title: str, topic_categories: Any = None) -> Dict[str, Any]:
        title_lc = (topic_title or "").strip().lower()
        categories_lc = self._normalize_categories(topic_categories)

        hard_block_hits = [term for term in NON_FINANCIAL_HARD_BLOCKLIST if term in title_lc]

        title_hits = [kw for kw in FINANCIAL_TITLE_KEYWORDS if kw in title_lc]

        category_hits: List[str] = []
        for category in categories_lc:
            if any(hint in category for hint in FINANCIAL_CATEGORY_HINTS):
                category_hits.append(category)

        # Heurística extra: captura títulos con activos/monedas en mayúsculas o %/$
        token_signal = bool(re.search(r"\b(usd|ars|eur|btc|eth|mep|ccl|blue)\b|[%$]", title_lc))

        score = (len(title_hits) * 2) + (len(category_hits) * 2) + (1 if token_signal else 0)
        allowed = (not hard_block_hits) and score >= 2

        return {
            "allowed": allowed,
            "score": score,
            "hard_block_hits": hard_block_hits,
            "title_hits": title_hits[:8],
            "category_hits": category_hits[:4],
            "token_signal": token_signal,
        }

    def evaluate_topic(self, agent: Any, topic_title: str, topic_categories: Any = None) -> Dict[str, Any]:
        preferred_categories = self._normalize_list(getattr(agent, "preferred_categories", []))
        forbidden_topics = self._normalize_list(getattr(agent, "forbidden_topics", []))
        strict_financial_gate = self._is_truthy_env(
            os.getenv("FINANCIAL_RELEVANCE_STRICT", "true")
        )

        title_lc = (topic_title or "").lower()
        forbidden_hits = [rule for rule in forbidden_topics if rule and rule in title_lc]

        financial_relevance = self.evaluate_financial_relevance(topic_title, topic_categories)

        allowed = not forbidden_hits
        reasons = []
        if forbidden_hits:
            reasons.append("Coincide con forbidden_topics")

        if strict_financial_gate and not financial_relevance.get("allowed"):
            allowed = False
            reasons.append("Tema fuera de foco financiero")

        penalty = len(forbidden_hits) * 100

        preferred_hits = [cat for cat in preferred_categories if cat and cat in title_lc]

        return {
            "allowed": allowed,
            "reason": " | ".join(reasons) if reasons else "OK",
            "forbidden_hits": forbidden_hits,
            "preferred_hits": preferred_hits,
            "score_delta": -penalty + (10 if preferred_hits else 0),
            "financial_strict_gate": strict_financial_gate,
            "financial_relevance": financial_relevance,
        }

    def evaluate_article(self, agent: Any, article_data: Dict[str, Any], article_content: str) -> Dict[str, Any]:
        preferred_categories = self._normalize_list(getattr(agent, "preferred_categories", []))
        forbidden_topics = self._normalize_list(getattr(agent, "forbidden_topics", []))

        category = str(article_data.get("category", "")).lower()
        combined_text = f"{article_data.get('title', '')} {article_content}".lower()

        forbidden_hits = [rule for rule in forbidden_topics if rule and rule in combined_text]
        preferred_category_hit = bool(category and category in preferred_categories) if preferred_categories else True

        allowed = not forbidden_hits
        reasons = []
        if forbidden_hits:
            reasons.append("Contenido/artículo coincide con forbidden_topics")
        if not preferred_category_hit:
            reasons.append("Categoría fuera de preferred_categories")

        return {
            "allowed": allowed,
            "reason": " | ".join(reasons) if reasons else "OK",
            "forbidden_hits": forbidden_hits,
            "preferred_category_hit": preferred_category_hit,
            "preferred_categories": preferred_categories,
            "detected_category": category,
        }

    def evaluate_profile_alignment(self, agent: Any, article_content: str) -> Dict[str, Any]:
        """Valida alineación mínima con writing_style, tone y target_audience."""
        text = (article_content or "").lower()
        writing_style = str(getattr(agent, "writing_style", "periodistico") or "periodistico").lower()
        tone = str(getattr(agent, "tone", "neutral") or "neutral").lower()
        target_audience = str(getattr(agent, "target_audience", "audiencia general") or "audiencia general").lower()

        checks = []

        style_keywords = {
            "periodistico": ["según", "reportó", "indicó", "contexto"],
            "analitico": ["causa", "consecuencia", "escenario", "impacto"],
            "didactico": ["explic", "en términos simples", "ejemplo", "paso"],
            "opinion": ["tesis", "argument", "postura", "conclu"],
        }
        style_tokens = style_keywords.get(writing_style, ["análisis", "contexto"])
        checks.append(any(token in text for token in style_tokens))

        tone_keywords = {
            "neutral": ["por un lado", "por otro", "sin embargo"],
            "formal": ["en consecuencia", "no obstante", "asimismo"],
            "cercano": ["en la práctica", "esto significa", "a nivel"],
            "critico": ["riesgo", "limitación", "vulnerabilidad"],
        }
        tone_tokens = tone_keywords.get(tone, ["sin embargo", "impacto"])
        checks.append(any(token in text for token in tone_tokens))

        audience_ok = True
        if "invers" in target_audience:
            audience_ok = any(token in text for token in ["riesgo", "rendimiento", "cartera", "volatilidad"])
        elif "empr" in target_audience:
            audience_ok = any(token in text for token in ["pyme", "startup", "costo", "margen"])
        elif "general" in target_audience:
            audience_ok = any(token in text for token in ["esto significa", "en términos simples", "en la práctica"])
        checks.append(audience_ok)

        score = round((sum(1 for c in checks if c) / max(len(checks), 1)) * 100, 2)
        aligned = score >= 66.0

        return {
            "aligned": aligned,
            "score": score,
            "writing_style": writing_style,
            "tone": tone,
            "target_audience": target_audience,
            "checks": {
                "style": checks[0],
                "tone": checks[1],
                "audience": checks[2],
            },
        }
