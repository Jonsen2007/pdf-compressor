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
# PERFORMANCE (Render Free tier): met een gedeelde/beperkte CPU concurreren
# meerdere workers om dezelfde rekenkracht, wat elke individuele compressie
# juist trager maakt in plaats van sneller. Op deze tier is 1 worker (die
# verzoeken netjes na elkaar afhandelt) sneller per bestand dan 3 workers
# die allemaal een eigen Ghostscript/qpdf-proces om CPU-tijd laten vechten.
# --timeout iets hoger gezet omdat een koude start + trage CPU bij een groot
# bestand samen de oude 120s kunnen overschrijden.
CMD ["gunicorn", "-b", "0.0.0.0:10000", "--workers", "1", "--threads", "2", "--timeout", "180", "server:app"]