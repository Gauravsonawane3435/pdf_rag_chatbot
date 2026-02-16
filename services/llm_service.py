from langchain_groq import ChatGroq
from langchain_openai import ChatOpenAI
from langchain_anthropic import ChatAnthropic
from langchain_cohere import ChatCohere
from flask import current_app
import os

class LLMService:
    @staticmethod
    def get_llm(provider="groq", model_name=None, temperature=0.7):
        if provider == "groq":
            model = model_name or "llama-3.3-70b-versatile"
            return ChatGroq(
                api_key=os.getenv("GROQ_API_KEY"),
                model_name=model,
                temperature=temperature
            )
        elif provider == "openai":
            model = model_name or "gpt-4-turbo"
            return ChatOpenAI(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name=model,
                temperature=temperature
            )
        elif provider == "anthropic":
            model = model_name or "claude-3-5-sonnet-20240620"
            return ChatAnthropic(
                api_key=os.getenv("ANTHROPIC_API_KEY"),
                model_name=model,
                temperature=temperature
            )
        elif provider == "cohere":
            model = model_name or "command-r-plus"
            return ChatCohere(
                api_key=os.getenv("COHERE_API_KEY"),
                model_name=model,
                temperature=temperature
            )
        else:
            # Fallback to Groq
            return ChatGroq(
                api_key=os.getenv("GROQ_API_KEY"),
                model_name="llama-3.3-70b-versatile",
                temperature=temperature
            )
