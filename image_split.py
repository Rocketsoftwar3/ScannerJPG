"""
split_book_pages.py
-------------------
Découpe une image JPG de livre ouvert en deux pages distinctes (gauche et droite).
Logique :
1. Supprimer 8% sur les côtés gauche/droit et 4% en haut/bas (bordures du livre).
2. Sur la zone centrale restante, détecter les limites horizontales du texte
   (seuil de 3% de pixels blancs par colonne).
3. Trouver la gouttière (minimum de densité dans la zone 35%-65%).
4. Découper les pages avec une marge ajustable autour de la gouttière.
"""

import os
import numpy as np
import cv2

# ──────────────────────────────────────────────────────────────────────────────
# 1. UTILITAIRES INTERNES
# ──────────────────────────────────────────────────────────────────────────────

def _load_image(path):
    """Charge l'image en couleur (BGR) et en niveaux de gris."""
    bgr = cv2.imread(path)
    if bgr is None:
        raise FileNotFoundError(f"Impossible de charger : {path}")
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
    return bgr, gray

def _binarize(gray):
    """
    Binarisation adaptative : texte blanc (255), fond noir (0).
    Utilise la méthode GAUSSIENNE pour s'adapter aux variations d'éclairage.
    """
    binary = cv2.adaptiveThreshold(
        gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY_INV, blockSize=51, C=15
    )
    # Dilatation légère pour connecter les lettres entre elles
    kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 2))
    binary = cv2.dilate(binary, kernel, iterations=1)
    return binary

def _fast_denoise(binary, min_component_area=10):
    """
    Supprime le bruit de l'image binaire :
    1. Ouverture morphologique (érosion puis dilatation) pour enlever les petits pixels isolés.
    2. Filtrage par taille des composantes connexes (optionnel).
    """
    # Ouverture : supprime les petits points blancs isolés
    kernel = np.ones((4, 4), np.uint8)
    denoised = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

    # (Optionnel) Suppression des composantes trop petites
    if min_component_area > 0:
        nb_components, labels, stats, _ = cv2.connectedComponentsWithStats(denoised, connectivity=8)
        for i in range(1, nb_components):
            if stats[i, cv2.CC_STAT_AREA] < min_component_area:
                denoised[labels == i] = 0
    return denoised

def _apply_global_margins(width, height, horiz_percent=0.08, vert_percent=0.04):
    """
    Retourne (x_start, x_end, y_start, y_end) après suppression :
    - horiz_percent sur les bords gauche et droit (par défaut 8%)
    - vert_percent sur les bords haut et bas (par défaut 4%)
    """
    margin_h = int(width * horiz_percent)
    margin_v = int(height * vert_percent)
    x_start = margin_h
    x_end   = width - margin_h
    y_start = margin_v
    y_end   = height - margin_v
    return x_start, x_end, y_start, y_end

def _get_text_boundaries_x(binary, col_threshold=0.03):
    """
    Détecte la première et la dernière colonne contenant du texte.
    C'est ICI que le DÉBUT et la FIN du texte sont reconnus.
    
    Principe :
    - On projette l'image binaire verticalement (somme des pixels blancs par colonne).
    - On normalise par la hauteur pour obtenir une proportion de blancs par colonne.
    - On lisse la courbe pour éviter les micro-variations.
    - On garde les colonnes où la proportion > seuil (3% par défaut).
    - La première et la dernière de ces colonnes donnent x_min et x_max.
    """
    h, w = binary.shape
    # Projection verticale : vecteur de taille w
    col_density = binary.sum(axis=0) / (255*h)
    # Lissage avec une fenêtre de 5 pixels
    col_density = np.convolve(col_density, np.ones(5)/5, mode='same')
    # Colonnes significatives (contenant assez de blanc)
    cols_with_text = np.where(col_density > col_threshold)[0]
    if len(cols_with_text) == 0:
        raise ValueError("Aucune colonne contenant du texte détectée.")
    x_min = cols_with_text[0]   # PREMIÈRE colonne de texte
    x_max = cols_with_text[-1]  # DERNIÈRE colonne de texte
    return int(x_min), int(x_max)

