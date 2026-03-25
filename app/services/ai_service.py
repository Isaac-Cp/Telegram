import logging
import json
from typing import Any, Optional
import openai
from groq import AsyncGroq
import google.generativeai as genai
from app.core.config import get_settings

logger = logging.getLogger(__name__)

class AIService:
    def __init__(self):
        self.settings = get_settings()
        self.openai_client = None
        self.groq_client = None
        self._setup_clients()

    def _setup_clients(self):
        if self.settings.openai_api_key:
            self.openai_client = openai.AsyncOpenAI(api_key=self.settings.openai_api_key)
        
        if self.settings.groq_api_key:
            self.groq_client = AsyncGroq(api_key=self.settings.groq_api_key)
        
        if self.settings.gemini_api_key:
            genai.configure(api_key=self.settings.gemini_api_key)

    async def chat_completion(self, prompt: str, system_prompt: str = None, response_format: str = "text") -> Optional[str]:
        """
        Executes a chat completion with fallback: OpenAI -> Groq -> Gemini
        """
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

                response = await self.openai_client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=messages,
                    temperature=0.0,
                    **extra_args
                )
                return response.choices[0].message.content.strip()
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

                response = await self.groq_client.chat.completions.create(
                    model="llama-3.3-70b-versatile",
                    messages=messages,
                    temperature=0.0,
                    **extra_args
                )
                return response.choices[0].message.content.strip()
            except Exception as e:
                logger.error(f"Groq completion failed: {e}")

        # 3. Fallback to Gemini
        if self.settings.gemini_api_key:
            try:
                logger.info("Attempting AI completion via Gemini...")
                model = genai.GenerativeModel('gemini-1.5-flash')
                full_prompt = prompt
                if system_prompt:
                    full_prompt = f"{system_prompt}\n\nUser: {prompt}"
                
                generation_config = {}
                if response_format == "json_object":
                    generation_config["response_mime_type"] = "application/json"

                response = model.generate_content(
                    full_prompt,
                    generation_config=genai.types.GenerationConfig(
                        temperature=0.0,
                        **generation_config
                    )
                )
                return response.text.strip()
            except Exception as e:
                logger.error(f"Gemini completion failed: {e}")

        logger.error("All AI providers failed or no API keys provided.")
        return None

ai_service = AIService()
