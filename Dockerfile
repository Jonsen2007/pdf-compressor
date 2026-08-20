FROM python:3.10-slim

# Installeer Ghostscript op de virtuele Linux-server
RUN apt-get update && apt-get install -y ghostscript && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Installeer Flask
RUN pip install --no-cache-dir -r requirements.txt

# Start je server
CMD ["gunicorn", "-b", "0.0.0.0:10000", "server:app"]