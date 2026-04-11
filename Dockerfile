# Use Python 3.9 slim image
FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Copy requirements and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Expose port 8003
EXPOSE 8003

# Run the application
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8003", "--reload"]