FROM python:3.11-slim

WORKDIR /app

# Install curl for healthcheck
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY scanner/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy common and scanner code
COPY common/ /app/common/
COPY scanner/ /app/scanner/

# Set Python path to include /app
ENV PYTHONPATH=/app

# Set working directory to scanner
WORKDIR /app/scanner

# Expose webhook port
EXPOSE 8001

# Run the worker
CMD ["python", "worker.py"]

