from agents.config import llm
from crewai import Agent, Task

def get_marketing_agent(message):
    goal = f"Perfeccionar los artículos escritos por el equipo de periodistas de Fin.Gurú. El artículo debe tratar sobre {message} y estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español, o si está en inglés en ingles"
    backstory = "Como especialista en Marketing y SEO en Fin.Gurú, posees conocimientos avanzados en técnicas de SEO (Search Engine Optimization) y tácticas de marketing digital para aumentar la visibilidad y el engagement del contenido en línea. Eres un estratega creativo en la construcción de titulares impactantes y contenido optimizado para motores de búsqueda, manteniendo siempre la integridad y relevancia del tema tratado."

    return Agent(
        role="Marketing y SEO",
        goal=goal,
        backstory=backstory,
        tools=[],
        llm=llm
    )
    
def get_marketing_task(message):
    goal = "Perfeccionar los artículos escritos por el equipo de periodistas de Fin.Gurú."
    description = f"{goal} El artículo debe tratar sobre {message} y estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español, o si está en inglés en ingles"
    expected_output = f"Optimizar los artículos para motores de búsqueda y engagement del público objetivo, asegurando la relevancia y calidad del contenido. Devolver el artículo, y asegurar que trate sobre: {message} y debe estar en el mismo lenguaje del mensaje"
    agent = get_marketing_agent(message)

    return Task(
        description=description,
        expected_output=expected_output,
        tools=[],
        agent=agent,
        async_execution=False,
    )