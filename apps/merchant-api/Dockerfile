FROM python:3.12-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    postgresql-client \
    && rm -rf /var/lib/apt/lists/*

# Copy lekker-pay package first (for dependency installation)
COPY packages/lekker-pay /packages/lekker-pay

# Install lekker-pay in editable mode
RUN pip install -e /packages/lekker-pay

# Copy merchant-api requirements and install
COPY apps/merchant-api/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy merchant-api application code
COPY apps/merchant-api/app ./app

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# Made with Bob
