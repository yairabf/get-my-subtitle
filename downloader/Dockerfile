FROM python:3.11-slim

WORKDIR /app

# Copy requirements and install dependencies
COPY downloader/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Copy common and downloader code
COPY common/ /app/common/
COPY downloader/ /app/downloader/

# Set Python path to include /app
ENV PYTHONPATH=/app

# Set working directory to downloader
WORKDIR /app/downloader

# Run the worker
CMD ["python", "worker.py"]
