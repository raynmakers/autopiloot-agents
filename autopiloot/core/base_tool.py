import os
from abc import ABC, abstractmethod
from typing import Any, Dict, TypedDict
from dotenv import load_dotenv

load_dotenv()


class ToolRequest(TypedDict):
    pass


class ToolResponse(TypedDict):
    pass


class BaseTool(ABC):
    def __init__(self):
        self._validate_env_vars()
    
    @abstractmethod
    def _validate_env_vars(self):
        pass
    
    @abstractmethod
    def run(self, request: Dict[str, Any]) -> Dict[str, Any]:
        pass
    
    def get_env_var(self, key: str, required: bool = True) -> str:
        value = os.getenv(key)
        if required and not value:
            raise ValueError(f"Environment variable {key} is required but not set")
        return value or ""