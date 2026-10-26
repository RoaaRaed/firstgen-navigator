import os
from dotenv import load_dotenv
from langchain_groq import ChatGroq

load_dotenv()  # reads the .env file into environment variables

api_key = os.getenv("GROQ_API_KEY")
model_name = os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile")

if not api_key:
    raise SystemExit("GROQ_API_KEY is missing. Check your .env file.")

llm = ChatGroq(model=model_name, api_key=api_key, temperature=0, max_tokens=1000)

response = llm.invoke("In one sentence, what is the FAFSA?")
print(response.content)