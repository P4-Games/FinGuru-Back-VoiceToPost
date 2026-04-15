import hashlib
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from .agent_api_utils import search_google_news
from .agent_content_utils import (
    _extract_trend_title,
    _validate_article_depth,
    create_prompt,
    generate_article_content,
    process_article_data,
)
from .policy_engine import ProfilePolicyEngine


class TopicSelector:
    """Selecciona tema y aplica policy gate de perfil."""

    def __init__(self, policy_engine: ProfilePolicyEngine):
        self.policy_engine = policy_engine

    def select(self, agent: Any, trends_data: Dict[str, Any], topic_position: Optional[int], user_id: Optional[int]) -> Dict[str, Any]:
        if topic_position is None:
            selection_result = agent.select_trending_topic(trends_data, user_id)
            if selection_result.get("status") != "success":
                return selection_result

            selected_position = selection_result.get("selected_position")
            selected_title = selection_result.get("selected_title")
            selected_reason = selection_result.get("selected_reason")
        else:
            selected_position = topic_position
            selected_title = _extract_trend_title(trends_data, topic_position)
            if not selected_title:
                return {
                    "status": "error",
                    "message": f"No se pudo extraer título de la tendencia en posición {topic_position}",
                }
            selected_reason = "Selección manual"

        policy_decision = self.policy_engine.evaluate_topic(agent, selected_title)
        if not policy_decision.get("allowed"):
            return {
                "status": "no_suitable_topic",
                "message": "Tema rechazado por policy engine del perfil",
                "reason": policy_decision.get("reason"),
                "policy": policy_decision,
            }

        return {
            "status": "success",
            "selected_position": selected_position,
            "selected_title": selected_title,
            "selected_reason": selected_reason,
            "policy": policy_decision,
        }


class PromptBuilder:
    """Construye prompt y huella para trazabilidad."""

    @staticmethod
    def build(agent: Any, trends_data: Dict[str, Any], search_results: Dict[str, Any], selected_trend: str, topic_position: int) -> Dict[str, Any]:
        prompt = create_prompt(agent, trends_data, search_results, selected_trend, topic_position)
        fingerprint = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return {
            "prompt": prompt,
            "prompt_fingerprint": fingerprint,
            "prompt_length": len(prompt),
        }


class ContentGenerator:
    """Genera contenido y expone parámetros efectivos del LLM."""

    @staticmethod
    def _effective_params(agent: Any) -> Dict[str, Any]:
        return {
            "model": "gpt-4o-mini",
            "temperature": max(0.0, min(1.5, float(getattr(agent, "temperature", 0.6)))),
            "max_tokens": max(256, int(getattr(agent, "max_tokens", 1400))),
            "top_p": 0.9,
            "frequency_penalty": 0.3,
            "presence_penalty": 0.1,
        }

    def generate(self, agent: Any, prompt: str) -> Dict[str, Any]:
        effective_params = self._effective_params(agent)
        content = generate_article_content(agent, prompt)
        return {
            "content": content,
            "llm_effective_params": effective_params,
        }


class DepthValidator:
    """Valida profundidad editorial del artículo."""

    @staticmethod
    def validate(article_content: str) -> Dict[str, Any]:
        return _validate_article_depth(article_content)


class Publisher:
    """Publica artículo usando el publicador existente del agente."""

    @staticmethod
    def publish(agent: Any, article_data: Dict[str, Any], selected_trend: str, search_results: Dict[str, Any]) -> Dict[str, Any]:
        return agent.publish_article(article_data, selected_trend, search_results)


