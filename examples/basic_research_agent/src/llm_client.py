"""LLM client for the research agent."""

import json
import os

import aiohttp
from dotenv import load_dotenv

from .models import FinalAnswer, ToolCall

load_dotenv(override=True)
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openrouter").lower()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")


async def call_llm(system: str, user: str) -> str:
    """Call the selected LLM provider (OpenAI or OpenRouter) with the given system and user prompts."""
    if LLM_PROVIDER == "openrouter":
        return await call_openrouter(system, user)
    else:
        return await call_openai(system, user)


async def call_openai(system: str, user: str) -> str:
    """Call OpenAI's API asynchronously."""
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    response = await client.chat.completions.create(
        model="gpt-4-turbo-preview",
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        tools=[
            {
                "type": "function",
                "function": {
                    "name": "ToolCall",
                    "description": "Call a tool with arguments",
                    "parameters": ToolCall.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "FinalAnswer",
                    "description": "Return a final answer",
                    "parameters": FinalAnswer.model_json_schema(),
                },
            },
        ],
        tool_choice="auto",
    )
    message = response.choices[0].message
    if message.tool_calls:
        # Handle tool call
        tool_call = message.tool_calls[0]
        args = json.loads(tool_call.function.arguments)
        return json.dumps(args)
    return message.content


async def call_openrouter(system: str, user: str) -> str:
    """Call OpenRouter's API asynchronously."""
    if not OPENROUTER_API_KEY:
        raise ValueError("OPENROUTER_API_KEY not set")

    url = "https://openrouter.ai/api/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "http://localhost:5001",
        "X-Title": "WorkflowGraphAgent",
    }
    data = {
        "model": "openai/gpt-4-turbo-preview",
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
        "tools": [
            {
                "type": "function",
                "function": {
                    "name": "ToolCall",
                    "description": "Call a tool with arguments",
                    "parameters": ToolCall.model_json_schema(),
                },
            },
            {
                "type": "function",
                "function": {
                    "name": "FinalAnswer",
                    "description": "Return a final answer",
                    "parameters": FinalAnswer.model_json_schema(),
                },
            },
        ],
        "tool_choice": "auto",
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(url, headers=headers, json=data) as response:
            response.raise_for_status()
            result = await response.json()
            message = result["choices"][0]["message"]
            if "tool_calls" in message:
                # Handle tool call
                tool_call = message["tool_calls"][0]
                args = json.loads(tool_call["function"]["arguments"])
                return json.dumps(args)
            return message["content"]