def _find_gutter_from_density(density, x_min, x_max):
    """
    Trouve la colonne de densité minimale (gouttière) dans la zone centrale
    définie entre 35% et 65% de la largeur du texte.
    """
    w = x_max - x_min
    lo = x_min + int(w * 0.35)
    hi = x_min + int(w * 0.65)
    lo = max(lo, x_min + 5)
    hi = min(hi, x_max - 5)
    return lo + int(np.argmin(density[lo:hi]))

# ──────────────────────────────────────────────────────────────────────────────
# 2. FONCTION PRINCIPALE
# ──────────────────────────────────────────────────────────────────────────────


# ... (garder toutes les fonctions existantes : _load_image, _binarize, _fast_denoise,
#      _apply_global_margins, _get_text_boundaries_x, _find_gutter_from_density,
#      measure_text_width_with_margin)

def normal_split(image_path, dest_path, margin=50,
                 horiz_margin_percent=0.08, vert_margin_percent=0.1):
    """
    Ancienne logique de split_book (découpage systématique en deux pages).
    """
    os.makedirs(dest_path, exist_ok=True)

    bgr, gray = _load_image(image_path)
    img_h, img_w = gray.shape

    binary_raw = _binarize(gray)
    binary = _fast_denoise(binary_raw)

    x_start, x_end, y_start, y_end = _apply_global_margins(
        img_w, img_h, horiz_margin_percent, vert_margin_percent
    )

    binary_central = binary[y_start:y_end, x_start:x_end]
    try:
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.025)
        x_min_abs = x_start + x_min_rel
        x_max_abs = x_start + x_max_rel
    except ValueError as e:
        print(f"⚠️ Erreur détection texte : {e}. Utilisation de toute la zone centrale.")
        x_min_abs = x_start
        x_max_abs = x_end


    binary_text = binary[y_start:y_end, x_min_abs:x_max_abs]
    density = binary_text.sum(axis=0).astype(np.float32)
    window = max(5, int(len(density) * 0.02))
    density = np.convolve(density, np.ones(window)/window, mode='same')

    mid_local = _find_gutter_from_density(density, 0, len(density))
    gutter_x = x_min_abs + mid_local

    left_x_start = max(0, x_min_abs - margin)
    left_x_end   = min(img_w, gutter_x + margin)
    right_x_start = max(0, gutter_x - margin)
    right_x_end   = min(x_max_abs + margin, img_w)
    margin_v = 0.05 * img_h
    y_start2 = int(margin_v)
    y_end2 = int(img_h - margin_v)

    left_img  = bgr[y_start2:y_end2, left_x_start:left_x_end]
    right_img = bgr[y_start2:y_end2, right_x_start:right_x_end]

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    left_path  = os.path.join(dest_path, f"{base_name}_gauche.jpg")
    right_path = os.path.join(dest_path, f"{base_name}_droite.jpg")

    cv2.imwrite(left_path, left_img)
    cv2.imwrite(right_path, right_img)

    return left_path, right_path


