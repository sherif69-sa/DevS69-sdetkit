FROM public.ecr.aws/x8v8d7g8/mars-base:latest

WORKDIR /app

RUN groupadd -g 1001 app \
 && useradd -u 1001 -g app -m app

RUN python3 -m venv .venv \
 && . .venv/bin/activate \
 && python -m pip install -q pytest

ENV PYTHONPATH=src

COPY . .

USER app

CMD ["/bin/bash", "-lc", ". .venv/bin/activate && pytest -q"]
