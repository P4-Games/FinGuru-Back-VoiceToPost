import openai
import json

openai.api_key = "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"

def chat_gpt(message,rol):
    prompt = f"Tu eres:{rol}. Y este es el articulo con el cual tienes que trabajar: {message}"
    response = openai.Completion.create(
        engine="gpt-3.5-turbo-instruct",
        prompt=prompt,
        max_tokens=1024,
        n=1,
        stop=None,
        temperature=0.2,
    )
    message = response.choices[0].text.strip()
    return message

from prompts import *

def iterate_many_times(message, times):
    new_message = message
    agents = [asistente, marketing, editor, director]
    for i in range(times):
        for agent in agents:
            new_message = chat_gpt(new_message, agent)

            print(new_message)
    
    return new_message


print(iterate_many_times("Hubo un choque en callao y santa fe, creo que el conductor estaba ebrio, no hubo muertos", 3))