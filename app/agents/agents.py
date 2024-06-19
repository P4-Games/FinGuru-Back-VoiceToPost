from crewai import Agent, Task, Crew, Process
import os
from langchain.chat_models import ChatOpenAI
from dotenv import load_dotenv
from agents.asistente import get_asistente_agent,get_asistente_task
from agents.marketing import get_marketing_agent,get_marketing_task
from agents.editor import get_editor_agent,get_editor_task
from agents.director import get_director_agent,get_director_task

load_dotenv('.env.local')

openai_api_key = os.getenv("OPENAI_API_KEY")

# Start the process with the crew, taking the input message
def iterate_agents(message):
    asistente = get_asistente_agent(message)
    marketing = get_marketing_agent(message)
    editor = get_editor_agent(message)
    director = get_director_agent(message)
    
    marketing_task = get_marketing_task(message)
    editor_task = get_editor_task(message)
    writer_task = get_asistente_task(message)
    director_task = get_director_task(message)

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

