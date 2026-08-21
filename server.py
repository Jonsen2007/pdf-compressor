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

PRESETS = {
    "/screen":  {"target_dpi": 96,  "max_dim": 900,  "quality": 45},
    "/ebook":   {"target_dpi": 150, "max_dim": 1400, "quality": 65},
    "/printer": {"target_dpi": 220, "max_dim": 2000, "quality": 82},
}

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

def _target_pixels_for_image(page, xref, target_dpi, fallback_max_dim):
    try:
        rects = page.get_image_rects(xref)
    except Exception:
        rects = []

    if rects:
        widest = max(rects, key=lambda r: r.width * r.height)
        display_w_in = widest.width / 72.0
        display_h_in = widest.height / 72.0
        if display_w_in > 0 and display_h_in > 0:
            target_w = max(50, round(display_w_in * target_dpi))
            target_h = max(50, round(display_h_in * target_dpi))
            return target_w, target_h

    return fallback_max_dim, fallback_max_dim

def _strip_bloat(doc):
    """Verwijdert opmaakprogramma-specifieke 'privé'-data en andere verborgen
    bloat die de PDF gigantisch kunnen maken, speciaal gericht op Adobe files."""
    
    # Wis alle standaard tekst-metadata
    try:
        doc.set_metadata({})
    except Exception:
        pass

    for xref in range(1, doc.xref_length()):
        try:
            keys = doc.xref_get_keys(xref)
        except Exception:
            continue
            
        # 1. Verwijder Adobe bewerkingsdata (vaak de ruwe .ai/.indd bestanden)
        if "PieceInfo" in keys:
            doc.xref_set_key(xref, "PieceInfo", "null")
        if "Private" in keys:
            doc.xref_set_key(xref, "Private", "null")
            
        # 2. Print/page thumbnails
        if "Thumb" in keys:
            doc.xref_set_key(xref, "Thumb", "null")
            
        # 3. XMP Metadata kan gigantisch worden (100MB+ door Adobe edit-historie)
        if "Metadata" in keys:
            doc.xref_set_key(xref, "Metadata", "null")
            
        # 4. Structurele PDF-tags. Bij complexe vector-afbeeldingen genereert dit 
        # voor letterlijk ELK lijntje een tag. Enorme overhead zonder nut voor weergave.
        if "StructTreeRoot" in keys:
            doc.xref_set_key(xref, "StructTreeRoot", "null")
        if "MarkInfo" in keys:
            doc.xref_set_key(xref, "MarkInfo", "null")

        # 5. Ingesloten originele bestanden weggooien
        if "EmbeddedFiles" in keys:
            doc.xref_set_key(xref, "EmbeddedFiles", "null")

def compress_pdf_smart(in_path, out_path, quality_preset):
    params = PRESETS.get(quality_preset, PRESETS["/ebook"])
    target_dpi = params["target_dpi"]
    fallback_max_dim = params["max_dim"]
    jpg_quality = params["quality"]

    doc = fitz.open(in_path)
    _strip_bloat(doc)
    processed_xrefs = set()

    for page in doc:
        # Extra optimalisatie voor zware vector/tekening-bestanden
        try:
            page.clean_contents()
        except Exception:
            pass

        image_list = page.get_images(full=True)
        for img_info in image_list:
            xref = img_info[0]
            if xref in processed_xrefs:
                continue
            processed_xrefs.add(xref)

            try:
                base_image = doc.extract_image(xref)
                image_bytes = base_image["image"]
                img = Image.open(io.BytesIO(image_bytes))
                native_w, native_h = img.size

                target_w, target_h = _target_pixels_for_image(
                    page, xref, target_dpi, fallback_max_dim
                )

                if native_w > target_w or native_h > target_h:
                    img.thumbnail((target_w, target_h), Image.Resampling.LANCZOS)

                if img.mode in ("RGBA", "P", "LA"):
                    img = img.convert("RGB")

                out_buffer = io.BytesIO()
                img.save(out_buffer, format="JPEG", quality=jpg_quality, optimize=True)
                new_bytes = out_buffer.getvalue()

                if len(new_bytes) < len(image_bytes):
                    page.replace_image(xref, stream=new_bytes)
            except Exception as e:
                print(f"Afbeelding overgeslagen wegens fout: {e}")

    try:
        doc.subset_fonts(fallback=True)
    except Exception as e:
        print(f"Font subsetting overgeslagen: {e}")

    # garbage=4 is cruciaal: dit gooit alle bestanden weg waarvan we hierboven 
    # de linkjes (zoals Metadata en StructTreeRoot) hebben stukgeknipt ("null").
    doc.save(
        out_path,
        garbage=4,
        deflate=True,
        deflate_images=True,
        deflate_fonts=True,
        clean=True,
    )
    doc.close()

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