class TrendsPipeline:
    """Pipeline v2 desacoplado para selección, generación, validación y publicación."""

    def __init__(self) -> None:
        self.policy_engine = ProfilePolicyEngine()
        self.topic_selector = TopicSelector(self.policy_engine)
        self.prompt_builder = PromptBuilder()
        self.content_generator = ContentGenerator()
        self.depth_validator = DepthValidator()
        self.publisher = Publisher()

    @staticmethod
    def _build_quality_retry_prompt(base_prompt: str, depth_validation: Dict[str, Any], alignment: Dict[str, Any]) -> str:
        depth_issues = depth_validation.get("issues", []) if isinstance(depth_validation, dict) else []
        alignment_checks = (alignment or {}).get("checks", {})
        weak_checks = [k for k, ok in alignment_checks.items() if not ok]

        retry_block = "\n\nREINTENTO DE CALIDAD (OBLIGATORIO):\n"
        if depth_issues:
            retry_block += "- Corrige estos problemas detectados de profundidad:\n"
            for issue in depth_issues:
                retry_block += f"  * {issue}\n"
        if weak_checks:
            retry_block += "- Mejora explícitamente alineación de perfil en:\n"
            for check in weak_checks:
                retry_block += f"  * {check}\n"
        retry_block += "- Reescribe el artículo completo corrigiendo todo, manteniendo formato markdown requerido.\n"
        return base_prompt + retry_block

    def execute(
        self,
        agent: Any,
        trends_data: Dict[str, Any],
        topic_position: Optional[int] = None,
        dry_run: bool = False,
        correlation_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        correlation_id = correlation_id or str(uuid.uuid4())
        execution_started = datetime.utcnow().isoformat() + "Z"

        timings: Dict[str, float] = {}

        select_start = time.perf_counter()
        user_id = agent.agent_config.get("userId", 5822)
        selection = self.topic_selector.select(agent, trends_data, topic_position, user_id)
        timings["selection_ms"] = round((time.perf_counter() - select_start) * 1000, 2)

        if selection.get("status") != "success":
            return {
                "status": "skipped" if selection.get("status") == "no_suitable_topic" else "error",
                "correlation_id": correlation_id,
                "agent": {
                    "id": agent.agent_id,
                    "name": agent.agent_name,
                },
                "selection": selection,
                "timestamp": execution_started,
                "timings": timings,
            }

        selected_trend = selection["selected_title"]
        selected_position = selection["selected_position"]

        search_start = time.perf_counter()
        search_results = search_google_news(agent, selected_trend)
        timings["search_ms"] = round((time.perf_counter() - search_start) * 1000, 2)

        prompt_start = time.perf_counter()
        prompt_data = self.prompt_builder.build(agent, trends_data, search_results, selected_trend, selected_position)
        timings["prompt_build_ms"] = round((time.perf_counter() - prompt_start) * 1000, 2)

        generation_start = time.perf_counter()
        generation = self.content_generator.generate(agent, prompt_data["prompt"])
        timings["generation_ms"] = round((time.perf_counter() - generation_start) * 1000, 2)

        content = generation.get("content") or ""
        if not content.strip():
            return {
                "status": "error",
                "correlation_id": correlation_id,
                "agent": {
                    "id": agent.agent_id,
                    "name": agent.agent_name,
                },
                "selection": selection,
                "prompt": {
                    "fingerprint": prompt_data["prompt_fingerprint"],
                    "length": prompt_data["prompt_length"],
                },
                "llm": generation.get("llm_effective_params", {}),
                "message": "No se pudo generar contenido",
                "timestamp": execution_started,
                "timings": timings,
            }

        depth_start = time.perf_counter()
        depth_validation = self.depth_validator.validate(content)
        timings["depth_validation_ms"] = round((time.perf_counter() - depth_start) * 1000, 2)

        alignment_start = time.perf_counter()
        profile_alignment = self.policy_engine.evaluate_profile_alignment(agent, content)
        timings["profile_alignment_ms"] = round((time.perf_counter() - alignment_start) * 1000, 2)

        retried = False
        if (not depth_validation.get("is_valid")) or (not profile_alignment.get("aligned")):
            retry_start = time.perf_counter()
            retried = True
            retry_prompt = self._build_quality_retry_prompt(
                prompt_data["prompt"],
                depth_validation,
                profile_alignment,
            )
            retry_generation = self.content_generator.generate(agent, retry_prompt)
            retry_content = retry_generation.get("content") or ""
            if retry_content.strip():
                content = retry_content
                generation = retry_generation
                depth_validation = self.depth_validator.validate(content)
                profile_alignment = self.policy_engine.evaluate_profile_alignment(agent, content)
            timings["quality_retry_ms"] = round((time.perf_counter() - retry_start) * 1000, 2)

        if not depth_validation.get("is_valid"):
            return {
                "status": "skipped",
                "correlation_id": correlation_id,
                "agent": {
                    "id": agent.agent_id,
                    "name": agent.agent_name,
                },
                "selection": selection,
                "prompt": {
                    "fingerprint": prompt_data["prompt_fingerprint"],
                    "length": prompt_data["prompt_length"],
                },
                "llm": generation.get("llm_effective_params", {}),
                "validation": {
                    "depth": depth_validation,
                    "profile_alignment": profile_alignment,
                },
                "retried": retried,
                "message": "Artículo rechazado por falta de profundidad",
                "timestamp": execution_started,
                "timings": timings,
            }

        process_start = time.perf_counter()
        article_data = process_article_data(content)
        policy_article = self.policy_engine.evaluate_article(agent, article_data, content)
        timings["article_processing_ms"] = round((time.perf_counter() - process_start) * 1000, 2)

        if not policy_article.get("allowed"):
            return {
                "status": "skipped",
                "correlation_id": correlation_id,
                "agent": {
                    "id": agent.agent_id,
                    "name": agent.agent_name,
                },
                "selection": selection,
                "prompt": {
                    "fingerprint": prompt_data["prompt_fingerprint"],
                    "length": prompt_data["prompt_length"],
                },
                "llm": generation.get("llm_effective_params", {}),
                "validation": {
                    "depth": depth_validation,
                    "policy": policy_article,
                    "profile_alignment": profile_alignment,
                },
                "article": {
                    "title": article_data.get("title"),
                    "category": article_data.get("category"),
                },
                "message": "Artículo rechazado por policy engine",
                "timestamp": execution_started,
                "timings": timings,
            }

        publish_start = time.perf_counter()
        publish_result = {
            "status": "skipped",
            "message": "dry_run habilitado: no se publicó en fin.guru",
        }
        if not dry_run:
            publish_result = self.publisher.publish(agent, article_data, selected_trend, search_results)
        timings["publish_ms"] = round((time.perf_counter() - publish_start) * 1000, 2)

        return {
            "status": "success" if publish_result.get("status") == "success" or dry_run else "error",
            "correlation_id": correlation_id,
            "agent": {
                "id": agent.agent_id,
                "name": agent.agent_name,
                "profile": {
                    "writing_style": agent.writing_style,
                    "tone": agent.tone,
                    "target_audience": agent.target_audience,
                    "preferred_categories": agent.preferred_categories,
                    "forbidden_topics": agent.forbidden_topics,
                },
            },
            "selection": {
                "position": selected_position,
                "trend": selected_trend,
                "reason": selection.get("selected_reason"),
                "policy": selection.get("policy"),
            },
            "prompt": {
                "fingerprint": prompt_data["prompt_fingerprint"],
                "length": prompt_data["prompt_length"],
            },
            "llm": generation.get("llm_effective_params", {}),
            "validation": {
                "depth": depth_validation,
                "policy": policy_article,
                "profile_alignment": profile_alignment,
            },
            "retried": retried,
            "article": {
                "title": article_data.get("title"),
                "category": article_data.get("category"),
            },
            "publication": {
                "dry_run": dry_run,
                "result": publish_result,
            },
            "timestamp": execution_started,
            "timings": timings,
        }
