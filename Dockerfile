FROM python:3.10-slim

# Installeer alleen qpdf (Ghostscript is niet meer nodig)
RUN apt-get update && apt-get install -y qpdf && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Installeer Flask, PyMuPDF, Pillow, etc.
RUN pip install --no-cache-dir -r requirements.txt

# Start de server
CMD ["gunicorn", "-b", "0.0.0.0:10000", "--workers", "1", "--threads", "2", "--timeout", "180", "server:app"]