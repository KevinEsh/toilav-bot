FROM python:3.12.11-slim
COPY --from=ghcr.io/astral-sh/uv:latest /uv /bin/

WORKDIR /code
ENV PATH="/code/.venv/bin:$PATH"

COPY pyproject.toml .python-version uv.lock /code/
RUN uv sync --locked --no-dev

COPY chatbot_schema.py dbconfig.py run_engine.py /code/

#import env variables from .env file
# COPY .env /code/
#set environment variables from .env file
# ENV $(cat .env | xargs)


CMD ["python", "run_engine.py"]
