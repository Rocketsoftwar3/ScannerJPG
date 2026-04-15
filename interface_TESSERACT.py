import recon_caract
import tkinter as tk
import tkinter.filedialog
import os
import subprocess
import image_split as ims

# Variable globale pour stocker le dossier de destination du découpage
dossier_decoupe = None

def analyse_fichiers():
    global dossier_decoupe
    if not nomRepertoire.get():
        tk.messagebox.showwarning("Avertissement", "Aucun répertoire sélectionné.")
        return

    ref = ref_width.get()
    if ref <= 0:
        tk.messagebox.showwarning("Avertissement", "Veuillez d'abord choisir une image type valide.")
        return

    a = recon_caract.ouverture_pdf(nomRepertoire.get(), ref)
    if a:
        tk.messagebox.showinfo("PDF crée","Le PDF a été créé ")
    if suprFichiers.get():
        recon_caract.suprimer_fichiers(nomRepertoire.get())
    if ouvrirPDF.get():
        subprocess.Popen([os.path.join(nomRepertoire.get(), "Livre_numérique.pdf")], shell=True)

    if a:
        tk.messagebox.showinfo("PDF créé", "Le PDF a été créé avec succès.")
    else:
        tk.messagebox.showerror("Erreur", "La création du PDF a échoué.")
        return

    # 3. Suppression facultative des images (dans le dossier découpé)
    if suprFichiers.get():
        try:
            recon_caract.suprimer_fichiers(dossier_decoupe)
        except Exception as e:
            tk.messagebox.showwarning("Attention", f"Suppression partielle : {e}")

    # 4. Ouverture automatique du PDF
    if ouvrirPDF.get():
        pdf_path = os.path.join(dossier_decoupe, "Livre_numérique.pdf")
        if os.path.exists(pdf_path):
            subprocess.Popen([pdf_path], shell=True)
        else:
            tk.messagebox.showerror("Erreur", "PDF introuvable après conversion.")

def choisir_fichier_type():
    """Ouvre une boîte de dialogue pour choisir une image type dans le répertoire sélectionné."""
    rep = nomRepertoire.get()
    if not rep:
        tk.messagebox.showwarning("Attention", "Veuillez d'abord sélectionner un répertoire.")
        return

    file_path = tk.filedialog.askopenfilename(
        title="Choisir une image de page simple (type)",
        initialdir=rep,
        filetypes=[("Fichiers JPG", "*.jpg")]
    )
    if file_path:
        # Vérifier que le fichier est bien dans le répertoire (ou un sous-dossier)
        if not os.path.abspath(file_path).startswith(os.path.abspath(rep)):
            tk.messagebox.showwarning("Attention", "L'image type doit se trouver dans le répertoire sélectionné (ou un sous-dossier).")
            return
        width = ims.measure_text_width_with_margin(file_path)
        if width > 0:
            ref_width.set(width)
            label_ref.config(text=f"Largeur de référence : {width} px")
            # Activer le bouton de conversion
            btn_convert.config(state=tk.NORMAL)
        else:
            tk.messagebox.showwarning("Erreur", "Aucun texte détecté dans l'image type.")
            ref_width.set(0)
            label_ref.config(text="Aucune référence valide")
            btn_convert.config(state=tk.DISABLED)
    else:
        ref_width.set(0)
        label_ref.config(text="Aucune référence")
        btn_convert.config(state=tk.DISABLED)

def choix_repertoire():
    rep = tk.filedialog.askdirectory(
        initialdir="/",
        title="Sélectionnez un répertoire"
    )
    if rep:
        nomRepertoire.set(rep)
        nomAffiche.set(os.path.basename(rep))
        # Réinitialiser la référence car le répertoire change
        ref_width.set(0)
        label_ref.config(text="Aucune référence sélectionnée")
        btn_convert.config(state=tk.DISABLED)
        # Activer le bouton de choix du fichier type
        btn_type.config(state=tk.NORMAL)
    else:
        btn_type.config(state=tk.DISABLED)

if __name__ == "__main__":
    root = tk.Tk()

    nomRepertoire = tk.StringVar()
    nomAffiche = tk.StringVar()
    suprFichiers = tk.BooleanVar()
    ouvrirPDF = tk.BooleanVar()
    ref_width = tk.IntVar(value=0)

    root.title("Livre numérique")
    root.geometry("500x450")
    root.configure(bg="#f5f6fa")

    # Style
    FONT_TITLE = ("Helvetica", 18, "bold")
    FONT_TEXT = ("Helvetica", 11)
    BTN_STYLE = {
        "font": ("Helvetica", 10, "bold"),
        "bg": "#4a69bd",
        "fg": "white",
        "activebackground": "#1e3799",
        "activeforeground": "white",
        "bd": 0,
        "padx": 10,
        "pady": 8,
        "cursor": "hand2"
    }

    # Layout
    frame = tk.Frame(root, bg="#f5f6fa")
    frame.pack(expand=True)

    tk.Label(
        frame,
        text="Convertisseur JPG PDF",
        font=FONT_TITLE,
        bg="#f5f6fa",
        fg="#2f3640"
    ).pack(pady=(20, 10))

    tk.Label(
        frame,
        text="Seuls les fichiers JPG seront convertis.",
        font=FONT_TEXT,
        bg="#f5f6fa",
        fg="#636e72"
    ).pack(pady=(0, 20))

    # Bouton répertoire
    tk.Button(
        frame,
        text="Choisir un répertoire",
        command=choix_repertoire,
        **BTN_STYLE
    ).pack(pady=10)

    tk.Label(
        frame,
        textvariable=nomAffiche,
        font=("Helvetica", 10, "italic"),
        bg="#f5f6fa",
        fg="#2d3436"
    ).pack(pady=10)

    # Bouton image type (désactivé au départ)
    btn_type = tk.Button(
        frame,
        text="Choisir une image type (page simple)",
        command=choisir_fichier_type,
        font=("Helvetica", 10),
        bg="#f39c12",
        fg="white",
        padx=10,
        pady=5,
        cursor="hand2",
        state=tk.DISABLED
    )
    btn_type.pack(pady=5)

    label_ref = tk.Label(
        frame,
        text="Aucune référence sélectionnée",
        font=FONT_TEXT,
        bg="#f5f6fa",
        fg="#e67e22"
    )
    label_ref.pack(pady=(0, 15))

    # Bouton conversion (désactivé au départ)
    btn_convert = tk.Button(
        frame,
        text="Convertir en PDF",
        command=analyse_fichiers,
        font=("Helvetica", 11, "bold"),
        bg="#20bf6b",
        fg="white",
        activebackground="#0fb9b1",
        bd=0,
        padx=15,
        pady=10,
        cursor="hand2",
        state=tk.DISABLED
    )
    btn_convert.pack(pady=20)

    # Checkboxes
    tk.Checkbutton(
        frame,
        text="Supprimer les images après conversion",
        variable=suprFichiers,
        bg="#f5f6fa",
        fg="#636e72",
        font=FONT_TEXT
    ).pack(pady=5)

    tk.Checkbutton(
        frame,
        text="Ouvrir le PDF après conversion",
        variable=ouvrirPDF,
        bg="#f5f6fa",
        fg="#636e72",
        font=FONT_TEXT
    ).pack(pady=5)

    root.mainloop()