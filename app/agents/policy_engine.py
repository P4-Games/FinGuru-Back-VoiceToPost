from typing import Any, Dict, List


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

    def evaluate_topic(self, agent: Any, topic_title: str) -> Dict[str, Any]:
        preferred_categories = self._normalize_list(getattr(agent, "preferred_categories", []))
        forbidden_topics = self._normalize_list(getattr(agent, "forbidden_topics", []))

        title_lc = (topic_title or "").lower()
        forbidden_hits = [rule for rule in forbidden_topics if rule and rule in title_lc]

        allowed = not forbidden_hits
        penalty = len(forbidden_hits) * 100

        preferred_hits = [cat for cat in preferred_categories if cat and cat in title_lc]

        return {
            "allowed": allowed,
            "reason": "Coincide con forbidden_topics" if forbidden_hits else "OK",
            "forbidden_hits": forbidden_hits,
            "preferred_hits": preferred_hits,
            "score_delta": -penalty + (10 if preferred_hits else 0),
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
