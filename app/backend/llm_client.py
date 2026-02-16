import os
import subprocess
import json
import logging
import httpx
import re
import time
from abc import ABC, abstractmethod
from typing import List, Dict, Optional, Any, Union
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Setup logging
logger = logging.getLogger(__name__)

class LLMClient(ABC):
    @abstractmethod
    def chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None, temperature: float = 0.7) -> str:
        """
        Send a chat request to the LLM.
        
        Args:
            messages: List of message dicts. Content can be str or list (for multimodal).
            model: Optional model override.
            temperature: Sampling temperature.
            
        Returns:
            The content of the response message.
        """
        pass

class GHCopilotCLIClient(LLMClient):
    """
    Wrapper for 'gh copilot' CLI.
    Best for high-context text tasks where Azure 8k limit is a problem.
    Does NOT support images/multimodal input effectively via this wrapper.
    """
    def chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None, temperature: float = 0.7) -> str:
        logger.info("Using GitHub Copilot CLI")
        
        # Check for multimodal content
        for msg in messages:
            if isinstance(msg.get("content"), list):
                logger.warning("GHCopilotCLIClient received multimodal input, which is likely not supported. Trying to extract text only.")
                text_content = []
                for item in msg["content"]:
                    if isinstance(item, dict) and item.get("type") == "text":
                        text_content.append(item.get("text", ""))
                    elif isinstance(item, str):
                        text_content.append(item)
                msg["content"] = "\n".join(text_content)

        # Flatten messages into a single prompt
        prompt_parts = []
        for msg in messages:
            role = msg.get("role", "")
            content = msg.get("content", "")
            if role == "system":
                prompt_parts.append(f"System: {content}")
            elif role == "user":
                prompt_parts.append(f"User: {content}")
            elif role == "assistant":
                prompt_parts.append(f"Assistant: {content}")
        
        full_prompt = "\n\n".join(prompt_parts)
        
        # Command based on summarize.py implementation
        # usage: gh copilot -- -p "prompt" -s --allow-all-tools
        cmd = [
            "gh", "copilot", "--",
            "-p", full_prompt,
            "-s", # silent mode (only output)
            "--allow-all-tools" # allow file access if needed
        ]
        
        try:
            logger.debug(f"Calling gh copilot with prompt length: {len(full_prompt)}")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)
            
            if result.returncode != 0:
                raise RuntimeError(f"gh copilot failed: {result.stderr}")
                
            raw = result.stdout.strip()
            
            # Clean up markdown code blocks if present
            if "```" in raw:
                # Remove starting block
                raw = re.sub(r"^```[a-zA-Z0-9]*\n?", "", raw)
                # Remove ending block
                raw = raw.replace("```", "").strip()
                
            return raw
            
        except subprocess.TimeoutExpired:
            raise RuntimeError("gh copilot timed out")
        except Exception as e:
            raise RuntimeError(f"gh copilot error: {e}")

