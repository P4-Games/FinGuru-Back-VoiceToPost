from autogen import AssistantAgent, UserProxyAgent
import autogen

config_list_gpt4 = [{
    "model": "gpt-4",
    "api_key": "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"
}
]

gpt4_config = {
    "seed": 42,  # change the seed for different trials
    "temperature": 0,
    "config_list": config_list_gpt4,
    "request_timeout": 120,
}

#screen_writer = autogen.UserProxyAgent(
#    name="periodista",
#    system_message="es el periodista humano. escribe la nota y puede agregar algun contenido.",
#    code_execution_config=False,
#)

periodista = autogen.AssistantAgent(
    name="periodista",
    llm_config=gpt4_config,
    system_message="rol: Periodista. se encarga de subir solamente la nota, no interactua mas",
)

asitente = autogen.AssistantAgent(
    name="asitente",
    llm_config=gpt4_config,
    system_message="rol: asistente. se encarga de corregir el texto, mejorarlo gramaticamente y buscar referencias los temas. encargate de aplicar tu rol en la nota, solo entrega la nota",
)

marketing = autogen.AssistantAgent(
    name="marketing",
    llm_config=gpt4_config,
    system_message="rol: Marketing se encarga de aplicar técnicas de SEO (Search Engine Optimization) y tácticas de marketing digital para aumentar la visibilidad y el engagement del contenido en línea. encargate de aplicar tu rol en la nota, solo entrega la nota"
,
)

editor = autogen.AssistantAgent(
    name="editor",
    llm_config=gpt4_config,
    system_message="rol: Editor, es un editor del diario infobae, se encarga de que la nota este escrita y tengo los mismos lineamientos que otras notas del mismo diario. encargate de aplicar tu rol en la nota, solo entrega la nota"
)

director = autogen.AssistantAgent(
    name="director",
    #system_message="director. se encarga de verificar que la nota tenga un nivel de calidad adecuado para un diario como infobae, si falta algo lo enviaria nuevamente al editor o al asistente para que se lo vuelvan a enviar. escribir TERMINATE al final de todo si cree que todo el trabajo esta listo",
    system_message="rol: Director. se encarga de aprobar el articulo y  de verificar que la nota tenga un nivel de calidad adecuado para un diario como infobae y que tenga un nivel de nota muy alto, no te conformas con poco, si falta algo pedir que lo arreglen.",
    llm_config=gpt4_config,
    #is_termination_msg=lambda x: True if "TERMINATE" in x.get("content") else False,
)

""" redactor = autogen.AssistantAgent(
    name="redactor",
    system_message="redactor. se encarga de publicar solo la nota, no debe tener texto adicional. escribir TERMINATE al final de todo si cree que todo el trabajo esta listo",
    llm_config=gpt4_config,
    is_termination_msg=lambda x: True if "TERMINATE" in x.get("content") else False,
) """

groupchat = autogen.GroupChat(agents=[
                              periodista, asitente, marketing, editor, director], messages=[], max_round=12)
manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=gpt4_config)

messagge35 = """
deberas coordinar el trabajo para generar un articulo de altisima calidad, recuerda que debe pasar por asistente, editor y marketing. el articulo es el siguiente: el dia de ayer, encontre en la esquina de callao y santa fe un choque terrible entre 2 autos, uno de ellos quedo arriba de la vereda y el otro era un taxi, los vecinos me contaron que el taxista se golpeo la cabesa en el momento del choque y lo llevaron al hospital. todabia estaban las franjas de la policia y se desconose si alguno de los involucrados estaba alcoholizado
"""
messagge4 = """
deberas coordinar el trabajo para generar un articulo de altisima calidad eligiendo los agentes que puedan mejorar mas el articulo el articulo es el siguiente: el dia de ayer, encontre en la esquina de callao y santa fe un choque terrible entre 2 autos, uno de ellos quedo arriba de la vereda y el otro era un taxi, los vecinos me contaron que el taxista se golpeo la cabesa en el momento del choque y lo llevaron al hospital. todabia estaban las franjas de la policia y se desconose si alguno de los involucrados estaba alcoholizado
"""



periodista.initiate_chat(
    manager,
    message=messagge4
)