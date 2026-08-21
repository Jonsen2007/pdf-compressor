FROM python:3.10-slim

# Installeer Ghostscript + qpdf (qpdf doet een extra optimalisatiepas
# bovenop Ghostscript, zie server.py) op de virtuele Linux-server
RUN apt-get update && apt-get install -y ghostscript qpdf && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY . /app

# Installeer Flask
RUN pip install --no-cache-dir -r requirements.txt

# Start je server
# --workers: aantal parallelle processen (was standaard maar 1, dus vorige
#   bestand moest altijd volledig klaar zijn voor de volgende begon)
# --threads: extra gelijktijdigheid per worker
# --timeout: compressie van grote PDF's kan langer duren dan gunicorn's
#   standaard 30s, dus die verhogen we
CMD ["gunicorn", "-b", "0.0.0.0:10000", "--workers", "3", "--threads", "2", "--timeout", "120", "server:app"]