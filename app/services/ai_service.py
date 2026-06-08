import logging
import json
from typing import Any, Optional
import openai
from groq import AsyncGroq
from google import genai
from google.genai import types
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.settings = get_settings()
        self.openai_client = None
        self.groq_client = None
        self.gemini_client = None
        self._setup_clients()

    def _setup_clients(self):
        if self.settings.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)
        
        if self.settings.groq_api_key:
            self.groq_client = AsyncGroq(api_key=self.settings.groq_api_key)
        
        if self.settings.gemini_api_key:
            self.gemini_client = genai.Client(api_key=self.settings.gemini_api_key)

    async def chat_completion(self, prompt: str, system_prompt: str = None, response_format: str = "text", timeout: int = 30) -> Optional[str]:
        """
        Executes a chat completion with fallback: OpenAI -> Groq -> Gemini
        Includes timeout protection to prevent hanging.
        """
        import asyncio
        
        # 1. Try OpenAI
        if self.openai_client:
            try:
                logger.info("Attempting AI completion via OpenAI...")
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                extra_args = {}
                if response_format == "json_object":
                    extra_args["response_format"] = {"type": "json_object"}

                response = await asyncio.wait_for(
                    self.openai_client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=messages,
                        temperature=0.8,
                        **extra_args
                    ),
                    timeout=timeout
                )
                return response.choices[0].message.content.strip()
            except asyncio.TimeoutError:
                logger.warning(f"OpenAI timeout after {timeout}s")
            except Exception as e:
                logger.error(f"OpenAI completion failed: {e}")

        # 2. Fallback to Groq
        if self.groq_client:
            try:
                logger.info("Attempting AI completion via Groq...")
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                extra_args = {}
                if response_format == "json_object":
                    extra_args["response_format"] = {"type": "json_object"}

                response = await asyncio.wait_for(
                    self.groq_client.chat.completions.create(
                        model="llama-3.3-70b-versatile",
                        messages=messages,
                        temperature=0.8,
                        **extra_args
                    ),
                    timeout=timeout
                )
                return response.choices[0].message.content.strip()
            except asyncio.TimeoutError:
                logger.warning(f"Groq timeout after {timeout}s")
            except Exception as e:
                logger.error(f"Groq completion failed: {e}")

        # 3. Fallback to Gemini
        if self.gemini_client:
            try:
                logger.info("Attempting AI completion via Gemini...")
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\nUser: {prompt}"
                
                generation_config = types.GenerateContentConfig(
                    temperature=0.8,
                    response_mime_type="application/json" if response_format == "json_object" else None,
                )

                response = await asyncio.wait_for(
                    self.gemini_client.aio.models.generate_content(
                        model="gemini-1.5-flash",
                        contents=full_prompt,
                        config=generation_config,
                    ),
                    timeout=timeout
                )
                return (response.text or "").strip()
            except asyncio.TimeoutError:
                logger.warning(f"Gemini timeout after {timeout}s")
            except Exception as e:
                logger.error(f"Gemini completion failed: {e}")

        logger.error("All AI providers failed or no API keys provided.")
        return None

ai_service = AIService()
