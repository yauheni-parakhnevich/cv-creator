"""Configuration module for Azure OpenAI and Tavily API setup."""

import os
from dataclasses import dataclass

from dotenv import load_dotenv
from openai import AsyncAzureOpenAI
from agents import set_default_openai_client, set_tracing_disabled, OpenAIChatCompletionsModel
from tavily import TavilyClient


@dataclass
class Config:
    """Application configuration."""

    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_api_version: str
    azure_openai_deployment: str
    tavily_api_key: str


def load_config() -> Config:
    """Load configuration from environment variables."""
    load_dotenv()

    required_vars = [
        "AZURE_OPENAI_API_KEY",
        "AZURE_OPENAI_ENDPOINT",
        "AZURE_OPENAI_API_VERSION",
        "AZURE_OPENAI_DEPLOYMENT",
        "TAVILY_API_KEY",
    ]

    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        raise ValueError(f"Missing required environment variables: {', '.join(missing)}")

    return Config(
        azure_openai_api_key=os.getenv("AZURE_OPENAI_API_KEY"),
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT"),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION"),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT"),
        tavily_api_key=os.getenv("TAVILY_API_KEY"),
    )


_config: Config | None = None
_openai_client: AsyncAzureOpenAI | None = None
_tavily_client: TavilyClient | None = None
_model: OpenAIChatCompletionsModel | None = None


def get_config() -> Config:
    """Get the application configuration (lazy loaded)."""
    global _config
    if _config is None:
        _config = load_config()
    return _config


def get_openai_client() -> AsyncAzureOpenAI:
    """Get the Azure OpenAI client (lazy loaded)."""
    global _openai_client
    if _openai_client is None:
        config = get_config()
        _openai_client = AsyncAzureOpenAI(
            api_key=config.azure_openai_api_key,
            api_version=config.azure_openai_api_version,
            azure_endpoint=config.azure_openai_endpoint,
        )
    return _openai_client


def get_tavily_client() -> TavilyClient:
    """Get the Tavily client for web search (lazy loaded)."""
    global _tavily_client
    if _tavily_client is None:
        config = get_config()
        _tavily_client = TavilyClient(api_key=config.tavily_api_key)
    return _tavily_client


def get_model() -> OpenAIChatCompletionsModel:
    """Get the OpenAI chat completions model configured for Azure."""
    global _model
    if _model is None:
        config = get_config()
        client = get_openai_client()
        _model = OpenAIChatCompletionsModel(
            model=config.azure_openai_deployment,
            openai_client=client,
        )
    return _model


def initialize() -> None:
    """Initialize the OpenAI Agents SDK with Azure OpenAI client."""
    # Disable tracing - it only works with OpenAI's platform, not Azure
    set_tracing_disabled(True)
    client = get_openai_client()
    set_default_openai_client(client)