def image_with_blank_split(image_path, dest_path, ref_text_width, margin=50,
                           horiz_margin_percent=0.08, vert_margin_percent=0.04):
    """
    Extrait une seule page (gauche ou droite) à partir d'une image où l'autre page est blanche.
    La détection du côté se fait par la position de la zone de texte par rapport au centre.
    """
    os.makedirs(dest_path, exist_ok=True)
    bgr, gray = _load_image(image_path)
    img_h, img_w = gray.shape

    binary_raw = _binarize(gray)
    binary = _fast_denoise(binary_raw)

    # Suppression des bords du livre
    x_start, x_end, y_start, y_end = _apply_global_margins(
        img_w, img_h, horiz_margin_percent, vert_margin_percent
    )
    binary_central = binary[y_start:y_end, x_start:x_end]
    try:
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.025)
        x_min_abs = x_start + x_min_rel
        x_max_abs = x_start + x_max_rel
    except ValueError:
        # Fallback : utiliser toute la zone centrale
        x_min_abs = x_start
        x_max_abs = x_end

    # Centre de la zone de texte
    text_center = (x_min_abs + x_max_abs) // 2
    image_center = img_w // 2

    # Marge verticale
    margin_v = int(0.05 * img_h)
    y_start2 = margin_v
    y_end2 = img_h - margin_v

    if text_center < image_center:
        # Page gauche : le texte est à gauche, on prend une région de largeur ref_text_width
        # à partir de x_min_abs (bord gauche du texte) vers la droite
        left = max(0, x_min_abs - margin)
        right = min(img_w, left + ref_text_width)
        # Ajustement si on dépasse
        if right - left < ref_text_width:
            right = min(img_w, left + ref_text_width)
    else:
        # Page droite : le texte est à droite, on prend une région de largeur ref_text_width
        # se terminant à x_max_abs (bord droit du texte)
        right = min(img_w, x_max_abs + margin)
        left = max(0, right - ref_text_width)

    single_img = bgr[y_start2:y_end2, left:right]
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    out_path = os.path.join(dest_path, f"{base_name}_simple.jpg")
    cv2.imwrite(out_path, single_img)
    return out_path


def partial_split(image_path, dest_path, ref_text_width, margin=50,
                  horiz_margin_percent=0.08, vert_margin_percent=0.04):
    os.makedirs(dest_path, exist_ok=True)
    bgr, gray = _load_image(image_path)
    img_h, img_w = gray.shape

    # 1. Détection des limites du texte pour trouver le "centre optique" du livre
    binary_raw = _binarize(gray)
    binary = _fast_denoise(binary_raw)
    x_start, x_end, y_start, y_end = _apply_global_margins(
        img_w, img_h, horiz_margin_percent, vert_margin_percent
    )
    
    binary_central = binary[y_start:y_end, x_start:x_end]
    try:
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.025)
        x_min_abs = x_start + x_min_rel
        x_max_abs = x_start + x_max_rel
    except ValueError:
        x_min_abs, x_max_abs = x_start, x_end

    # 2. Définition de la reliure (spine)
    # On utilise le milieu de la zone de texte totale comme point de séparation
    spine_x = (x_min_abs + x_max_abs) // 2
    
    # Largeur cible pour une seule page
    page_target_w = ref_text_width // 2 

    # 3. Calcul des coordonnées de découpe pour les deux pages
    # Page Gauche : du pivot vers la gauche
    l_left = max(0, spine_x - page_target_w)
    l_right = spine_x
    
    # Page Droite : du pivot vers la droite
    r_left = spine_x
    r_right = min(img_w, spine_x + page_target_w)

    # 4. Ajustement des hauteurs (pour avoir des pages propres)
    margin_v = int(vert_margin_percent * img_h)
    y_top = margin_v
    y_bottom = img_h - margin_v

    # Fonction interne pour extraire et "nettoyer" la page (padding si trop courte)
    def extract_and_pad(img, x1, x2, target_w):
        crop = img[y_top:y_bottom, x1:x2]
        current_h, current_w = crop.shape[:2]
        
        # Si la découpe est plus étroite que la cible (bord de l'image atteint)
        # on complète avec la couleur moyenne du bord (souvent la couleur du papier)
        if current_w < target_w:
            # On détermine si on doit ajouter à gauche ou à droite
            pad_color = np.median(crop[:, -5:], axis=(0, 1)).astype(np.uint8).tolist()
            if x1 == 0: # Manque à gauche
                pad_width = target_w - current_w
                crop = cv2.copyMakeBorder(crop, 0, 0, pad_width, 0, cv2.BORDER_CONSTANT, value=pad_color)
            else: # Manque à droite
                pad_width = target_w - current_w
                crop = cv2.copyMakeBorder(crop, 0, 0, 0, pad_width, cv2.BORDER_CONSTANT, value=pad_color)
        return crop

    # 5. Extraction finale
    left_page_img = extract_and_pad(bgr, l_left, l_right, page_target_w)
    right_page_img = extract_and_pad(bgr, r_left, r_right, page_target_w)

    # Sauvegarde
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    path_l = os.path.join(dest_path, f"{base_name}_L.jpg")
    path_r = os.path.join(dest_path, f"{base_name}_R.jpg")
    
    cv2.imwrite(path_l, left_page_img)
    cv2.imwrite(path_r, right_page_img)

    return path_l, path_r


