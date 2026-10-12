# Multi-stage Production Dockerfile for Skye8 Loan Collections Prioritiser
FROM python:3.11-slim

WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements and install
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application source code
COPY . .

# Generate initial trained models and 400-account production call book
RUN python run_pipeline.py

# Expose ports: 8501 for Streamlit UI, 8080 for Production REST API
EXPOSE 8501 8080

# Launch both REST API server and Streamlit app
CMD python app/server.py & streamlit run app/app.py --server.port 8501 --server.address 0.0.0.0
