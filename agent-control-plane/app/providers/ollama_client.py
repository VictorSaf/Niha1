import httpx

from app.config import settings


class OllamaClient:
    async def generate(self, model: str, prompt: str) -> str:
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=settings.ollama_timeout_seconds) as client:
            response = await client.post(f"{settings.ollama_base_url}/api/chat", json=payload)
            response.raise_for_status()
            data = response.json()

        message = data.get("message", {})
        return message.get("content", "")
