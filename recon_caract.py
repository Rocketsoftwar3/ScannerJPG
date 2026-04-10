import os
import subprocess
import PyPDF2 as p2
import pytesseract as pt
from PIL import Image


def ouverture_pdf(livre):
    recon_caracteres(livre)
    mise_en_page(livre)
    subprocess.Popen([os.path.join(livre, "Livre_numérique.pdf")], shell=True)

def mise_en_page(livre):
    pdf=p2.PdfWriter()
    for file in os.listdir(livre):
        if file.lower().endswith(".pdf"):
            pdf.add_page(p2.PdfReader(os.path.join(livre, file)).pages[0])
    with open(os.path.join(livre, "Livre_numérique.pdf"), "wb") as f:
        pdf.write(f)


def recon_caracteres(livre):
    for file in os.listdir(livre):
        if not file.lower().endswith(".png"):
            continue
        image_path = os.path.join(livre, file)
        try:
            Image.open(image_path).verify()
        except:
            print(f"Fichier ignoré: {file}")
            continue
        pdf_path = os.path.join(livre, file.replace(".png", ".pdf"))
        pdf = pt.image_to_pdf_or_hocr(image_path, extension='pdf')
        with open(pdf_path, 'wb') as f:
            f.write(pdf)
        
ouverture_pdf("C:\\Users\\claud\\Documents\\Stage\\ImagesPDF\\ImagesJPG")