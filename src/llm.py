import os

from dotenv import load_dotenv

load_dotenv()


def _create_chat_llm():
    provider = os.getenv("LLM_PROVIDER", "ollama").lower().strip()

    if provider == "anthropic":
        # Uses the SAP-internal Hyperspace AI (HAI) proxy, which forwards
        # requests to Anthropic. Model IDs and base_url defaults reflect
        # the HAI convention, not the public Anthropic API.
        from langchain_anthropic import ChatAnthropic

        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError(
                "LLM_PROVIDER is set to 'anthropic' but ANTHROPIC_API_KEY is not set. "
                "Please set it in your .env file."
            )
        return ChatAnthropic(
            model=os.getenv("ANTHROPIC_MODEL", "anthropic--claude-4.6-opus"),
            base_url=os.getenv("ANTHROPIC_BASE_URL", "http://localhost:6655/anthropic/"),
            api_key=api_key,
        )

    if provider == "ollama":
        from langchain_ollama import ChatOllama

        return ChatOllama(model=os.getenv("OLLAMA_MODEL", "ministral-3:14b"))

    raise ValueError(
        f"Unknown LLM_PROVIDER: '{provider}'. Supported values: 'ollama', 'anthropic'."
    )


chat_llm = _create_chat_llm()


def bind_tools_sequential(llm, tools):
    """bind_tools, disabling parallel tool calls where the provider supports it.

    ChatAnthropic accepts ``parallel_tool_calls=False``; ChatOllama forwards
    the kwarg to its underlying client, which raises TypeError at invoke time.
    """
    if type(llm).__name__ == "ChatOllama":
        return llm.bind_tools(tools)
    return llm.bind_tools(tools, parallel_tool_calls=False)


def normalize_content(content):
    """Normalize LLM message content to a plain string.

    Anthropic returns content as a list of blocks when tool calls are present;
    Ollama always returns a string. This ensures a consistent string everywhere.
    """
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return " ".join(
            block.get("text", "") if isinstance(block, dict) else str(block)
            for block in content
        ).strip()
    return str(content)
