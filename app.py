import io
import os
import subprocess
import tempfile
import shutil
from flask import Flask, request, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__)
CORS(app)

GHOSTSCRIPT_CMD = r"C:\Program Files\gs\gs10.07.1\bin\gswin64c.exe"
CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

@app.route('/compress_single', methods=['POST'])
def compress_single():
    file = request.files.get('file')
    quality = request.form.get('quality', '/ebook')

    if not file:
        return "Geen bestand ontvangen", 400

    if not file.filename or not file.filename.lower().endswith('.pdf'):
        return "Alleen PDF bestanden zijn toegestaan", 400

    safe_name = secure_filename(file.filename) or "document.pdf"
    temp_dir = tempfile.mkdtemp()
    
    try:
        in_path = os.path.join(temp_dir, safe_name)
        out_path = os.path.join(temp_dir, f"min_{safe_name}")
        file.save(in_path)
        original_size = os.path.getsize(in_path)

        cmd = [
            GHOSTSCRIPT_CMD, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
            f"-dPDFSETTINGS={quality}", "-dDownsampleColorImages=true",
            "-dNOPAUSE", "-dQUIET", "-dBATCH",
            f"-sOutputFile={out_path}", in_path
        ]

        subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW)
        out_size = os.path.getsize(out_path)

        if out_size >= original_size:
            shutil.copy(in_path, out_path)

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
    app.run(port=5000, debug=True)
