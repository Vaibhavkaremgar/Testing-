FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including LibreOffice for Word to PDF conversion
RUN apt-get update && apt-get install -y \
    gcc \
    libreoffice \
    libreoffice-writer \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model
RUN python -m spacy download en_core_web_sm

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Expose port
EXPOSE 8000

# Run the application with Railway's dynamic port
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]