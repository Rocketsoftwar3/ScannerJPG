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
    print(col_density)
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

    left_img  = bgr[:, left_x_start:left_x_end]
    right_img = bgr[:, right_x_start:right_x_end]

    # 10. Sauvegarde finale
    base_name = os.path.splitext(os.path.basename(image_path))[0]
    left_path  = os.path.join(dest_path, f"{base_name}_gauche.jpg")
    right_path = os.path.join(dest_path, f"{base_name}_droite.jpg")

    cv2.imwrite(left_path,  left_img)
    cv2.imwrite(right_path, right_img)

    print(f"✔ Page gauche → {left_path}  ({left_img.shape[1]} px)")
    print(f"✔ Page droite → {right_path} ({right_img.shape[1]} px)")

    return left_path, right_path

# ──────────────────────────────────────────────────────────────────────────────
# 3. APPEL
# ──────────────────────────────────────────────────────────────────────────────