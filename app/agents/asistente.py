from agents.config import llm
from crewai import Agent, Task

def get_asistente_agent(message):
    goal = f"Asistente de Redacción, ambos trabajamos en Fin.Gurú y compartimos un interés común en colaborar para completar con éxito una tarea asignada por un nuevo cliente. Perfeccionar los artículos escritos por el equipo de periodistas de Fin.Gurú. Redacta un borrador de artículo sobre esto: {message}, debe estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español, o si está en inglés en ingles"
    backstory = "Como un agente altamente capacitado en asistencia editorial, tu función esencial es perfeccionar los artículos escritos por nuestro equipo de periodistas de Fin.Gurú para que sean impecables tanto en estilo como en gramática. Posees un excelente dominio del idioma y una comprensión profunda de las normas editoriales, lo cual te permite pulir los textos para que fluyan de manera natural y sean de fácil lectura."

    return Agent(
        role="Asistente de Redacción",
        goal=goal,
        backstory=backstory,
        tools=[],
        llm=llm
    )
    

def get_asistente_task(message):
    goal = "Colaborar para completar con éxito una tarea asignada por un nuevo cliente. Perfeccionar los artículos escritos por el equipo de periodistas de Fin.Gurú."
    description = f"{goal} El artículo debe tratar sobre {message} y estar en el mismo lenguaje del mensaje, si el mensaje está en español devolver el resultado en español, o si está en inglés en ingles"
    expected_output = f"Garantizar la cohesión y coherencia de los artículos con la línea editorial de Fin.Gurú y devolver el artículo optimizado asegurando que lo modificado o redactado sea sobre esto: {message} y debe estar en formato HTML de SOLO lo que va dentro del body, sin head, ni html, ni body tags, ni footer. Además debe estar en el mismo lenguaje del mensaje"
    agent = get_asistente_agent(message)

    return Task(
        description=description,
        expected_output=expected_output,
        tools=[],
        agent=agent,
        async_execution=False,
    )