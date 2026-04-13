import os
import PyPDF2 as p2
import pytesseract as pt
from PIL import Image

def redimA4(img):
    A4_WIDTH, A4_HEIGHT = 2480, 3508
    img = img.convert("RGB")
    ratio = min(A4_WIDTH / img.width, A4_HEIGHT / img.height)

    new_width = int(img.width * ratio)
    new_height = int(img.height * ratio)

    img_resized = img.resize((new_width, new_height), Image.LANCZOS)
    background = Image.new("RGB", (A4_WIDTH, A4_HEIGHT), (255, 255, 255))
    x = (A4_WIDTH - new_width) // 2
    y = (A4_HEIGHT - new_height) // 2

    background.paste(img_resized, (x, y))

    return background

def ouverture_pdf(livre):
    recon_caracteres(livre)
    mise_en_page(livre)

def mise_en_page(livre):
    merger = p2.PdfMerger()

    for file in sorted(os.listdir(livre)):
        if file.lower().endswith(".pdf") and file != "Livre_numérique.pdf":
            merger.append(os.path.join(livre, file))

    merger.write(os.path.join(livre, "Livre_numérique.pdf"))
    merger.close()


def recon_caracteres(livre):
    for file in os.listdir(livre):
        if not file.lower().endswith(".jpg"):
            continue
        image_path = os.path.join(livre, file)
        try:
            img = Image.open(image_path)
        except:
            print(f"Fichier ignoré: {file}")
            continue
        img=redimA4(img)
        pdf_path = os.path.join(livre, file.replace(".jpg", ".pdf"))
        pdf = pt.image_to_pdf_or_hocr(img, extension='pdf')
        with open(pdf_path, 'wb') as f:
            f.write(pdf)
            
def suprimer_fichiers(livre):
    for file in os.listdir(livre):
        if file.lower().endswith(".jpg"):
            os.remove(os.path.join(livre, file))
        