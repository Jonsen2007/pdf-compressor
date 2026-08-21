import os, subprocess, tempfile, shutil
from flask import Flask, request, send_file
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# Controleer of dit pad klopt op jouw systeem
GHOSTSCRIPT_CMD = r"C:\Program Files\gs\gs10.07.1\bin\gswin64c.exe"

@app.route('/compress_single', methods=['POST'])
def compress_single():
    file = request.files.get('file')
    quality = request.form.get('quality', '/ebook')
    
    if not file:
        return "Geen bestand ontvangen", 400

    # Valideer bestandstype op backend
    if not file.filename.lower().endswith('.pdf'):
        return "Alleen PDF bestanden zijn toegestaan", 400

    temp_dir = tempfile.mkdtemp()
    in_path = os.path.join(temp_dir, file.filename)
    out_path = os.path.join(temp_dir, f"min_{file.filename}")
    file.save(in_path)

    cmd = [
        GHOSTSCRIPT_CMD, "-sDEVICE=pdfwrite", "-dCompatibilityLevel=1.4",
        f"-dPDFSETTINGS={quality}", "-dDownsampleColorImages=true",
        "-dNOPAUSE", "-dQUIET", "-dBATCH",
        f"-sOutputFile={out_path}", in_path
    ]
    
    try:
        subprocess.run(cmd, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        
        # Controleer of het gecomprimeerde bestand groter is geworden
        # Zo ja: behoud het originele bestand
        if os.path.getsize(out_path) >= os.path.getsize(in_path):
            shutil.copy(in_path, out_path)
            
        return send_file(out_path, as_attachment=True, download_name=file.filename)
    except Exception as e:
        print(f"Server Fout: {e}")
        return "Fout bij compressie", 500

if __name__ == '__main__':
    app.run(port=5000, debug=True)