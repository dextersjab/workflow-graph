"""Tools for the research agent."""

import os
import re
from typing import Any, Dict, List

import aiohttp
from dotenv import load_dotenv

load_dotenv(override=True)
BRAVE_API_KEY = os.getenv("BRAVE_API_KEY")
HEADERS = {"User-Agent": "Researcher-WorkflowGraph/0.3"}


async def brave_search(query: str, k: int = 10) -> List[Dict[str, str]]:
    """Search the web using Brave Search API or DuckDuckGo fallback."""
    if BRAVE_API_KEY:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": query, "count": k},
                headers={
                    "Accept": "application/json",
                    "Accept-Encoding": "gzip",
                    "X-Subscription-Token": BRAVE_API_KEY,
                    **HEADERS,
                },
                timeout=15,
            ) as response:
                response.raise_for_status()
                data = await response.json()
                # Convert BraveSearch response format to match expected format
                results = []
                for result in data.get("web", {}).get("results", []):
                    results.append(
                        {
                            "title": result.get("title", ""),
                            "link": result.get("url", ""),
                            "snippet": result.get("description", ""),
                        }
                    )
                return results
    # public duckduckgo fallback
    async with aiohttp.ClientSession() as session:
        async with session.get(
            "https://ddg-webapp-search.vercel.app/search",
            params={"q": query, "k": k},
            headers=HEADERS,
            timeout=15,
        ) as response:
            response.raise_for_status()
            return await response.json()


async def fetch_page(url: str, limit: int = 6000) -> str:
    """Fetch and extract text from a webpage."""
    async with aiohttp.ClientSession() as session:
        async with session.get(url, headers=HEADERS, timeout=25) as response:
            response.raise_for_status()
            html = await response.text()
            html = re.sub(
                r"<script[\s\S]*?</script>|<style[\s\S]*?</style>",
                " ",
                html,
                flags=re.I,
            )
            text = re.sub(r"<[^>]+>", " ", html)
            text = re.sub(r"\s+", " ", text)
            return text[:limit]


# Tool registry
tools: Dict[str, Any] = {
    "search": brave_search,
    "fetch": fetch_page,
}