def split_book(image_path, dest_path, margin=50,
               cover_width=None, ref_text_width=None,
               horiz_margin_percent=0.08, vert_margin_percent=0.1):
    """
    Contrôleur : décide du traitement en fonction de la largeur de texte mesurée.
    
    Paramètres :
        cover_width : largeur de l'image de couverture
        ref_text_width : largeur de texte de référence
    Si ces paramètres ne sont pas fournis, on applique normal_split (ancien comportement).
    """
    if cover_width is None or ref_text_width is None:
        # Comportement par défaut : split normal
        return normal_split(image_path, dest_path, margin,
                            horiz_margin_percent, vert_margin_percent)

    # Mesurer la largeur de texte de l'image courante
    text_width = measure_text_width_with_margin(image_path,
                                                horiz_margin_percent,
                                                vert_margin_percent)
    if text_width == 0:
        import shutil
        os.makedirs(dest_path, exist_ok=True)
        shutil.copy(image_path, dest_path)
        return image_path, None

    ratio = text_width / ref_text_width

    if ratio >= 0.9:
        print('split normal')
        return normal_split(image_path, dest_path, margin,
                            horiz_margin_percent, vert_margin_percent)
    elif ratio <= 0.45:
        print("→ Page avec zone blanche (une seule page)")
        return image_with_blank_split(image_path, dest_path, ref_text_width, margin,
                                      horiz_margin_percent, vert_margin_percent)
    else:
        print("→ Cas partiel")
        return partial_split(image_path, dest_path, margin)

# ──────────────────────────────────────────────────────────────────────────────
# 3. UTILITAIRES EXTERNES
# ──────────────────────────────────────────────────────────────────────────────

def measure_text_width_with_margin(image_path, horiz_margin_percent=0.08, vert_margin_percent=0.04):
    """
    Retourne la largeur de la zone de texte (en pixels) pour une image de page simple.
    Utilise les mêmes marges globales que split_book.
    """
    bgr, gray = _load_image(image_path)
    img_h, img_w = gray.shape
    
    binary_raw = _binarize(gray)
    binary = _fast_denoise(binary_raw) 
    
    x_start, x_end, y_start, y_end = _apply_global_margins(
        img_w, img_h, horiz_margin_percent, vert_margin_percent
    )
    binary_central = binary[y_start:y_end, x_start:x_end]
    try:
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.025)
        text_width = (x_max_rel - x_min_rel)*0.8
        return text_width
    except ValueError:
        return 0   # pas de texte détecté
    

def save_image(image_path, dest_path):
    bgr, gray = _load_image(image_path)

    img_h, img_w = gray.shape


    margin_v = int(0.05 * img_h)
    y_start2 = margin_v
    y_end2 = img_h - margin_v

    img = bgr[y_start2:y_end2, :]

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    path  = os.path.join(dest_path, f"{base_name}.jpg")

    cv2.imwrite(path, img)









