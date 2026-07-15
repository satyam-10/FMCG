"""
One LLM client, provider-agnostic.

Model and provider are read from the environment so the code does not hardcode a
version string that may go stale. Set LLM_MODEL and LLM_PROVIDER in .env.
Defaults target Anthropic; override for OpenAI or others without code changes.
"""

import os
from functools import lru_cache
from langchain_openai import ChatOpenAI


@lru_cache(maxsize=1)
def get_llm(temperature: float = 0.0):
    return ChatOpenAI(
        model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        temperature=temperature,
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        openai_api_base=os.getenv("OPENAI_BASE_URL", "https://aibe.mygreatlearning.com/openai/v1"),
    )