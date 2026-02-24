"""Configuration module for Microsoft Agent Framework and Tavily API setup."""

import os
from dataclasses import dataclass

from agent_framework.azure import AzureOpenAIChatClient
from azure.identity import AzureCliCredential
from dotenv import load_dotenv
from tavily import TavilyClient


@dataclass
class Config:
    """Application configuration."""

    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_api_version: str
    tavily_api_key: str
    use_api_key: bool = False
    azure_openai_api_key: str | None = None


def load_config() -> Config:
    """Load configuration from environment variables."""
    load_dotenv()

    required_vars = [
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_DEPLOYMENT",
        "TAVILY_API_KEY",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    # Check if API key auth is used (optional)
    api_key = os.getenv("AZURE_OPENAI_API_KEY")

    return Config(
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        tavily_api_key=os.getenv("TAVILY_API_KEY"),
        use_api_key=bool(api_key),
        azure_openai_api_key=api_key,
    )


_config: Config | None = None
_chat_client: AzureOpenAIChatClient | None = None
_tavily_client: TavilyClient | None = None


def get_config() -> Config:
    """Get the application configuration (lazy loaded)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_chat_client() -> AzureOpenAIChatClient:
    """Get the Azure OpenAI Chat client (lazy loaded)."""
    global _chat_client
    if _chat_client is None:
        config = get_config()

        if config.use_api_key:
            _chat_client = AzureOpenAIChatClient(
                endpoint=config.azure_openai_endpoint,
                deployment_name=config.azure_openai_deployment,
                api_key=config.azure_openai_api_key,
                api_version=config.azure_openai_api_version,
            )
        else:
            # Use Azure CLI credential for authentication
            _chat_client = AzureOpenAIChatClient(
                endpoint=config.azure_openai_endpoint,
                deployment_name=config.azure_openai_deployment,
                credential=AzureCliCredential(),
                api_version=config.azure_openai_api_version,
            )
    return _chat_client


def get_tavily_client() -> TavilyClient:
    """Get the Tavily client for web search (lazy loaded)."""
    global _tavily_client
    if _tavily_client is None:
        config = get_config()
        _tavily_client = TavilyClient(api_key=config.tavily_api_key)
    return _tavily_client


def initialize() -> None:
    """Initialize the application (preload clients)."""
    get_chat_client()
    get_tavily_client()