'''
def split_book(image_path, dest_path, margin=50,
               horiz_margin_percent=0.08, vert_margin_percent=0.1):
    """
    Découpe un scan de livre ouvert en page gauche et page droite.

    Paramètres
    ----------
    image_path : str
    dest_path  : str
    margin     : int   — pixels de marge ajoutés autour de la gouttière
    horiz_margin_percent : float — pourcentage à enlever sur les côtés (défaut 0.08 = 8%)
    vert_margin_percent  : float — pourcentage à enlever en haut/bas (défaut 0.04 = 4%)
    """
    os.makedirs(dest_path, exist_ok=True)

    # 1. Chargement
    bgr, gray = _load_image(image_path)
    img_h, img_w = gray.shape

    # 2. Binarisation + débruitage rapide
    binary_raw = _binarize(gray)
    binary = _fast_denoise(binary_raw)

    binary_path = os.path.join(dest_path, os.path.basename(image_path).replace('.jpg', '_binary_raw.jpg'))
    #cv2.imwrite(binary_path, binary_raw)

    # 3. Suppression des bords du livre (marges globales)
    x_start, x_end, y_start, y_end = _apply_global_margins(
        img_w, img_h, horiz_margin_percent, vert_margin_percent
    )
    print(f"Zone centrale après suppression des bords :")
    print(f"  Horizontal : {horiz_margin_percent*100:.0f}% de chaque côté → x=[{x_start}, {x_end}]")
    print(f"  Vertical   : {vert_margin_percent*100:.0f}% en haut et en bas → y=[{y_start}, {y_end}]")

    # 4. Détection des limites horizontales du texte (début et fin du texte)
    #    On travaille sur la zone centrale (débarrassée des bordures du livre)
    binary_central = binary[y_start:y_end, x_start:x_end]
    try:
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.025)
        # Conversion en coordonnées absolues dans l'image entière
        x_min_abs = x_start + x_min_rel
        x_max_abs = x_start + x_max_rel
    except ValueError as e:
        print(f"⚠️ Erreur détection texte : {e}. Utilisation de toute la zone centrale.")
        x_min_abs = x_start
        x_max_abs = x_end

    print(f"RECONNAISSANCE : Début du texte à x = {x_min_abs}, fin du texte à x = {x_max_abs}")

    # 5. Recadrage de l'image binaire aux seules colonnes du texte (pour trouver la gouttière)
    binary_text = binary[y_start:y_end, x_min_abs:x_max_abs] 

    # 6. Calcul de la densité par colonne sur cette zone
    density = binary_text.sum(axis=0).astype(np.float32)
    window = max(5, int(len(density) * 0.02))
    density = np.convolve(density, np.ones(window)/window, mode='same')

    # 7. Trouver la gouttière (colonne de densité minimale)
    mid_local = _find_gutter_from_density(density, 0, len(density))
    gutter_x = x_min_abs + mid_local
    print(f"Gouttière détectée à x = {gutter_x}")

    # 8. Sauvegarde de l'image binaire (zone texte seule, pour débogage)
    binary_debug = binary[y_start:y_end, x_min_abs:x_max_abs]
    binary_path = os.path.join(dest_path, os.path.basename(image_path).replace('.jpg', '_binary.jpg'))
    #cv2.imwrite(binary_path, binary_debug)
    print(f"🧪 Binaire sauvegardé : {binary_path}")

    # 9. Découpage des deux pages dans l'image couleur
    #    On utilise les marges verticales (y_start, y_end) pour supprimer les bords haut/bas
    left_x_start = max(0, x_min_abs-margin)
    left_x_end   = min(img_w, gutter_x + margin)
    right_x_start = max(0, gutter_x - margin)
    right_x_end   = min(x_max_abs+margin, img_w)
    margin_v = 0.05 * img_h
    y_start = margin_v
    y_end   = img_h - margin_v

    left_img  = bgr[y_start:y_end, left_x_start:left_x_end]
    right_img = bgr[y_start:y_end, right_x_start:right_x_end]

    # 10. Sauvegarde finale
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    left_path  = os.path.join(dest_path, f"{base_name}_gauche.jpg")
    right_path = os.path.join(dest_path, f"{base_name}_droite.jpg")

    cv2.imwrite(left_path,  left_img)
    cv2.imwrite(right_path, right_img)

    print(f"✔ Page gauche → {left_path}  ({left_img.shape[1]} px)")
    print(f"✔ Page droite → {right_path} ({right_img.shape[1]} px)")

    return left_path, right_path
'''