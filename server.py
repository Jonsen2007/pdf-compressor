import io
import os
import subprocess
import tempfile
import shutil
from flask import Flask, request, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

# app ingesteld om ook je HTML, CSS en JS bestanden te kunnen laden
app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)

# Aangepast naar het standaard Linux-commando voor Ghostscript op Render
GHOSTSCRIPT_CMD = "gs"

# Kwaliteitsniveaus van hoog naar laag, gebruikt om automatisch verder te
# comprimeren als de "max. grootte" nog niet is gehaald.
QUALITY_LADDER = ["/printer", "/ebook", "/screen"]

QUALITY_ARGS = {
    "/screen": [
        "-dDownsampleColorImages=true",
        "-dColorImageResolution=72",
        "-dColorImageDownsampleType=/Bicubic",
        "-dDownsampleGrayImages=true",
        "-dGrayImageResolution=72",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dJPEGQ=40",
    ],
    "/ebook": [
        "-dDownsampleColorImages=true",
        "-dColorImageResolution=150",
        "-dColorImageDownsampleType=/Bicubic",
        "-dDownsampleGrayImages=true",
        "-dGrayImageResolution=150",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dJPEGQ=75",
    ],
    "/printer": [],
}


# Zorgt ervoor dat je website wordt geladen als mensen naar je link gaan
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')


def run_ghostscript(quality, in_path, out_path):
    cmd = [
        GHOSTSCRIPT_CMD,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={quality}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        # Pakt ook fonts en dubbele objecten aan i.p.v. alleen afbeeldingen te
        # downsamplen. Bij "professionele" PDF's (veel tekst/vectoren/ingesloten
        # fonts) zit de winst vaak hier, niet in de rasterafbeeldingen.
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dDetectDuplicateImages=true",
        "-dCompressPages=true",
    ]
    cmd.extend(QUALITY_ARGS.get(quality, []))
    cmd.extend([f"-sOutputFile={out_path}", in_path])
    subprocess.run(cmd, check=True)


def run_qpdf_optimize(in_path, out_path):
    """Extra nabewerking bovenop Ghostscript: herschrijft de PDF-structuur
    met object streams, wat vaak nog 5-15% extra bespaart bovenop wat
    Ghostscript alleen doet. Faalt qpdf (niet geïnstalleerd, corrupt bestand,
    etc.) dan gebruiken we gewoon het Ghostscript-resultaat."""
    cmd = [
        "qpdf",
        "--object-streams=generate",
        "--compression-level=9",
        "--recompress-flate",
        in_path,
        out_path,
    ]
    subprocess.run(cmd, check=True, timeout=60)


@app.route('/compress_single', methods=['POST'])
def compress_single():
    file = request.files.get('file')
    quality = request.form.get('quality', '/ebook')
    if quality not in QUALITY_ARGS:
        quality = '/ebook'

    # BUGFIX: max_target_mb werd door de frontend verstuurd maar hier nooit
    # gelezen of toegepast, waardoor de "max. bestandsgrootte" instelling
    # geen enkel effect had.
    try:
        max_target_mb = float(request.form.get('max_target_mb', 0))
    except (TypeError, ValueError):
        max_target_mb = 0

    if not file or not file.filename or not file.filename.lower().endswith('.pdf'):
        return "Geen geldig PDF bestand ontvangen", 400

    # BUGFIX: de originele bestandsnaam werd ongefilterd gebruikt om paden op
    # te bouwen. Een naam als "../../iets.pdf" kon zo buiten de tijdelijke map
    # schrijven (path traversal). secure_filename() voorkomt dit.
    safe_name = secure_filename(file.filename) or "document.pdf"

    temp_dir = tempfile.mkdtemp()
    try:
        in_path = os.path.join(temp_dir, safe_name)
        file.save(in_path)
        original_size = os.path.getsize(in_path)

        max_target_bytes = max_target_mb * 1024 * 1024 if max_target_mb > 0 else None

        # Begin bij de door de gebruiker gekozen kwaliteit, en val pas terug op
        # zwaardere compressie als de gewenste max. grootte nog niet gehaald is.
        attempt_order = [quality] + [q for q in QUALITY_LADDER if q != quality]

        best_path = None
        best_size = None

        for step, q in enumerate(attempt_order):
            out_path = os.path.join(temp_dir, f"min_{step}_{safe_name}")
            try:
                run_ghostscript(q, in_path, out_path)
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                print(f"Ghostscript fout ({q}): {e}")
                continue

            size = os.path.getsize(out_path)
            if best_size is None or size < best_size:
                best_path, best_size = out_path, size

            # Extra qpdf-pass bovenop het Ghostscript-resultaat. Dit kan
            # falen (qpdf niet aanwezig, edge-case in het bestand) - dan
            # gaan we gewoon door met het Ghostscript-resultaat hierboven.
            qpdf_out_path = os.path.join(temp_dir, f"qpdf_{step}_{safe_name}")
            try:
                run_qpdf_optimize(out_path, qpdf_out_path)
                qpdf_size = os.path.getsize(qpdf_out_path)
                if qpdf_size < best_size:
                    best_path, best_size = qpdf_out_path, qpdf_size
                    size = qpdf_size
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
                print(f"qpdf optimalisatie overgeslagen: {e}")

            # Stop zodra we onder de gewenste max. grootte zitten, of als er
            # geen max. grootte is ingesteld (dan is de eerste poging genoeg).
            if max_target_bytes is None or size <= max_target_bytes:
                break

        if best_path is None:
            return "Fout bij compressie", 500

        # Als comprimeren het bestand juist groter maakte, behoud het origineel.
        if best_size >= original_size:
            best_path, best_size = in_path, original_size

        # Lees het resultaat in het geheugen zodat de tijdelijke map meteen
        # daarna opgeruimd kan worden (voorheen bleven deze mappen onbeperkt
        # op de server staan bij elke upload).
        with open(best_path, 'rb') as f:
            data = f.read()

        return send_file(
            io.BytesIO(data),
            as_attachment=True,
            download_name=file.filename,
            mimetype='application/pdf',
        )
    except Exception as e:
        print(f"Server Fout: {e}")
        return "Fout bij compressie", 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    debug_mode = os.environ.get("FLASK_DEBUG", "false").lower() == "true"
    app.run(host='0.0.0.0', port=port, debug=debug_mode)