from langchain_core.language_models.chat_models import BaseChatModel
from app.core.config import settings


class LLMFactory:
    """
    Factory class for creating LLM instances based on the configured provider.

    Provider SDKs are imported lazily inside `get_llm()` so that importing this
    module (and anything that depends on it, such as the orchestrator) does not
    require every provider's packages to be installed. A deployment that only
    uses OpenAI needs only `langchain-openai`.
    """

    @staticmethod
    def get_llm() -> BaseChatModel:
        provider = settings.LLM_PROVIDER.lower()

        if provider == "openai":
            if not settings.OPENAI_API_KEY:
                raise ValueError("OPENAI_API_KEY must be configured to use OpenAI.")
            from langchain_openai import ChatOpenAI
            return ChatOpenAI(
                model=settings.LLM_MODEL_NAME,
                api_key=settings.OPENAI_API_KEY,
                temperature=0.0,
            )

        elif provider == "anthropic":
            if not settings.ANTHROPIC_API_KEY:
                raise ValueError("ANTHROPIC_API_KEY must be configured to use Anthropic.")
            from langchain_anthropic import ChatAnthropic
            return ChatAnthropic(
                model_name=settings.LLM_MODEL_NAME,
                api_key=settings.ANTHROPIC_API_KEY,
                temperature=0.0,
            )

        elif provider == "ollama":
            from langchain_ollama import ChatOllama
            return ChatOllama(
                model=settings.LLM_MODEL_NAME,
                base_url=settings.OLLAMA_BASE_URL,
                temperature=0.0,
            )

        elif provider == "google":
            if not settings.GOOGLE_API_KEY:
                raise ValueError("GOOGLE_API_KEY must be configured to use Google LLM.")
            from langchain_google_genai import ChatGoogleGenerativeAI
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
