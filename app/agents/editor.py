from agents.config import llm
from crewai import Agent, Task

def get_editor_agent(message):
    goal = f"Editor, ambos trabajamos en Fin.Gurú y compartimos un interés común en colaborar para completar con éxito una tarea asignada por un nuevo cliente. Perfeccionar los artículos escritos por el equipo de periodistas de Fin.Gurú. El artículo debe tratar sobre {message}, de al menos varios párrafos, y estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español, o si está en inglés en ingles"
    backstory = "Como el editor de Fin.Gurú, tienes la responsabilidad de supervisar el proceso editorial y garantizar la cohesión y coherencia de los artículos con la línea editorial de Fin.Guru. Con un agudo sentido de la calidad periodística y una sólida experiencia en la edición de contenidos para medios digitales, posees el criterio necesario para asegurar que cada artículo cumpla con los estándares del diario."

    return Agent(
        role="Editor",
        goal=goal,
        backstory=backstory,
        tools=[],
        llm=llm
    )
    
def get_editor_task(message):
    goal = "Perfeccionar los artículos escritos por el equipo de periodistas de Fin.Gurú."
    description = f"{goal} El artículo debe tratar sobre {message} y estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español, o si está en inglés en ingles"
    expected_output = f"Garantizar la cohesión y coherencia de los artículos con la línea editorial de Fin.Gurú y devolver el artículo optimizado asegurando que lo modificado o redactado sea sobre esto: {message} y debe estar en formato HTML de SOLO lo que va dentro del body, sin head, ni html, ni body tags, ni footer. Además debe estar en el mismo lenguaje del mensaje"
    agent = get_editor_agent(message)

    return Task(
        description=description,
        expected_output=expected_output,
        tools=[],
        agent=agent,
        async_execution=False,
    )