FROM python:3.11-slim

WORKDIR /usr/src/app

# Create a virtual environment
RUN python -m venv /opt/venv
# Activate the virtual environment
ENV PATH="/opt/venv/bin:$PATH"

# Install dependencies
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Set PYTHONPATH to include the src directory
ENV PYTHONPATH=/usr/src/app/src

# Expose port
EXPOSE 8080

# Run the application
CMD ["uvicorn", "openapi_server.main:app", "--host", "0.0.0.0", "--port", "8080"]
