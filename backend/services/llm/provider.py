import json
import logging
import inspect
from typing import List, Dict, Any, Optional
from google import genai
from google.genai import types as genai_types
from openai import AsyncOpenAI
from core.config import settings

logger = logging.getLogger(__name__)

class LLMResponse:
    def __init__(self, content: str, tool_calls: Optional[List[Dict]] = None):
        self.content = content
        self.tool_calls = tool_calls or []

class LLMProvider:
    def __init__(self):
        self.primary_provider = settings.LLM_PROVIDER_PRIMARY
        self.fallback_provider = settings.LLM_PROVIDER_FALLBACK
        
        self.gemini_client = None
        if settings.GEMINI_API_KEY:
            self.gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)
            
        self.groq_client = None
        if settings.GROQ_API_KEY:
            self.groq_client = AsyncOpenAI(
                api_key=settings.GROQ_API_KEY,
                base_url="https://api.groq.com/openai/v1"
            )

        self.ollama_client = None
        if hasattr(settings, 'OLLAMA_BASE_URL') and settings.OLLAMA_BASE_URL:
            self.ollama_client = AsyncOpenAI(
                api_key="ollama",
                base_url=settings.OLLAMA_BASE_URL
            )

    async def generate(self, system_prompt: str, messages: List[Dict[str, str]], tools: Optional[List[Any]] = None, response_schema: Optional[Any] = None) -> LLMResponse:
        """
        Attempts to generate response using primary provider, falls back if rate limited or fails.
        """
        try:
            if self.primary_provider == "ollama" and self.ollama_client:
                return await self._generate_ollama(system_prompt, messages, tools, response_schema)
            elif self.primary_provider == "gemini" and self.gemini_client:
                return await self._generate_gemini(system_prompt, messages, tools, response_schema)
            elif self.primary_provider in ["groq", "openai"] and self.groq_client:
                return await self._generate_groq(system_prompt, messages, tools, response_schema)
            else:
                raise ValueError(f"Primary provider {self.primary_provider} not configured.")
        except Exception as e:
            logger.warning(f"Primary provider failed, falling back to {self.fallback_provider}. Error: {e}")
            if self.fallback_provider in ["groq", "openai"] and self.groq_client:
                return await self._generate_groq(system_prompt, messages, tools, response_schema)
            elif self.fallback_provider == "gemini" and self.gemini_client:
                return await self._generate_gemini(system_prompt, messages, tools, response_schema)
            elif self.fallback_provider == "ollama" and self.ollama_client:
                return await self._generate_ollama(system_prompt, messages, tools, response_schema)
            else:
                raise e

    async def _generate_gemini(self, system_prompt: str, messages: List[Dict[str, str]], tools: Optional[List[Any]] = None, response_schema: Optional[Any] = None) -> LLMResponse:
        contents = []
        for msg in messages:
            # We map standard 'user'/'assistant' to Gemini 'user'/'model'
            role = "user" if msg["role"] == "user" else "model"
            contents.append(genai_types.Content(role=role, parts=[genai_types.Part.from_text(msg["content"])]))
            
        config = genai_types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=0.2,
        )
        
        if tools:
            # Not fully implementing function calling translation here yet, but standardizing the interface
            # The google-genai SDK takes python callables directly in the config.tools
            config.tools = tools
            
        if response_schema:
            config.response_mime_type = "application/json"
            config.response_schema = response_schema
            
        # Using async generation (requires async client or wrap in thread)
        # Note: google-genai has an aio client for async operations. 
        # Using it directly for this example:
        response = await self.gemini_client.aio.models.generate_content(
            model='gemini-2.5-flash',
            contents=contents,
            config=config
        )
        
        # Check for tool calls
        tool_calls = []
        if response.function_calls:
            for fc in response.function_calls:
                tool_calls.append({
                    "name": fc.name,
                    "arguments": fc.args
                })
                
        return LLMResponse(content=response.text or "", tool_calls=tool_calls)

    async def _generate_groq(self, system_prompt: str, messages: List[Dict[str, str]], tools: Optional[List[Any]] = None, response_schema: Optional[Any] = None) -> LLMResponse:
        oai_messages = [{"role": "system", "content": system_prompt}] + messages
        
        # We need to map python callables to OpenAI tool definitions
        oai_tools = []
        if tools:
            for tool in tools:
                sig = inspect.signature(tool)
                parameters = {"type": "object", "properties": {}, "required": []}
                for name, param in sig.parameters.items():
                    parameters["properties"][name] = {"type": "string"}
                    if param.default == inspect.Parameter.empty:
                        parameters["required"].append(name)
                oai_tools.append({
                    "type": "function",
                    "function": {
                        "name": tool.__name__,
                        "description": tool.__doc__ or f"Tool {tool.__name__}",
                        "parameters": parameters
                    }
                })

        kwargs = {
            "model": "llama-3.3-70b-versatile",
            "messages": oai_messages,
            "temperature": 0.2
        }
        
        if oai_tools:
            kwargs["tools"] = oai_tools
            kwargs["tool_choice"] = "auto"
        
        if response_schema:
            kwargs["response_format"] = {"type": "json_object"}
            
        response = await self.groq_client.chat.completions.create(**kwargs)
        
        message = response.choices[0].message
        content = message.content or ""
        
        tool_calls = []
        if message.tool_calls:
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments)
                except:
                    args = tc.function.arguments
                tool_calls.append({
                    "name": tc.function.name,
                    "arguments": args
                })
        
        return LLMResponse(content=content, tool_calls=tool_calls)

    async def _generate_ollama(self, system_prompt: str, messages: List[Dict[str, str]], tools: Optional[List[Any]] = None, response_schema: Optional[Any] = None) -> LLMResponse:
        oai_messages = [{"role": "system", "content": system_prompt}] + messages
        
        kwargs = {
            "model": getattr(settings, 'OLLAMA_MODEL', 'qwen:4b'),
            "messages": oai_messages,
            "temperature": 0.2
        }
        
        if response_schema:
            kwargs["response_format"] = {"type": "json_object"}
            
        response = await self.ollama_client.chat.completions.create(**kwargs)
        message = response.choices[0].message
        return LLMResponse(content=message.content or "")

llm_provider = LLMProvider()
