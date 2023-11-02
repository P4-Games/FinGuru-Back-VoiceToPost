from autogen import AssistantAgent, UserProxyAgent
import autogen

config_list_gpt4 = [{
    "model": "gpt-3.5-turbo",
    "api_key": ""
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
    system_message="periodista. se encarga de escribir la nota y agregar contenido o modificaciones",
)

asitente = autogen.AssistantAgent(
    name="asitente",
    llm_config=gpt4_config,
    system_message='''asistente. se encarga de mejorar el estilo de redaccion la gramaticalmente y buscar referencias los temas.
''',
)

editor = autogen.AssistantAgent(
    name="editor",
    llm_config=gpt4_config,
    system_message="editor. es un editor del diario infobae, se encarga de que la nota este escrita y tengo los mismos lineamientos que otras notas del mismo diario"
,
)
director = autogen.AssistantAgent(
    name="director",
    #system_message="director. se encarga de verificar que la nota tenga un nivel de calidad adecuado para un diario como infobae, si falta algo lo enviaria nuevamente al editor o al asistente para que se lo vuelvan a enviar. escribir TERMINATE al final de todo si cree que todo el trabajo esta listo",
    system_message="director. se encarga de verificar que la nota tenga un nivel de calidad adecuado para un diario como infobae, es el que se encarga de aprobar la nota.",
    llm_config=gpt4_config,
)
redactor = autogen.AssistantAgent(
    name="redactor",
    system_message="redactor. se encarga de publicar solo la nota, no debe tener texto adicional. escribir TERMINATE al final de todo si cree que todo el trabajo esta listo",
    llm_config=gpt4_config,
    is_termination_msg=lambda x: True if "TERMINATE" in x.get("content") else False,
)

groupchat = autogen.GroupChat(agents=[
                              periodista, asitente, editor, director,redactor], messages=[], max_round=12)
manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=gpt4_config)

periodista.initiate_chat(
    manager,
    message="""
el dia de ayer, encontre en la esquina de callao y santa fe un choque terrible entre 2 autos, uno de ellos quedo arriba de la vereda y el otro era un taxi, los vecinos me contaron que el taxista se golpeo la cabesa en el momento del choque y lo llevaron al hospital. todabia estaban las franjas de la policia y se desconose si alguno de los involucrados estaba alcoholizado
""",
)