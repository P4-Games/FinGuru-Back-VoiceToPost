from openai import OpenAI
import json
from os import getenv
from load_env import load_env_files

load_env_files()
openai = OpenAI(
  api_key=getenv("OPENAI_API_KEY")
)

def chat_gpt(message,rol):
    prompt = f"Tu eres:{rol}. Y este es el articulo con el cual tienes que trabajar: {message}"
    response = openai.chat.completions.create(
        engine="gpt-4o-mini",
        prompt=prompt,
        max_tokens=1024,
        n=1,
        stop=None,
        temperature=0.2,
    )
    message = response.choices[0].text.strip()
    return message

def chat(message, rol):
    print(getenv("OPENAI_API_KEY"))
    response = openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": rol},
            {"role": "user", "content": message}
        ],
        temperature=0.2,
        max_tokens=2000,
    )
    response = response["choices"][0]["message"]["content"]
    return response

from prompts import *

def iterate_many_times(message, times):
    new_message = message
    agents = [asistente, marketing, editor, director]
    for i in range(times):
        for agent in agents:
            print("------------prompt llegada----------------")
            print(agents.index(agent))
            print(new_message)
            new_message = chat(new_message, agent)
            print("prompt salida: ------------")
            print(new_message)
    
    return new_message

#print(iterate_many_times("Hubo un choque en callao y santa fe, creo que el conductor estaba ebrio, no hubo muertos, ni heridos", 1))