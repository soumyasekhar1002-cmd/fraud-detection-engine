# Use official lightweight Python 3.12 slim image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies required for data science builds if needed
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first to leverage Docker layer caching
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the application source code into the container
COPY app/ /app/app/

# Expose the FastAPI listening port
EXPOSE 8000

# Run the application with Uvicorn production server
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]