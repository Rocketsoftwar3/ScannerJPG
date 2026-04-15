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

CORRECTION v2 : détection de gouttière robuste même sur pages peu ou pas textualisées,
via une stratégie hybride combinant bords verticaux (Sobel X), minimum de luminosité,
et densité de texte — pondérés selon le niveau de texte présent.
"""

import os
import numpy as np
import cv2
from scipy import ndimage

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
    kernel = np.ones((4, 4), np.uint8)
    denoised = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)

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


def _get_text_boundaries_x(binary, col_threshold=0.002):
    """
    Détecte la première et la dernière colonne contenant du texte.
    """
    h, w = binary.shape
    col_density = binary.sum(axis=0) / (255 * h)
    col_density = np.convolve(col_density, np.ones(5) / 5, mode='same')
    cols_with_text = np.where(col_density > col_threshold)[0]
    if len(cols_with_text) == 0:
        raise ValueError("Aucune colonne contenant du texte détectée.")
    x_min = cols_with_text[0]
    x_max = cols_with_text[-1]
    return int(x_min), int(x_max)


def _find_gutter_from_density(density, x_min, x_max):
    """
    Trouve la colonne de densité minimale (gouttière) dans la zone centrale
    définie entre 35% et 65% de la largeur du texte.
    (Méthode originale — utilisée en interne par normal_split quand le texte est dense.)
    """
    w = x_max - x_min
    lo = x_min + int(w * 0.35)
    hi = x_min + int(w * 0.65)
    lo = max(lo, x_min + 5)
    hi = min(hi, x_max - 5)
    return lo + int(np.argmin(density[lo:hi]))


def _find_gutter_robust(gray, search_lo_frac=0.25, search_hi_frac=0.75):
    """
    Détecte la gouttière (reliure) de façon robuste, même sur des pages peu ou
    pas textualisées (pages de titre, illustrations, pages quasi-vierges).

    Combine trois signaux normalisés, pondérés selon le niveau de texte :

    1. Bords verticaux continus (Sobel X) :
       La reliure crée un bord vertical fort et continu sur toute la hauteur.
       Ce signal est très fiable même sans texte.

    2. Minimum de luminosité :
       La reliure est souvent légèrement plus sombre que le papier (ombre de courbure).

    3. Minimum de densité de texte (méthode classique) :
       Fiable quand le texte est dense ; la gouttière est la vallée entre les deux blocs.

    La pondération est adaptative :
    - Pages peu textualisées (text_ratio < 0.04) → Sobel X dominant
    - Pages denses (text_ratio > 0.08)           → densité de texte dominante
    - Entre les deux                             → interpolation continue

    Paramètres
    ----------
    gray             : image en niveaux de gris (np.ndarray)
    search_lo_frac   : fraction gauche de la zone de recherche (défaut 0.25)
    search_hi_frac   : fraction droite de la zone de recherche (défaut 0.75)

    Retourne
    --------
    gutter_x : int — position x absolue de la gouttière dans l'image
    """
    h, w = gray.shape
    lo = int(w * search_lo_frac)
    hi = int(w * search_hi_frac)

    # ── Signal 1 : bords verticaux (Sobel X cumulé par colonne)
    sobelx = cv2.Sobel(gray, cv2.CV_64F, 1, 0, ksize=3)
    col_sobelx = np.abs(sobelx).sum(axis=0).astype(np.float32)
    col_sobelx_smooth = ndimage.gaussian_filter1d(col_sobelx, sigma=4)
    zone_s = col_sobelx_smooth[lo:hi]
    if zone_s.max() > zone_s.min():
        zone_s_norm = (zone_s - zone_s.min()) / (zone_s.max() - zone_s.min())
    else:
        zone_s_norm = np.zeros_like(zone_s)

    # ── Signal 2 : minimum de luminosité (zone sombre = ombre de reliure)
    col_brightness = gray.mean(axis=0).astype(np.float32)
    col_brightness_smooth = ndimage.gaussian_filter1d(col_brightness, sigma=4)
    zone_b = col_brightness_smooth[lo:hi]
    if zone_b.max() > zone_b.min():
        # Inverser : bas de luminosité → score élevé
        zone_b_norm = 1.0 - (zone_b - zone_b.min()) / (zone_b.max() - zone_b.min())
    else:
        zone_b_norm = np.zeros_like(zone_b)

    # ── Signal 3 : densité de texte (minimum = gouttière)
    binary = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                   cv2.THRESH_BINARY_INV, 51, 15)
    kernel = np.ones((4, 4), np.uint8)
    binary = cv2.morphologyEx(binary, cv2.MORPH_OPEN, kernel)
    col_density = binary.sum(axis=0).astype(np.float32) / (255 * h)
    window = max(5, int(w * 0.02))
    col_density_smooth = np.convolve(col_density, np.ones(window) / window, mode='same')
    zone_d = col_density_smooth[lo:hi]

    # ── Nouvel algorithme de score : Exclure fermement le texte
    # Centralité (prioriser le centre de l'image pour départager)
    x_indices = np.arange(lo, hi)
    center_x = w / 2.0
    sigma_center = w * 0.15
    zone_c = np.exp(-0.5 * ((x_indices - center_x) / sigma_center) ** 2)

    # Répression du texte : s'effondre très vite si la densité de texte dépasse le minimum local.
    # Garantit que la gouttière est cherchée UNIQUEMENT dans l'espace sans texte.
    text_suppression = np.exp(-(zone_d - zone_d.min()) * 150.0)

    score = (0.4 * zone_s_norm + 0.4 * zone_b_norm + 0.2 * zone_c) * text_suppression

    gutter_local = int(np.argmax(score))
    gutter_abs = lo + gutter_local
    return gutter_abs


# ──────────────────────────────────────────────────────────────────────────────
# 2. FONCTIONS PRINCIPALES
# ──────────────────────────────────────────────────────────────────────────────

def normal_split(image_path, dest_path, margin=50,
                 horiz_margin_percent=0.08, vert_margin_percent=0.1):
    """
    Split standard : découpe systématiquement en deux pages gauche/droite.
    Utilise la détection de gouttière ROBUSTE (fonctionne même pages peu textualisées).
    """
    os.makedirs(dest_path, exist_ok=True)

    bgr, gray = _load_image(image_path)
    img_h, img_w = gray.shape

    binary_raw = _binarize(gray)
    binary = _fast_denoise(binary_raw)

    x_start, x_end, y_start, y_end = _apply_global_margins(
        img_w, img_h, horiz_margin_percent, vert_margin_percent
    )

    # ── Bornes du texte (pour cadrer la découpe finale)
    binary_central = binary[y_start:y_end, x_start:x_end]
    try:
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.002)
        x_min_abs = x_start + x_min_rel
        x_max_abs = x_start + x_max_rel
    except ValueError:
        x_min_abs = x_start
        x_max_abs = x_end

    # ── Détection robuste de la gouttière (zone 25%-75% de l'image)
    gutter_x = _find_gutter_robust(gray, search_lo_frac=0.25, search_hi_frac=0.75)

    # ── Découpage
    left_x_start  = max(0, x_min_abs - margin)
    left_x_end    = min(img_w, gutter_x + margin)
    right_x_start = max(0, gutter_x - margin)
    right_x_end   = min(x_max_abs + margin, img_w)

    margin_v  = int(0.05 * img_h)
    y_start2  = margin_v
    y_end2    = img_h - margin_v

    left_img  = bgr[y_start2:y_end2, left_x_start:left_x_end]
    right_img = bgr[y_start2:y_end2, right_x_start:right_x_end]

    base_name  = os.path.splitext(os.path.basename(image_path))[0]
    left_path  = os.path.join(dest_path, f"{base_name}_gauche.jpg")
    right_path = os.path.join(dest_path, f"{base_name}_droite.jpg")

    cv2.imwrite(left_path,  left_img)
    cv2.imwrite(right_path, right_img)

    return left_path, right_path


def image_with_blank_split(image_path, dest_path, ref_text_width, margin=50,
                           horiz_margin_percent=0.08, vert_margin_percent=0.04):
    """
    Extrait une seule page (gauche ou droite) à partir d'une image où l'autre page
    est blanche. La détection du côté se fait par la position de la zone de texte
    par rapport au centre.
    Si aucun texte n'est détecté, on se rabat sur la moitié gauche ou droite selon
    la position du minimum de luminosité (ombre de reliure).
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
    gutter_x = _find_gutter_robust(gray, search_lo_frac=0.25, search_hi_frac=0.75)

    try:
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.002)
        x_min_abs = x_start + x_min_rel
        x_max_abs = x_start + x_max_rel
        text_center = (x_min_abs + x_max_abs) // 2
    except ValueError:
        # Aucun texte détecté : utiliser la gouttière robuste pour deviner le côté
        text_center = img_w // 4  # on suppose page gauche par défaut
        x_min_abs = x_start
        x_max_abs = gutter_x

    margin_v = int(0.05 * img_h)
    y_start2 = margin_v
    y_end2   = img_h - margin_v

    if text_center < gutter_x:
        left  = max(0, x_min_abs - margin)
        right = min(img_w, gutter_x + margin)
    else:
        right = min(img_w, x_max_abs + margin)
        left  = max(0, gutter_x - margin)

    single_img = bgr[y_start2:y_end2, left:right]
    base_name  = os.path.splitext(os.path.basename(image_path))[0]
    out_path   = os.path.join(dest_path, f"{base_name}_simple.jpg")
    cv2.imwrite(out_path, single_img)
    return out_path