class AzureInferenceClient(LLMClient):
    def __init__(self):
        try:
            from azure.ai.inference import ChatCompletionsClient
            from azure.core.credentials import AzureKeyCredential
            
            # Try to get token from multiple sources
            token = os.getenv("GITHUB_TOKEN") or os.getenv("COPILOT_TOKEN")
            if not token:
                # Try gh auth token
                try:
                    res = subprocess.run(["gh", "auth", "token"], capture_output=True, text=True)
                    if res.returncode == 0:
                        token = res.stdout.strip()
                except:
                    pass
            
            endpoint = os.getenv("AZURE_INFERENCE_ENDPOINT", "https://models.inference.ai.azure.com").strip()
            if not endpoint.startswith(("http://", "https://")):
                endpoint = f"https://{endpoint}"
            if endpoint.startswith("http://"):
                logger.warning("AZURE_INFERENCE_ENDPOINT used http://; forcing https:// for TLS compatibility")
                endpoint = "https://" + endpoint[len("http://"):]
            
            if not token:
                # Log warning but don't fail init, fail on chat
                self.client = None
                logger.warning("GITHUB_TOKEN/COPILOT_TOKEN not found for AzureInferenceClient")
            else:
                self.client = ChatCompletionsClient(
                    endpoint=endpoint,
                    credential=AzureKeyCredential(token),
                )
        except ImportError:
            logger.error("azure-ai-inference not installed")
            self.client = None

    def _convert_to_azure_messages(self, messages: List[Dict[str, Any]]) -> List[Any]:
        from azure.ai.inference.models import SystemMessage, UserMessage, AssistantMessage, TextContentItem, ImageContentItem, ImageUrl
        
        azure_msgs = []
        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            
            if role == "system":
                azure_msgs.append(SystemMessage(content=content))
            elif role == "user":
                if isinstance(content, list):
                    items = []
                    for item in content:
                        if isinstance(item, dict):
                            if item.get("type") == "text":
                                items.append(TextContentItem(text=item["text"]))
                            elif item.get("type") == "image_url":
                                items.append(ImageContentItem(image_url=ImageUrl(url=item["image_url"]["url"])))
                        else:
                            # Fallback if mixed string/dict
                            items.append(TextContentItem(text=str(item)))
                    azure_msgs.append(UserMessage(content=items))
                else:
                    azure_msgs.append(UserMessage(content=content))
            elif role == "assistant":
                azure_msgs.append(AssistantMessage(content=content))
        return azure_msgs

    def chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None, temperature: float = 0.7) -> str:
        if not self.client:
            raise RuntimeError("Azure Inference Client not initialized (check tokens/install)")
            
        model_name = model or "gpt-4o"
        
        azure_messages = self._convert_to_azure_messages(messages)
        
        response = self.client.complete(
            messages=azure_messages,
            model=model_name,
            temperature=temperature,
            max_tokens=4096
        )
        
        return response.choices[0].message.content

class OpenAIClient(LLMClient):
    def __init__(self):
        try:
            from openai import OpenAI
            api_key = os.getenv("OPENAI_API_KEY")
            if not api_key:
                 self.client = None
            else:
                 self.client = OpenAI(api_key=api_key)
        except ImportError:
            logger.error("openai package not installed")
            self.client = None
            
    def chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None, temperature: float = 0.7) -> str:
        if not self.client:
            raise RuntimeError("OpenAI Client not initialized")
            
        model_name = model or "gpt-4o"
        
        response = self.client.chat.completions.create(
            model=model_name,
            messages=messages,
            temperature=temperature
        )
        return response.choices[0].message.content

class OllamaClient(LLMClient):
    def __init__(self):
        self.base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        
    def chat(self, messages: List[Dict[str, Any]], model: Optional[str] = None, temperature: float = 0.7) -> str:
        model_name = model or "llama3" 
        
        url = f"{self.base_url}/api/chat"
        payload = {
            "model": model_name,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }
        
        try:
            response = httpx.post(url, json=payload, timeout=120.0)
            response.raise_for_status()
            data = response.json()
            return data.get("message", {}).get("content", "")
        except Exception as e:
            logger.error(f"Ollama request failed: {e}")
            raise

def get_llm_client(provider: Optional[str] = None) -> LLMClient:
    """
    Factory to get the appropriate LLM client.
    Priority:
    1. provider arg
    2. LLM_PROVIDER env var
    3. Default to Azure (GitHub Models)
    """
    if not provider:
        provider = os.getenv("LLM_PROVIDER", "azure").lower()
    
    if provider == "gh_copilot":
        return GHCopilotCLIClient()
    elif provider == "openai":
        return OpenAIClient()
    elif provider == "ollama":
        return OllamaClient()
    elif provider == "azure":
        return AzureInferenceClient()
    else:
        logger.warning(f"Unknown LLM_PROVIDER '{provider}', falling back to Azure")
        return AzureInferenceClient()
