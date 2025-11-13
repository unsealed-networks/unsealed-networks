"""Configuration management for unsealed-networks."""

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Load environment variables from .env file if it exists
# This allows users to configure via .env instead of shell environment
dotenv_path = Path.cwd() / ".env"
if dotenv_path.exists():
    load_dotenv(dotenv_path)
else:
    # Also try loading from project root if running from subdirectory
    load_dotenv()


@dataclass
class OllamaConfig:
    """Ollama LLM configuration."""

    host: str
    model: str
    timeout: int  # seconds

    @classmethod
    def from_env(cls, prefix: str = "OLLAMA") -> "OllamaConfig":
        """Load configuration from environment variables.

        Args:
            prefix: Environment variable prefix (e.g., "OLLAMA" or "OLLAMA_CLASSIFY")

        Returns:
            OllamaConfig instance
        """
        return cls(
            host=os.getenv(f"{prefix}_HOST", "http://localhost:11434"),
            model=os.getenv(f"{prefix}_MODEL", "qwen2.5:7b"),
            timeout=int(os.getenv(f"{prefix}_TIMEOUT", "120")),
        )


# Default configurations for different use cases
DEFAULT_OLLAMA_CONFIG = OllamaConfig.from_env("OLLAMA")
CLASSIFIER_OLLAMA_CONFIG = OllamaConfig.from_env("OLLAMA_CLASSIFY")
