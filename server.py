import io
import os
import subprocess
import tempfile
import shutil
import fitz  # PyMuPDF
from PIL import Image
from flask import Flask, request, send_file, send_from_directory
from flask_cors import CORS
from werkzeug.utils import secure_filename

app = Flask(__name__, static_url_path='', static_folder='.')
CORS(app)

# Preset configuraties voor slimme beeldbewerking
PRESETS = {
    "/screen":  {"max_dim": 800,  "quality": 45},
    "/ebook":   {"max_dim": 1100, "quality": 60},  # iLovePDF balans: klein én scherpe tekst
    "/printer": {"max_dim": 1600, "quality": 80},
}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

def compress_pdf_smart(in_path, out_path, quality_preset):
    """Haalt afbeeldingen uit de PDF, verkleint ze slim en plaatst ze haarscherp terug."""
    params = PRESETS.get(quality_preset, PRESETS["/ebook"])
    doc = fitz.open(in_path)

    for page in doc:
        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                img = Image.open(io.BytesIO(image_bytes))

                # Alleen schalen als het plaatje groter is dan max_dim
                if max(img.size) > params["max_dim"]:
                    img.thumbnail((params["max_dim"], params["max_dim"]), Image.Resampling.LANCZOS)

                if img.mode in ("RGBA", "P"):
                    img = img.convert("RGB")

                out_buffer = io.BytesIO()
                # optimize=True gebruikt slimme compressie waardoor letters op foto's strak blijven
                img.save(out_buffer, format="JPEG", quality=params["quality"], optimize=True)
                page.replace_image(xref, stream=out_buffer.getvalue())
            except Exception as e:
                print(f"Afbeelding overgeslagen wegens fout: {e}")

    # Sla PDF op met maximale interne opschoning
    doc.save(out_path, garbage=4, deflate=True, clean=True)
    doc.close()

def run_qpdf_optimize(in_path, out_path):
    """Extra optimalisatie op objectniveau."""
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

    if not file or not file.filename or not file.filename.lower().endswith('.pdf'):
        return "Geen geldig PDF bestand ontvangen", 400

    safe_name = secure_filename(file.filename) or "document.pdf"
    temp_dir = tempfile.mkdtemp()
    
    try:
        in_path = os.path.join(temp_dir, safe_name)
        file.save(in_path)
        original_size = os.path.getsize(in_path)

        smart_out_path = os.path.join(temp_dir, f"smart_{safe_name}")
        compress_pdf_smart(in_path, smart_out_path, quality)
        size = os.path.getsize(smart_out_path)
        out_path = smart_out_path

        # Na-optimalisatie met qpdf
        qpdf_out_path = os.path.join(temp_dir, f"qpdf_{safe_name}")
        try:
            run_qpdf_optimize(smart_out_path, qpdf_out_path)
            qpdf_size = os.path.getsize(qpdf_out_path)
            if qpdf_size < size:
                out_path = qpdf_out_path
                size = qpdf_size
        except Exception as e:
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