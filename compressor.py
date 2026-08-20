import os
import subprocess
import tkinter as tk
from tkinter import filedialog, messagebox

# --- CONFIGURATIE ---
# Pas dit pad aan als Ghostscript niet in je PATH staat. 
# Bijvoorbeeld: GHOSTSCRIPT_CMD = r"C:\Program Files\gs\gs10.02.1\bin\gswin64c.exe"
GHOSTSCRIPT_CMD = "gswin64c" 

def compress_pdf(input_path, output_path):
    """Gebruikt Ghostscript om een PDF te comprimeren."""
    # -dPDFSETTINGS=/screen is voor maximale compressie (lage kwaliteit, prima voor schermen)
    # Opties: /screen (laag), /ebook (medium), /printer (hoog)
    command = [
        GHOSTSCRIPT_CMD,
        "-sDEVICE=pdfwrite",
        "-dCompatibilityLevel=1.4",
        "-dPDFSETTINGS=/ebook", 
        "-dNOPAUSE",
        "-dQUIET",
        "-dBATCH",
        f"-sOutputFile={output_path}",
        input_path
    ]
    try:
        subprocess.run(command, check=True, creationflags=subprocess.CREATE_NO_WINDOW)
        return True
    except subprocess.CalledProcessError:
        return False
    except FileNotFoundError:
        messagebox.showerror("Fout", "Ghostscript niet gevonden. Controleer het GHOSTSCRIPT_CMD pad.")
        return False

def select_folder_and_compress():
    """Zorgt voor de map-selectie en verwerkt alle PDF's."""
    folder_path = filedialog.askdirectory(title="Selecteer de map met PDF bestanden")
    
    if not folder_path:
        return # Gebruiker heeft geannuleerd

    # Maak output map aan
    output_folder = os.path.join(folder_path, "Gecomprimeerd")
    os.makedirs(output_folder, exist_ok=True)

    # Zoek alle PDF bestanden
    pdf_files = [f for f in os.listdir(folder_path) if f.lower().endswith('.pdf')]
    
    if not pdf_files:
        messagebox.showinfo("Klaar", "Geen PDF bestanden gevonden in deze map.")
        return

    succes_count = 0
    for pdf in pdf_files:
        input_path = os.path.join(folder_path, pdf)
        output_path = os.path.join(output_folder, pdf)
        
        if compress_pdf(input_path, output_path):
            succes_count += 1

    messagebox.showinfo("Klaar!", f"Compressie voltooid!\n{succes_count} van de {len(pdf_files)} bestanden gecomprimeerd.\nOpgeslagen in de map 'Gecomprimeerd'.")

# --- GUI SETUP ---
root = tk.Tk()
root.title("Bulk PDF Compressor MVP")
root.geometry("350x150")
root.eval('tk::PlaceWindow . center')

label = tk.Label(root, text="Kies een map om alle PDF's te comprimeren.", pady=20)
label.pack()

btn = tk.Button(root, text="Selecteer Map & Start", command=select_folder_and_compress, padx=10, pady=5, bg="lightblue")
btn.pack()

root.mainloop()