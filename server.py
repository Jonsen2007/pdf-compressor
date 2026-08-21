import io
import os
import subprocess
import tempfile
import shutil
from flask import Flask, request, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)

GHOSTSCRIPT_CMD = "gs"

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
        "-dColorImageResolution=120", 
        "-dColorImageDownsampleType=/Bicubic",
        "-dDownsampleGrayImages=true",
        "-dGrayImageResolution=120", 
        "-dGrayImageDownsampleType=/Bicubic",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dJPEGQ=60", 
    ],
    "/printer": [
        "-dDownsampleColorImages=true",
        "-dColorImageResolution=300",
        "-dColorImageDownsampleType=/Bicubic",
        "-dDownsampleGrayImages=true",
        "-dGrayImageResolution=300",
        "-dGrayImageDownsampleType=/Bicubic",
        "-dAutoFilterColorImages=false",
        "-dColorImageFilter=/DCTEncode",
        "-dJPEGQ=85",
    ],
}

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
        "-dCompressFonts=true",
        "-dSubsetFonts=true",
        "-dDetectDuplicateImages=true",
        "-dCompressPages=true",
    ]
    cmd.extend(QUALITY_ARGS.get(quality, []))
    cmd.extend([f"-sOutputFile={out_path}", in_path])
    subprocess.run(cmd, check=True)

def run_qpdf_optimize(in_path, out_path):
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

    if not file or not file.filename or not file.filename.lower().endswith('.pdf'):
        return "Geen geldig PDF bestand ontvangen", 400

    safe_name = secure_filename(file.filename) or "document.pdf"
    temp_dir = tempfile.mkdtemp()
    
    try:
        in_path = os.path.join(temp_dir, safe_name)
        file.save(in_path)
        original_size = os.path.getsize(in_path)

        out_path = os.path.join(temp_dir, f"min_{safe_name}")
        run_ghostscript(quality, in_path, out_path)
        size = os.path.getsize(out_path)

        qpdf_out_path = os.path.join(temp_dir, f"qpdf_{safe_name}")
        try:
            run_qpdf_optimize(out_path, qpdf_out_path)
            qpdf_size = os.path.getsize(qpdf_out_path)
            if qpdf_size < size:
                out_path = qpdf_out_path
                size = qpdf_size
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as e:
            print(f"qpdf optimalisatie overgeslagen: {e}")

        if size >= original_size:
            out_path, size = in_path, original_size

        with open(out_path, 'rb') as f:
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
