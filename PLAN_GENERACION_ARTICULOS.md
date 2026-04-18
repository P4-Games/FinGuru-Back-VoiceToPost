# Plan De Modularizacion: Generacion De Articulos (Solo Texto)

## 1. Resumen Ejecutivo
Este documento define el plan para pasar el sistema actual de generacion de articulos desde un MVP a un producto modular, escalable y comercializable.

El foco es exclusivo en articulos escritos.
Audio queda fuera de alcance.

## 2. Objetivo De Negocio
Construir una plataforma de generacion de articulos que permita:
1. Mejor calidad editorial de forma consistente.
2. Configuracion por cliente (tono, estilo, audiencia, limites).
3. Operacion estable con trazabilidad completa por ejecucion.
4. Integracion sencilla para terceros via contrato API versionado.

## 3. Alcance
### Incluido
1. Flujo de generacion por texto.
2. Orquestacion multiagente para articulos.
3. Validaciones de calidad y politicas editoriales.
4. Preparacion para publicacion y metadatos SEO.
5. Observabilidad y metricas de calidad/costo.

### Excluido
1. Flujo de audio a texto.
2. Endpoints y pipelines de audio.
3. Cualquier optimizacion de transcripcion.

## 4. Estado Actual (Base Tecnica)
1. Existe un pipeline v2 desacoplado en app/agents/trends_pipeline.py con etapas de seleccion, outline, generacion, validacion, fact-check y publicacion.
2. Existe un flujo legacy secuencial (Crew) en app/agents/agents.py.
3. El endpoint de texto en app/main.py usa hoy el flujo legacy para generar articulos.
4. Hay utilidades de contenido y scoring de profundidad en app/agents/agent_content_utils.py.
5. Hay policy engine reutilizable en app/agents/policy_engine.py.

## 5. Arquitectura Objetivo (Producto)
Se propone separar el dominio de generacion en 6 modulos:

1. Generation Orchestrator
Responsabilidad: coordinar etapas, reintentos, fallback y estado final.

2. Content Intelligence
Responsabilidad: prompting, outline, redaccion y enriquecimiento de contexto.

3. Quality Gate
Responsabilidad: profundidad, fact-check, alineacion de perfil y bloqueos de policy.

4. Publishing Adapter
Responsabilidad: transformar salida final en payload publicable y manejar metadatos.

5. Tenant Profile Engine
Responsabilidad: aplicar reglas por cliente (estilo, tono, audiencia, restricciones).

6. Telemetry And Cost
Responsabilidad: tiempos por etapa, costo estimado, score de calidad y trazabilidad.

## 6. Plan De Implementacion Por Sprints
## Sprint 1 (Base Unificada)
Objetivo: crear un motor unico para articulos y mantener fallback al legacy.

Tareas:
1. Crear un modulo ArticleGenerationService como fachada unica del flujo.
2. Estandarizar un objeto de salida comun (status, article, validation, timings, correlation_id).
3. Conectar el endpoint de texto al nuevo servicio detras de feature flag.
4. Mantener fallback al flujo legacy si falla el flujo nuevo.

Criterios de aceptacion:
1. El endpoint de texto puede operar en modo nuevo y modo legacy.
2. El contrato de salida es consistente entre ejecuciones.
3. No hay caidas de servicio en produccion.

## Sprint 2 (Modularizacion Interna)
Objetivo: reducir acoplamiento y habilitar cambios por modulo.

Tareas:
1. Extraer interfaces para PromptBuilder, DraftGenerator, Validator y Publisher.
2. Aislar dependencias externas en adaptadores.
3. Separar reglas de validacion en un paquete QualityGate independiente.

Criterios de aceptacion:
1. Se puede reemplazar la logica de una etapa sin tocar las demas.
2. Cada modulo tiene responsabilidades claras y pruebas unitarias basicas.

## Sprint 3 (Producto Multi-Cliente)
Objetivo: parametrizar calidad y estilo por cliente.

Tareas:
1. Definir perfil editorial por cliente con versionado.
2. Permitir niveles de rigor (strict, standard, fast).
3. Aplicar limites y politicas por tenant en el pipeline.

Criterios de aceptacion:
1. Dos clientes con perfiles distintos producen resultados diferentes con el mismo tema.
2. Las restricciones de un cliente no impactan a otro.

## Sprint 4 (Hardening Comercial)
Objetivo: dejar listo para vender y operar con SLA interno.

Tareas:
1. Publicar contrato API v1 de generacion de articulos.
2. Exponer metricas por ejecucion (tiempo total, calidad, costo estimado).
3. Implementar alertas minimas de falla de calidad/publicacion.

Criterios de aceptacion:
1. Integrador externo puede consumir la API sin conocer detalles internos.
2. Hay trazabilidad completa por correlation_id.

## 7. Contrato De Salida Recomendado
Ejemplo de respuesta estandar de generacion:

```json
{
  "status": "success",
  "correlation_id": "uuid",
  "article": {
    "title": "string",
    "excerpt": "string",
    "content": "string",
    "category": "string",
    "seo_metadata": {
      "slug": "string",
      "meta_description": "string",
      "image_alt_text": "string"
    }
  },
  "validation": {
    "depth_score": 82,
    "fact_check": "PASS",
    "policy": "PASS"
  },
  "timings": {
    "selection_ms": 100,
    "generation_ms": 2200,
    "validation_ms": 480,
    "total_ms": 3200
  }
}
```

## 8. KPIs Del Producto De Articulos
1. Quality pass rate: porcentaje de articulos que pasan gates sin reintento manual.
2. Average depth score: promedio de profundidad editorial.
3. Publish success rate: porcentaje de publicaciones exitosas.
4. P95 latency: latencia p95 del flujo de generacion.
5. Cost per article: costo promedio por articulo generado.

## 9. Riesgos Y Mitigacion
1. Riesgo: degradacion de calidad en migracion.
Mitigacion: rollout gradual con feature flag y fallback.

2. Riesgo: aumento de latencia por mas controles.
Mitigacion: cache de contexto + limites por etapa + timeouts.

3. Riesgo: acoplamiento con proveedores externos.
Mitigacion: adaptadores e interfaces para reemplazo rapido.

## 10. Definition Of Done (Release Comercial)
1. El endpoint de texto usa por defecto el motor modular nuevo.
2. Existe fallback operativo al flujo legacy.
3. Se registran correlation_id, timings y score por ejecucion.
4. Existen perfiles editoriales por cliente con configuracion aislada.
5. El contrato API de generacion esta documentado y estable.

## 11. Proximo Paso Inmediato
Ejecutar Sprint 1 y abrir PR con:
1. ArticleGenerationService.
2. Feature flag de enrutamiento.
3. Contrato de salida unificado.
4. Migracion del endpoint de texto al servicio nuevo.
