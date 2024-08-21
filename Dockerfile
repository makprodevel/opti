FROM python:alpine
RUN pip install poetry
WORKDIR /app
COPY pyproject.toml poetry.lock* ./
RUN python -m poetry install --no-root --no-dev
COPY . .
EXPOSE 8000
CMD ["python", "-m", "poetry", "run", "uvicorn", "opti.main:app", "--host", "0.0.0.0", "--port", "8000"]
