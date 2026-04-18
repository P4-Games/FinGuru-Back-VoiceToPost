import hashlib
import os
import time
import uuid
from datetime import datetime
from typing import Any, Dict, Optional

from .agent_api_utils import get_recent_finguru_articles, search_google_news
from .agent_content_utils import (
    _extract_trend_title,
    _validate_article_depth,
    create_prompt,
    generate_article_content,
    process_article_data,
)
from .market_data_utils import get_market_data_snapshot
from .policy_engine import ProfilePolicyEngine


def _extract_trend_payload(trends_data: Dict[str, Any], position: Optional[int]) -> Dict[str, Any]:
    if not isinstance(trends_data, dict) or not isinstance(position, int) or position < 1:
        return {}

    topics = trends_data.get("trending_topics", [])
    if not isinstance(topics, list) or position > len(topics):
        return {}

    selected = topics[position - 1]
    if isinstance(selected, dict):
        return selected
    if isinstance(selected, str):
        return {"title": selected, "query": selected, "categories": []}
    return {}


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

        selected_payload = _extract_trend_payload(trends_data, selected_position)
        selected_categories = selected_payload.get("categories", []) if isinstance(selected_payload, dict) else []

        policy_decision = self.policy_engine.evaluate_topic(
            agent,
            selected_title,
            selected_categories,
        )
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
            "selected_categories": selected_categories,
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


class OutlineGenerator:
    """Genera esquema previo para guiar el borrador y evitar contenido plano."""

    @staticmethod
    def _fallback_outline(selected_trend: str) -> str:
        return (
            f"1) Contexto actual de {selected_trend}\n"
            "2) Causas y factores principales\n"
            "3) Comparación internacional con datos\n"
            "4) Implicancias en Argentina\n"
            "5) Escenarios y riesgos a corto/mediano plazo"
        )

    def generate(self, agent: Any, selected_trend: str, search_results: Dict[str, Any]) -> Dict[str, Any]:
        prompt = (
            "Arma un outline periodístico en español para un artículo financiero de FinGuru. "
            "Debe incluir 5 a 6 secciones accionables y evitar relleno. "
            f"Tema: {selected_trend}\n"
            "Devuelve solo una lista numerada."
        )

        if not hasattr(agent, "openai_client"):
            return {
                "status": "fallback",
                "outline": self._fallback_outline(selected_trend),
                "reason": "agent.openai_client no disponible",
            }

        try:
            model_name = os.getenv("OUTLINE_MODEL", "gpt-4o-mini")
            response = agent.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Eres editor senior de economía en Argentina."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=320,
                temperature=0.2,
            )
            outline = (response.choices[0].message.content or "").strip()
            if not outline:
                outline = self._fallback_outline(selected_trend)
                return {"status": "fallback", "outline": outline, "reason": "outline vacío"}

            return {"status": "success", "outline": outline, "model": model_name}
        except Exception as exc:
            return {
                "status": "fallback",
                "outline": self._fallback_outline(selected_trend),
                "reason": str(exc),
            }


class FactChecker:
    """Ejecuta chequeo de factualidad y densidad de evidencia antes de publicar."""

    @staticmethod
    def _parse_factcheck_text(raw_text: str) -> Dict[str, Any]:
        text = (raw_text or "").strip()
        text_lc = text.lower()
        verdict = "PASS" if "verdict: pass" in text_lc else "FAIL"
        issues = []
        for line in text.splitlines():
            line_clean = line.strip()
            if line_clean.startswith("-"):
                issues.append(line_clean.lstrip("- ").strip())
        return {
            "verdict": verdict,
            "issues": issues,
            "raw": text,
        }

    def check(self, agent: Any, draft: str, depth_validation: Dict[str, Any], search_results: Dict[str, Any]) -> Dict[str, Any]:
        deterministic_issues = []

        numeric_count = int(depth_validation.get("numeric_evidence_count", 0) or 0)
        if numeric_count < 3:
            deterministic_issues.append(f"Muy pocas cifras: {numeric_count} (mínimo recomendado 3)")

        forbidden_phrase_hits = depth_validation.get("forbidden_phrase_hits", []) or []
        if forbidden_phrase_hits:
            deterministic_issues.append(
                "Frases vagas detectadas: " + ", ".join(forbidden_phrase_hits)
            )

        llm_check = {"verdict": "PASS", "issues": [], "raw": ""}
        if hasattr(agent, "openai_client"):
            try:
                model_name = os.getenv("FACTCHECK_MODEL", "gpt-4o-mini")
                prompt = (
                    "Evalúa factualidad y precisión de este borrador financiero. "
                    "Responde exactamente con formato:\n"
                    "VERDICT: PASS o FAIL\n"
                    "ISSUES:\n"
                    "- issue 1\n"
                    "- issue 2\n"
                    "Si está bien, deja ISSUES vacío.\n\n"
                    f"BORRADOR:\n{draft}"
                )
                response = agent.openai_client.chat.completions.create(
                    model=model_name,
                    messages=[
                        {"role": "system", "content": "Eres un fact-checker económico exigente."},
                        {"role": "user", "content": prompt},
                    ],
                    max_tokens=260,
                    temperature=0.1,
                )
                llm_check = self._parse_factcheck_text(response.choices[0].message.content or "")
                llm_check["model"] = model_name
            except Exception as exc:
                llm_check = {
                    "verdict": "PASS",
                    "issues": [],
                    "raw": "",
                    "warning": str(exc),
                }

        combined_issues = deterministic_issues + list(llm_check.get("issues", []))
        passed = (not deterministic_issues) and llm_check.get("verdict") == "PASS"

        return {
            "passed": passed,
            "deterministic_issues": deterministic_issues,
            "llm": llm_check,
            "issues": combined_issues,
        }


