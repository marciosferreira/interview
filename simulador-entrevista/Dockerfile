FROM python:3.11-slim

WORKDIR /app

# Install dependencies first (better layer caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

EXPOSE 8000

# No --reload in production
CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
