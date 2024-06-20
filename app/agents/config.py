import os
from langchain.chat_models import ChatOpenAI
from load_env import load_env_files

load_env_files()

openai_api_key = os.getenv("OPENAI_API_KEY")
llm = ChatOpenAI(model_name="gpt-3.5-turbo-1106", temperature=0, openai_api_key=openai_api_key)