FROM python:3.12-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/uv

WORKDIR /app

COPY pyproject.toml uv.lock /app/
RUN uv sync --no-dev --compile-bytecode

COPY chatbot_schema.py dbconfig.py run_engine.py /app/

CMD ["uv", "run", "python", "run_engine.py"]




