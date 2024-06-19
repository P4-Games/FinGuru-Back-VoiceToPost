from agents.config import llm
from crewai import Agent, Task

def get_director_agent(message):
    goal = f"Realizar la evaluación final de los artículos para asegurar su calidad y coherencia con la reputación de Fin.Gurú. Si consideras que el artículo está listo para ser publicado, incluye la palabra 'TERMINAR' en tu respuesta. Revisar y evaluar el artículo sobre {message} y estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español, o si está en inglés en ingles"
    backstory = "Como Director de Fin.Gurú, tu rol es ejercer el máximo nivel de supervisión editorial asegurando que cada artículo no solo sea excelente en contenido y forma, sino que también respete y refuerce la reputación de Fin.Gurú como un medio de comunicación líder. Con una visión estratégica y un compromiso con la excelencia periodística, tu juicio determina la idoneidad final del contenido publicado."

    return Agent(
        role="Director",
        goal=goal,
        backstory=backstory,
        tools=[],
        llm=llm
    )
    
def get_director_task(message):
    goal = "Asegurar la calidad y coherencia del articulo con la reputación de Fin.Gurú."
    description = f"{goal} Revisar y evaluar el artículo sobre {message} y estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español, o si está en inglés en ingles"
    expected_output = "Determinar si el artículo está listo para ser publicado o si necesita ajustes adicionales, y devolver el artículo ya terminado en formato HTML de SOLO lo que va dentro del body, sin head, ni html, ni body tags, ni footer. Además debe estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español"
    agent = get_director_agent(message)

    return Task(
        description=description,
        expected_output=expected_output,
        tools=[],
        agent=agent,
        async_execution=False,
    )