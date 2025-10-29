FROM python:3.14-slim

WORKDIR /app

# Install curl for health checks
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Copy requirements and install dependencies
COPY manager/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy common and manager code
COPY common/ /app/common/
COPY manager/ /app/manager/

# Set Python path to include /app
ENV PYTHONPATH=/app

# Set working directory to manager
WORKDIR /app/manager

# Expose port
EXPOSE 8000

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
