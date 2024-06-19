from crewai import Agent, Task, Crew, Process
import os
from langchain.chat_models import ChatOpenAI
from dotenv import load_dotenv

load_dotenv()

openai_api_key = os.getenv("OPENAI_API_KEY")

# Start the process with the crew, taking the input message
def iterate_agents(message):
    llm = ChatOpenAI(model_name="gpt-4o", temperature=0, openai_api_key=openai_api_key)

    GOAL_PERFECTION = "Perfeccionar los artículos escritos por el equipo de periodistas de Fin.Gurú"

    goals = {
        "asistente": f"Asistente de Redacción, ambos trabajamos en Fin.Gurú y compartimos un interés común en colaborar para completar con éxito una tarea asignada por un nuevo cliente. {GOAL_PERFECTION}",
        "marketing": f"Marketing y SEO, ambos trabajamos en Fin.Gurú y compartimos un interés común en colaborar para completar con éxito una tarea asignada por un nuevo cliente. {GOAL_PERFECTION}",
        "editor": f"Editor, ambos trabajamos en Fin.Gurú y compartimos un interés común en colaborar para completar con éxito una tarea asignada por un nuevo cliente. {GOAL_PERFECTION}",
        "director": "Realizar la evaluación final de los artículos para asegurar su calidad y coherencia con la reputación de Fin.Gurú. Si consideras que el artículo está listo para ser publicado, incluye la palabra 'TERMINATE' en tu respuesta.",
    }

    asistente = Agent(
        role="Asistente de Redacción",
        goal=goals.get("asistente"),
        backstory="Como un agente altamente capacitado en asistencia editorial, tu función esencial es perfeccionar los artículos escritos por nuestro equipo de periodistas de Fin.Gurú para que sean impecables tanto en estilo como en gramática. Posees un excelente dominio del idioma y una comprensión profunda de las normas editoriales, lo cual te permite pulir los textos para que fluyan de manera natural y sean de fácil lectura.",
        tools=[],
        llm=llm
    )

    marketing = Agent(
        role="Marketing y SEO",
        goal=goals.get("marketing"),
        backstory="Como especialista en Marketing y SEO en Fin.Gurú, posees conocimientos avanzados en técnicas de SEO (Search Engine Optimization) y tácticas de marketing digital para aumentar la visibilidad y el engagement del contenido en línea. Eres un estratega creativo en la construcción de titulares impactantes y contenido optimizado para motores de búsqueda, manteniendo siempre la integridad y relevancia del tema tratado.",
        tools=[],
        llm=llm
    )

    editor = Agent(
        role="Editor",
        goal=goals.get("editor"),
        backstory="Como el editor de Fin.Gurú, tienes la responsabilidad de supervisar el proceso editorial y garantizar la cohesión y coherencia de los artículos con la línea editorial de Fin.Guru. Con un agudo sentido de la calidad periodística y una sólida experiencia en la edición de contenidos para medios digitales, posees el criterio necesario para asegurar que cada artículo cumpla con los estándares del diario.",
        tools=[],
        llm=llm
    )

    director = Agent(
        role="Director",
        goal=goals.get("director"),
        backstory="Como Director de Fin.Gurú, tu rol es ejercer el máximo nivel de supervisión editorial asegurando que cada artículo no solo sea excelente en contenido y forma, sino que también respete y refuerce la reputación de Fin.Gurú como un medio de comunicación líder. Con una visión estratégica y un compromiso con la excelencia periodística, tu juicio determina la idoneidad final del contenido publicado.",
        tools=[],
        llm=llm,
    )

    # Define the tasks for each agent

    marketing_task = Task(
        description=f"{goals.get('marketing')} El artículo debe tratar sobre {message}",
        expected_output=f"Optimizar los artículos para motores de búsqueda y engagement del público objetivo, asegurando la relevancia y calidad del contenido. Devolver el artículo, y asegurar que trate sobre: {message}",
        tools=[],
        agent=marketing,
        async_execution=False,
    )

    editor_task = Task(
        description=f"{goals.get('editor')} El artículo debe tratar sobre {message}",
        expected_output=f"Garantizar la cohesión y coherencia de los artículos con la línea editorial de Fin.Gurú y devolver el artículo optimizado asegurando que lo modificado o redactado sea sobre esto: {message} y debe estar en formato HTML de solo lo que va dentro del body",
        tools=[],
        agent=editor,
        async_execution=False,
    )

    writer_task = Task(
        description=f"{goals.get('asistente')} Redacta un borrador de artículo sobre esto: {message}",
        expected_output=f"Un artículo perfectamente escrito y pulido, listo para ser revisado por el editor, tiene que tratar sobre {message} y el articulo debe estar en formato HTML de solo lo que va dentro del body",
        tools=[],
        agent=asistente,
        async_execution=False,
    )

    director_task = Task(
        description=f"{goals.get('director')} Revisar y evaluar el artículo sobre {message}",
        expected_output="Determinar si el artículo está listo para ser publicado o si necesita ajustes adicionales, y devolver el articulo ya terminado en formato HTML de solo lo que va dentro del body",
        tools=[],
        agent=director,
        async_execution=False,
    )

    # Forming the tech-focused crew with some enhanced configurations
    crew = Crew(
        agents=[asistente, marketing, editor, director],
        tasks=[marketing_task, editor_task, writer_task, director_task],
        process=Process.sequential,
        memory=True,
        cache=True,
        max_rpm=100,
        share_crew=True,
    )

    result = crew.kickoff(inputs={'message': message})
    print(result)
    return result