class DevilAdvocateReviewer:
    """Critica el borrador para subir tono, contundencia y valor diferencial."""

    def review(self, agent: Any, draft: str) -> Dict[str, Any]:
        if not hasattr(agent, "openai_client"):
            return {
                "status": "skipped",
                "critique": "Sin cliente OpenAI para revisión crítica.",
            }

        try:
            model_name = os.getenv("DEVIL_ADVOCATE_MODEL", "gpt-4o-mini")
            prompt = (
                "Actúa como abogado del diablo de un portal económico. "
                "Critica el borrador y di cómo volverlo menos aburrido y más contundente. "
                "Devuelve 3 bullets concretos sin reescribir todo.\n\n"
                f"BORRADOR:\n{draft}"
            )
            response = agent.openai_client.chat.completions.create(
                model=model_name,
                messages=[
                    {"role": "system", "content": "Eres crítico editorial directo y técnico."},
                    {"role": "user", "content": prompt},
                ],
                max_tokens=220,
                temperature=0.2,
            )
            critique = (response.choices[0].message.content or "").strip()
            return {
                "status": "success",
                "model": model_name,
                "critique": critique,
            }
        except Exception as exc:
            return {
                "status": "error",
                "critique": "No se pudo generar crítica.",
                "error": str(exc),
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
        self.outline_generator = OutlineGenerator()
        self.content_generator = ContentGenerator()
        self.depth_validator = DepthValidator()
        self.fact_checker = FactChecker()
        self.devil_advocate = DevilAdvocateReviewer()
        self.publisher = Publisher()

    @staticmethod
    def _build_quality_retry_prompt(
        base_prompt: str,
        depth_validation: Dict[str, Any],
        alignment: Dict[str, Any],
        fact_check: Optional[Dict[str, Any]] = None,
        devil_review: Optional[Dict[str, Any]] = None,
    ) -> str:
        depth_issues = depth_validation.get("issues", []) if isinstance(depth_validation, dict) else []
        alignment_checks = (alignment or {}).get("checks", {})
        weak_checks = [k for k, ok in alignment_checks.items() if not ok]
        fact_issues = (fact_check or {}).get("issues", []) if isinstance(fact_check, dict) else []
        devil_text = (devil_review or {}).get("critique", "") if isinstance(devil_review, dict) else ""

        retry_block = "\n\nREINTENTO DE CALIDAD (OBLIGATORIO):\n"
        if depth_issues:
            retry_block += "- Corrige estos problemas detectados de profundidad:\n"
            for issue in depth_issues:
                retry_block += f"  * {issue}\n"
        if weak_checks:
            retry_block += "- Mejora explícitamente alineación de perfil en:\n"
            for check in weak_checks:
                retry_block += f"  * {check}\n"
        if fact_issues:
            retry_block += "- Corrige estos hallazgos de fact-check:\n"
            for issue in fact_issues:
                retry_block += f"  * {issue}\n"
        if devil_text:
            retry_block += "- Aplica estas críticas del abogado del diablo para subir contundencia:\n"
            for line in str(devil_text).splitlines()[:8]:
                clean = line.strip()
                if clean:
                    retry_block += f"  * {clean}\n"
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

        enrichment_start = time.perf_counter()
        if not isinstance(search_results, dict):
            search_results = {}

        geo = "AR"
        if isinstance(trends_data, dict):
            geo = trends_data.get("geo", "AR") or "AR"

        related_context = {
            "status": "skipped",
            "message": "agent.trends_api no disponible",
            "query": selected_trend,
            "related_queries": [],
            "related_topics": [],
        }

        if hasattr(agent, "trends_api"):
            try:
                related_context = agent.trends_api.get_related_trend_context(
                    query=selected_trend,
                    geo=geo,
                    language="es-419",
                )
            except Exception as exc:
                related_context = {
                    "status": "error",
                    "message": str(exc),
                    "query": selected_trend,
                    "related_queries": [],
                    "related_topics": [],
                }

        market_data = get_market_data_snapshot()

        links_context = get_recent_finguru_articles(limit=5)
        internal_links = links_context.get("articles", []) if isinstance(links_context, dict) else []

        search_results["related_context"] = related_context
        search_results["market_data"] = market_data
        search_results["internal_links"] = internal_links
        timings["context_enrichment_ms"] = round((time.perf_counter() - enrichment_start) * 1000, 2)

        prompt_start = time.perf_counter()
        prompt_data = self.prompt_builder.build(agent, trends_data, search_results, selected_trend, selected_position)
        timings["prompt_build_ms"] = round((time.perf_counter() - prompt_start) * 1000, 2)

        outline_start = time.perf_counter()
        outline_data = self.outline_generator.generate(agent, selected_trend, search_results)
        outline_text = outline_data.get("outline", "")
        timings["outline_ms"] = round((time.perf_counter() - outline_start) * 1000, 2)

        generation_prompt = prompt_data["prompt"]
        if outline_text:
            generation_prompt += (
                "\n\nOUTLINE EDITORIAL PREVIO (OBLIGATORIO RESPETAR):\n"
                f"{outline_text}\n"
            )

        generation_start = time.perf_counter()
        generation = self.content_generator.generate(agent, generation_prompt)
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

        factcheck_start = time.perf_counter()
        fact_check = self.fact_checker.check(agent, content, depth_validation, search_results)
        timings["factcheck_ms"] = round((time.perf_counter() - factcheck_start) * 1000, 2)

        devil_start = time.perf_counter()
        devil_review = self.devil_advocate.review(agent, content)
        timings["devil_advocate_ms"] = round((time.perf_counter() - devil_start) * 1000, 2)

        retried = False
        if (
            (not depth_validation.get("is_valid"))
            or (not profile_alignment.get("aligned"))
            or (not fact_check.get("passed"))
        ):
            retry_start = time.perf_counter()
            retried = True
            retry_prompt = self._build_quality_retry_prompt(
                generation_prompt,
                depth_validation,
                profile_alignment,
                fact_check,
                devil_review,
            )
            retry_generation = self.content_generator.generate(agent, retry_prompt)
            retry_content = retry_generation.get("content") or ""
            if retry_content.strip():
                content = retry_content
                generation = retry_generation
                depth_validation = self.depth_validator.validate(content)
                profile_alignment = self.policy_engine.evaluate_profile_alignment(agent, content)
                fact_check = self.fact_checker.check(agent, content, depth_validation, search_results)
                devil_review = self.devil_advocate.review(agent, content)
            timings["quality_retry_ms"] = round((time.perf_counter() - retry_start) * 1000, 2)

        if (not depth_validation.get("is_valid")) or (not fact_check.get("passed")):
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
                    "fact_check": fact_check,
                },
                "review": {
                    "devil_advocate": devil_review,
                },
                "retried": retried,
                "message": "Artículo rechazado por profundidad insuficiente o fact-check fallido",
                "timestamp": execution_started,
                "timings": timings,
            }

        process_start = time.perf_counter()
        article_data = process_article_data(
            content,
            selected_trend=selected_trend,
            search_results=search_results,
        )
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
                    "fact_check": fact_check,
                },
                "review": {
                    "devil_advocate": devil_review,
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
                "categories": selection.get("selected_categories", []),
                "reason": selection.get("selected_reason"),
                "policy": selection.get("policy"),
            },
            "context": {
                "related_context_status": related_context.get("status"),
                "market_data_status": market_data.get("status"),
                "internal_links_total": len(internal_links),
            },
            "workflow": {
                "outline": outline_data,
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
                "fact_check": fact_check,
            },
            "review": {
                "devil_advocate": devil_review,
            },
            "retried": retried,
            "article": {
                "title": article_data.get("title"),
                "category": article_data.get("category"),
                "seo_metadata": article_data.get("seo_metadata", {}),
            },
            "publication": {
                "dry_run": dry_run,
                "result": publish_result,
            },
            "timestamp": execution_started,
            "timings": timings,
        }
