# syntax=docker/dockerfile:1.6
FROM python:3.12-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UV_SYSTEM_PYTHON=1

# Install system packages required by WeasyPrint and other dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
      # WeasyPrint core dependencies
      libcairo2 \
      libpango-1.0-0 \
      libpangocairo-1.0-0 \
      libpangoft2-1.0-0 \
      libgdk-pixbuf-2.0-0 \
      libffi-dev \
      libgobject-2.0-0 \
      libgirepository-1.0-1 \
      # Additional useful packages
      libxml2 \
      libxslt1.1 \
      shared-mime-info \
      # Fonts for better PDF rendering
      fonts-liberation \
      fonts-dejavu-core \
      && rm -rf /var/lib/apt/lists/*

# Install uv
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

WORKDIR /app

# Copy dependency files first for better caching
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-cache

# Copy rest of the application
COPY . .

# Create non-root user for security
RUN useradd -m -u 1000 appuser && chown -R appuser:appuser /app
USER appuser

# Expose port for FastAPI
EXPOSE 8000

# Azure App Service expects port 8000 by default
CMD ["uv", "run", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]