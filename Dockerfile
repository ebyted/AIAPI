FROM python:3.11-slim

# Set work directory
WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Expose port
EXPOSE 8011

# Start the server
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8011"]