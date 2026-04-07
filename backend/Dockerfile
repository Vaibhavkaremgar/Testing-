FROM python:3.11-slim

WORKDIR /app

# Install system dependencies including OCR + PDF tooling for resume ingestion.
RUN apt-get update && apt-get install -y \
    gcc \
    libreoffice \
    libreoffice-writer \
    tesseract-ocr \
    tesseract-ocr-eng \
    libtesseract-dev \
    poppler-utils \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download spaCy model (specific version)
RUN python -m pip install https://github.com/explosion/spacy-models/releases/download/en_core_web_sm-3.7.1/en_core_web_sm-3.7.1-py3-none-any.whl

# Copy application code
COPY . .

# Create uploads directory
RUN mkdir -p uploads

# Railway production OCR configuration
ENV TESSERACT_CMD=/usr/bin/tesseract
RUN tesseract --version

# Expose port
EXPOSE 8000

# Run the application with Railway's dynamic port
CMD ["sh", "-c", "uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
