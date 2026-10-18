import json
import logging
import random
import time
from collections.abc import Callable

from openai import APIConnectionError, APIError, APIStatusError, OpenAI, RateLimitError

logger = logging.getLogger("cobrabot.llm")

EMPTY_REPLY = "No he podido generar una respuesta, inténtalo de nuevo."
MAX_TOOL_ROUNDS = 3

# Reintentos ante fallos transitorios del proveedor (429, cortes de conexión,
# respuestas malformadas sin 'choices'). Importante para el evento: varios
# equipos golpean el chat a la vez y OpenRouter devuelve 429 / respuestas vacías
# de forma intermitente. Con reintentos, esos baches se ocultan al jugador.
MAX_RETRIES = 4
RETRY_BASE_DELAY = 0.6  # segundos; crece de forma exponencial con jitter

# Enrutado de proveedores en OpenRouter. El modelo es el mismo (Llama 3.1 8B,
# igual de "débil" ante la inyección), pero forzamos proveedores fiables y con
# soporte de herramientas. Evita el proveedor que devolvía 429 / respuestas
# malformadas. allow_fallbacks deja que recurra a otros si los primeros fallan.
PROVIDER_ROUTING = {
    "order": ["Groq", "CoreWeave", "DeepInfra"],
    "allow_fallbacks": True,
}


class LLMError(Exception):
    """Error amigable, seguro para mostrar directamente al usuario del chat."""


class _TransientLLMError(Exception):
    """Fallo transitorio del proveedor: merece reintento."""


class LLMClient:
    def __init__(self, base_url: str, api_key: str, model: str):
        self._client = OpenAI(base_url=base_url, api_key=api_key)
        self.model = model

    def _create_once(self, messages: list[dict], tools: list[dict] | None = None):
        kwargs = {
            "model": self.model,
            "messages": messages,
            "temperature": 0.0,
            "max_tokens": 300,
            "extra_body": {"provider": PROVIDER_ROUTING},
        }
        if tools:
            kwargs["tools"] = tools
        try:
            response = self._client.chat.completions.create(**kwargs)
        except RateLimitError:
            logger.warning("LLM rate limit alcanzado (429)")
            raise _TransientLLMError("rate_limit")
        except APIConnectionError:
            logger.warning("No se pudo conectar con el proveedor del LLM")
            raise _TransientLLMError("connection")
        except (APIStatusError, APIError) as exc:
            logger.warning("Error de la API del LLM (se reintentará): %s", exc)
            raise _TransientLLMError("api_error")
        except Exception:
            logger.exception("Error inesperado llamando al LLM")
            raise LLMError("Ha ocurrido un error inesperado. Inténtalo de nuevo.")
        if not response or not response.choices:
            # El proveedor a veces devuelve 200 con choices=None y un error embebido.
            logger.warning("Respuesta del LLM sin choices (se reintentará): %s", response)
            raise _TransientLLMError("no_choices")
        return response

    def _create(self, messages: list[dict], tools: list[dict] | None = None):
        last_reason = "desconocido"
        for attempt in range(1, MAX_RETRIES + 1):
            try:
                return self._create_once(messages, tools=tools)
            except _TransientLLMError as exc:
                last_reason = str(exc)
                if attempt < MAX_RETRIES:
                    delay = RETRY_BASE_DELAY * (2 ** (attempt - 1)) + random.uniform(0, 0.4)
                    logger.info("Reintentando LLM (%s) intento %d/%d en %.1fs", last_reason, attempt, MAX_RETRIES, delay)
                    time.sleep(delay)
        logger.error("LLM agotó los reintentos (%s)", last_reason)
        raise LLMError("El asistente está muy solicitado ahora mismo. Inténtalo de nuevo en unos segundos.")

    def chat_with_tools(
        self,
        messages: list[dict],
        tools: list[dict],
        execute_tool: Callable[[str, dict], str],
    ) -> tuple[str, list[dict]]:
        trace: list[dict] = []
        convo = list(messages)

        for _ in range(MAX_TOOL_ROUNDS):
            message = self._create(convo, tools=tools).choices[0].message
            if not message.tool_calls:
                return (message.content or "").strip() or EMPTY_REPLY, trace

            convo.append({
                "role": "assistant",
                "content": message.content or "",
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {"name": tc.function.name, "arguments": tc.function.arguments},
                    }
                    for tc in message.tool_calls
                ],
            })
            for tc in message.tool_calls:
                try:
                    args = json.loads(tc.function.arguments or "{}")
                except json.JSONDecodeError:
                    args = {}
                result = execute_tool(tc.function.name, args)
                trace.append({"tool": tc.function.name, "args": args, "result": result})
                convo.append({"role": "tool", "tool_call_id": tc.id, "content": result})

        return EMPTY_REPLY, trace
