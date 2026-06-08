from langchain_core.language_models.chat_models import BaseChatModel
from app.core.config import settings
from langchain_anthropic import ChatAnthropic
from langchain_openai import ChatOpenAI
from langchain_ollama import ChatOllama
from langchain_google_genai import ChatGoogleGenerativeAI


class LLMFactory:
    """
    Factory class for creating LLM instances based on the configured provider.
    """

    @staticmethod
    def get_llm() -> BaseChatModel:
        provider = settings.LLM_PROVIDER.lower()

        if provider == "openai":

            if not settings.OPENAI_API_KEY:
                raise ValueError(
                    "OPENAI_API_KEY must be configured to use OpenAI."
                )
            return ChatOpenAI(
                model=settings.LLM_MODEL_NAME,
                api_key=settings.OPENAI_API_KEY,
                temperature=0.0,
            )

        elif provider == "anthropic":

            if not settings.ANTHROPIC_API_KEY:
                raise ValueError(
                    "ANTHROPIC_API_KEY must be configured to use Anthropic."
                )
            return ChatAnthropic(
                model_name=settings.LLM_MODEL_NAME,
                api_key=settings.ANTHROPIC_API_KEY,
                temperature=0.0,
            )

        elif provider == "ollama":

            return ChatOllama(
                model=settings.LLM_MODEL_NAME,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.0,
            )

        elif provider == "google":

            if not settings.GOOGLE_API_KEY:
                raise ValueError(
                    "GOOGLE_API_KEY must be configured to use Google LLM."
                )
            return ChatGoogleGenerativeAI(
                model=settings.LLM_MODEL_NAME,
                api_key=settings.GOOGLE_API_KEY,
                temperature=0.0,
            )
        else:
            raise ValueError(
                f"LLM_PROVIDER '{settings.LLM_PROVIDER}' not recognized. "
                "Please choose from 'openai', 'anthropic', 'ollama', or 'google'."
            )