def partial_split(image_path, dest_path, ref_text_width, margin=50,
                  horiz_margin_percent=0.08, vert_margin_percent=0.04):
    """
    Cas partiel : une page est nettement plus petite que la référence.
    Utilise la gouttière robuste comme pivot central.
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
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.002)
        x_min_abs = x_start + x_min_rel
        x_max_abs = x_start + x_max_rel
    except ValueError:
        x_min_abs = x_start
        x_max_abs = x_end

    # ── Gouttière robuste (pivot)
    gutter_x = _find_gutter_robust(gray, search_lo_frac=0.25, search_hi_frac=0.75)

    page_target_w = ref_text_width // 2

    l_left  = max(0, min(gutter_x - page_target_w, x_min_abs - margin))
    l_right = min(img_w, gutter_x + margin)
    r_left  = max(0, gutter_x - margin)
    r_right = min(img_w, max(gutter_x + page_target_w, x_max_abs + margin))

    margin_v = int(vert_margin_percent * img_h)
    y_top    = margin_v
    y_bottom = img_h - margin_v

    def extract_and_pad(img, x1, x2, target_w):
        crop = img[y_top:y_bottom, x1:x2]
        current_h, current_w = crop.shape[:2]
        if current_w < target_w:
            pad_color = np.median(crop[:, -5:], axis=(0, 1)).astype(np.uint8).tolist()
            if x1 == 0:
                pad_width = target_w - current_w
                crop = cv2.copyMakeBorder(crop, 0, 0, pad_width, 0,
                                          cv2.BORDER_CONSTANT, value=pad_color)
            else:
                pad_width = target_w - current_w
                crop = cv2.copyMakeBorder(crop, 0, 0, 0, pad_width,
                                          cv2.BORDER_CONSTANT, value=pad_color)
        return crop

    left_page_img  = extract_and_pad(bgr, l_left, l_right, page_target_w)
    right_page_img = extract_and_pad(bgr, r_left, r_right, page_target_w)

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
        cover_width     : largeur de l'image de couverture
        ref_text_width  : largeur de texte de référence
    Si ces paramètres ne sont pas fournis, on applique normal_split (comportement par défaut).
    """
    if cover_width is None or ref_text_width is None:
        return normal_split(image_path, dest_path, margin,
                            horiz_margin_percent, vert_margin_percent)

    text_width = measure_text_width_with_margin(image_path,
                                                horiz_margin_percent,
                                                vert_margin_percent)
    if text_width == 0:
        # Aucun texte détecté : on tente quand même un split visuel
        print("⚠️ Aucun texte détecté — split par gouttière visuelle")
        return normal_split(image_path, dest_path, margin,
                            horiz_margin_percent, vert_margin_percent)

    ratio = text_width / ref_text_width

    if ratio >= 0.9:
        print('→ Split normal (double page dense)')
        return normal_split(image_path, dest_path, margin,
                            horiz_margin_percent, vert_margin_percent)
    elif ratio <= 0.45:
        print("→ Page avec zone blanche (une seule page)")
        return image_with_blank_split(image_path, dest_path, ref_text_width, margin,
                                      horiz_margin_percent, vert_margin_percent)
    else:
        print("→ Cas partiel")
        return partial_split(image_path, dest_path, ref_text_width, margin,
                             horiz_margin_percent, vert_margin_percent)


# ──────────────────────────────────────────────────────────────────────────────
# 3. UTILITAIRES EXTERNES
# ──────────────────────────────────────────────────────────────────────────────

def measure_text_width_with_margin(image_path,
                                   horiz_margin_percent=0.08,
                                   vert_margin_percent=0.04):
    """
    Retourne la largeur de la zone de texte (en pixels) pour une image de page simple.
    Retourne 0 si aucun texte n'est détecté (pages vierges, illustrations…).
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
        x_min_rel, x_max_rel = _get_text_boundaries_x(binary_central, col_threshold=0.002)
        text_width = (x_max_rel - x_min_rel) * 0.8
        return text_width
    except ValueError:
        return 0  # pas de texte détecté


def save_image(image_path, dest_path):
    bgr, gray = _load_image(image_path)
    img_h, img_w = gray.shape

    margin_v = int(0.05 * img_h)
    y_start2 = margin_v
    y_end2   = img_h - margin_v

    img = bgr[y_start2:y_end2, :]

    base_name = os.path.splitext(os.path.basename(image_path))[0]
    path = os.path.join(dest_path, f"{base_name}.jpg")
    cv2.imwrite(path, img)