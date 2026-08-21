import os, subprocess, tempfile, shutil
from flask import Flask, request, send_file, send_from_directory
from flask_cors import CORS

# app ingesteld om ook je HTML, CSS en JS bestanden te kunnen laden
app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)

# Aangepast naar het standaard Linux-commando voor Ghostscript op Render
GHOSTSCRIPT_CMD = "gs"

# Zorgt ervoor dat je website wordt geladen als mensen naar je link gaan
@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/compress_single', methods=['POST'])
def compress_single():
    file = request.files.get('file')
    quality = request.form.get('quality', '/ebook')
    
    if not file or not file.filename.lower().endswith('.pdf'):
        return "Geen geldig PDF bestand ontvangen", 400

    temp_dir = tempfile.mkdtemp()
    in_path = os.path.join(temp_dir, file.filename)
    out_path = os.path.join(temp_dir, f"min_{file.filename}")
    file.save(in_path)

    cmd = [
        GHOSTSCRIPT_CMD,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={quality}",
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH"
    ]

    if quality == '/screen':
        cmd.extend([
            "-dDownsampleColorImages=true",
            "-dColorImageResolution=72",
            "-dColorImageDownsampleType=/Bicubic",
            "-dDownsampleGrayImages=true",
            "-dGrayImageResolution=72",
            "-dGrayImageDownsampleType=/Bicubic",
            "-dAutoFilterColorImages=false",
            "-dColorImageFilter=/DCTEncode",
            "-dJPEGQ=40"
        ])
    elif quality == '/ebook':
        cmd.extend([
            "-dDownsampleColorImages=true",
            "-dColorImageResolution=150",
            "-dColorImageDownsampleType=/Bicubic",
            "-dDownsampleGrayImages=true",
            "-dGrayImageResolution=150",
            "-dGrayImageDownsampleType=/Bicubic",
            "-dAutoFilterColorImages=false",
            "-dColorImageFilter=/DCTEncode",
            "-dJPEGQ=75"
        ])

    cmd.extend([f"-sOutputFile={out_path}", in_path])

    try:
        # 'creationflags' is weggehaald omdat dit alleen voor Windows werkt
        subprocess.run(cmd, check=True)
        
        if os.path.getsize(out_path) >= os.path.getsize(in_path):
            shutil.copy(in_path, out_path)
            
        return send_file(out_path, as_attachment=True, download_name=file.filename)
    except Exception as e:
        print(f"Server Fout: {e}")
        return "Fout bij compressie", 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)