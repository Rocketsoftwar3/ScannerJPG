import os
import subprocess
import PyPDF2 as p2
import pytesseract as pt
from PIL import Image
import image_split as ims
import shutil
from multiprocessing import Pool, cpu_count

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

def decoupe_livre(livre, ref_width = None):
    destination=os.path.join(livre,'LivreDecoupe')
    if os.path.isdir(destination):
        shutil.rmtree(destination)
    os.makedirs(destination)

    cover_width = None
    cover_path = None
    for file in os.listdir(livre):
        if file.lower().endswith(".jpg") and ('001' in file or '0001' in file):
            img = Image.open(os.path.join(livre, file))
            cover_width = img.width
            cover_path = os.path.join(livre, file)
            img.close()
            break

    if cover_width is None:
        print("⚠️ Aucune couverture trouvée (fichier avec 001 ou 0001). Utilisation de tous les fichiers sans split.")
        raise ValueError ("fichier de couverture introuvable")
    
    if ref_width is None:
        print("Aucune taille de réference de texte trouvée")
        raise ValueError ("fichier de couverture introuvable")


    for file in os.listdir(livre):
        if file.lower().endswith(".jpg"):
            print(file)
            img=Image.open(os.path.join(livre,file))
            width,height=img.size
            img.close()
            if width>height:
                ims.split_book(os.path.join(livre,file),destination,20,cover_width, ref_width)
            else :
                ims.save_image(os.path.join(livre,file),destination)
                
    return destination

                

def ouverture_pdf(livre, ref_width):    
    try:
        dossier_decoupe = decoupe_livre(livre, ref_width)
    except ValueError as e:
        print("fichier de couverture introuvable")
        
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


def traiter_image(args):
    livre, file = args
    if not file.lower().endswith(".jpg"):
        return
    
    image_path = os.path.join(livre, file)
    
    try:
        img = Image.open(image_path)
    except:
        print(f"Fichier ignoré: {file}")
        return

    #img = redimA4(img)
    pdf_path = os.path.join(livre, file.replace(".jpg", ".pdf"))
    
    pdf = pt.image_to_pdf_or_hocr(img, extension='pdf', config='--oem 1 --psm 6')
    
    with open(pdf_path, 'wb') as f:
        f.write(pdf)

def recon_caracteres(livre):
    files = os.listdir(livre)
    args = [(livre, file) for file in files]

    with Pool(cpu_count()) as p:
        p.map(traiter_image, args)
            
def suprimer_fichiers(livre):
    for file in os.listdir(livre):
        if file.lower().endswith(".jpg"):
            os.remove(os.path.join(livre, file))
            

            
    
        