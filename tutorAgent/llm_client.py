"""Reuse the team's shared local Ollama runtime."""
from llm.ollama import OllamaClient

def create_llm_client():
    return OllamaClient()
