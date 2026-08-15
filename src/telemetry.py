import os
import logging
from dotenv import load_dotenv

# Disable CrewAI phone-home telemetry to prevent SSL import hangs
os.environ["CREWAI_TELEMETRY_OPT_OUT"] = "true"

logger = logging.getLogger("nyayavaani.telemetry")

_telemetry_initialized = False

def setup_telemetry():
    """
    Initializes OpenTelemetry tracing for CrewAI and LiteLLM, exporting
    multi-agent traces directly to local Langfuse OTLP endpoint.
    """
    global _telemetry_initialized
    if _telemetry_initialized:
        return

    load_dotenv(override=True)

    # Patch langfuse.version for compatibility with newer langfuse SDKs
    try:
        import langfuse
        if not hasattr(langfuse, "version") and hasattr(langfuse, "_version"):
            langfuse.version = langfuse._version
    except Exception as e:
        logger.warning(f"Could not patch langfuse.version: {e}")

    host = os.getenv("LANGFUSE_HOST", "http://127.0.0.1:3000")
    otlp_endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", f"{host}/api/public/otel/v1/traces")
    if not otlp_endpoint.endswith("/v1/traces"):
        otlp_endpoint = otlp_endpoint.rstrip("/") + "/v1/traces"

    headers_str = os.getenv("OTEL_EXPORTER_OTLP_HEADERS", "")
    headers = {}
    if headers_str:
        for item in headers_str.split(","):
            if "=" in item:
                k, v = item.split("=", 1)
                headers[k.strip()] = v.strip()

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
        from openinference.instrumentation.crewai import CrewAIInstrumentor
        from openinference.instrumentation.litellm import LiteLLMInstrumentor

        provider = trace.get_tracer_provider()
        if not isinstance(provider, TracerProvider):
            provider = TracerProvider()
            trace.set_tracer_provider(provider)

        exporter = OTLPSpanExporter(
            endpoint=otlp_endpoint,
            headers=headers if headers else None
        )
        processor = BatchSpanProcessor(exporter)
        provider.add_span_processor(processor)

        CrewAIInstrumentor().instrument(tracer_provider=provider)
        LiteLLMInstrumentor().instrument(tracer_provider=provider)

        _telemetry_initialized = True
        logger.info(f"CrewAI & LiteLLM OpenTelemetry tracing initialized -> {otlp_endpoint}")
        print(f"[Telemetry] CrewAI & LiteLLM tracing initialized -> {otlp_endpoint}")
    except Exception as e:
        logger.error(f"Failed to initialize OpenTelemetry tracing: {e}")
        print(f"[Telemetry Error] {e}")

if __name__ == "__main__":
    setup_telemetry()
