import os
import subprocess
import PyPDF2 as p2
import pytesseract as pt
from PIL import Image
import image_split as ims
import shutil

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

def decoupe_livre(livre):
    destination=os.path.join(livre,'LivreDecoupe')
    if os.path.isdir(destination):
        shutil.rmtree(destination)
    os.makedirs(destination)
    for file in os.listdir(livre):
        if file.lower().endswith(".jpg"):
            img=Image.open(os.path.join(livre,file))
            width,height=img.size
            img.close()
            if width>height:
                print(os.path.join(livre,file))
                ims.split_book(os.path.join(livre,file),destination,margin=20)
                
    return destination

                

def ouverture_pdf(livre):
    dossier_decoupe = decoupe_livre(livre)
    recon_caracteres(dossier_decoupe)
    mise_en_page(dossier_decoupe)

def mise_en_page(livre):
    merger = p2.PdfMerger()

    for file in sorted(os.listdir(livre)):
        print(f"Traitement du fichier : {file}")
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
            
mise_en_page(r"C:\Users\claud\Documents\Stage\ImagesPDF\Vente de Bacque\13.04.26\PPPPC\LivreDecoupe")
subprocess.Popen([os.path.join(r"C:\Users\claud\Documents\Stage\ImagesPDF\Vente de Bacque\13.04.26\PPPPC\LivreDecoupe", "Livre_numérique.pdf")], shell=True)

            
    
        