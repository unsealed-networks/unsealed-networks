"""Configuration management for unsealed-networks."""

import os
from dataclasses import dataclass


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
