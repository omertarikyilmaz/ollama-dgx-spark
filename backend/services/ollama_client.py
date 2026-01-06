"""
Ollama API Client with KV Cache optimization
"""
import httpx
import time
import json
from typing import Dict, Any, Optional
import os


class OllamaClient:
    def __init__(self, base_url: str = None):
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.client = httpx.AsyncClient(timeout=300.0)  # 5 min timeout for large models
    
    async def generate(
        self,
        model: str,
        prompt: str,
        system_prompt: str,
        json_schema: Dict[str, Any],
        keep_alive: str = "10m",
        num_ctx: int = 4096,
        temperature: float = 0.0
    ) -> Dict[str, Any]:
        """
        Generate a response with JSON structured output.
        Uses Ollama's format parameter for guaranteed JSON structure.
        """
        start_time = time.time()
        
        # Build the JSON schema for structured output
        format_schema = {
            "type": "object",
            "properties": {},
            "required": list(json_schema.keys())
        }
        
        for field_name, field_config in json_schema.items():
            prop = {
                "type": field_config.get("type", "string"),
                "description": field_config.get("description", "")
            }
            if "enum" in field_config:
                prop["enum"] = field_config["enum"]
            format_schema["properties"][field_name] = prop
        
        # Prepared prompt with explicit JSON instruction
        full_prompt = f"{system_prompt}\n\nHaber metni:\n{prompt}\n\nYukarıdaki haberi analiz et ve JSON formatında yanıt ver."
        
        payload = {
            "model": model,
            "prompt": full_prompt,
            "format": format_schema,
            "stream": False,
            "options": {
                "temperature": temperature,
                "num_ctx": num_ctx
            },
            "keep_alive": keep_alive
        }
        
        response = await self.client.post(
            f"{self.base_url}/api/generate",
            json=payload
        )
        response.raise_for_status()
        
        result = response.json()
        end_time = time.time()
        
        # Parse the JSON response
        try:
            parsed_result = json.loads(result.get("response", "{}"))
        except json.JSONDecodeError:
            parsed_result = {"raw_response": result.get("response", "")}
        
        # Calculate metrics
        total_duration_ms = (end_time - start_time) * 1000
        eval_count = result.get("eval_count", 0)
        eval_duration_ns = result.get("eval_duration", 1)
        tokens_per_second = (eval_count / eval_duration_ns) * 1e9 if eval_duration_ns > 0 else 0
        
        return {
            "result": parsed_result,
            "response_time_ms": total_duration_ms,
            "tokens_per_second": tokens_per_second,
            "prompt_eval_count": result.get("prompt_eval_count", 0),
            "eval_count": eval_count
        }
    
    async def list_models(self) -> Dict[str, Any]:
        """List available models"""
        response = await self.client.get(f"{self.base_url}/api/tags")
        response.raise_for_status()
        return response.json()
    
    async def pull_model(self, model: str) -> bool:
        """Pull a model from Ollama registry"""
        response = await self.client.post(
            f"{self.base_url}/api/pull",
            json={"name": model},
            timeout=3600.0  # 1 hour for large models
        )
        return response.status_code == 200
    
    async def health_check(self) -> bool:
        """Check if Ollama is healthy"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self):
        await self.client.aclose()


# Singleton instance
_client: Optional[OllamaClient] = None


def get_ollama_client() -> OllamaClient:
    global _client
    if _client is None:
        _client = OllamaClient()
    return _client
