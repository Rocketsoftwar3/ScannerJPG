import recon_caract
import tkinter as tk
import tkinter.filedialog
import os
import subprocess

def analyse_fichiers():
    if nomRepertoire.get():
        a = recon_caract.ouverture_pdf(nomRepertoire.get())
        if a:
            tk.messagebox.showinfo("PDF crée","Le PDF a été créé ")
        if suprFichiers.get():
            recon_caract.suprimer_fichiers(nomRepertoire.get())
        if ouvrirPDF.get():
            subprocess.Popen([os.path.join(nomRepertoire.get(), "Livre_numérique.pdf")], shell=True)
    else:
        tk.messagebox.showwarning("Avertissement","Aucun répertoire sélectionné")

def choix_repertoire():
    rep = tkinter.filedialog.askdirectory(
        initialdir="/",
        title="Sélectionnez un répertoire"
    )
    
    nomRepertoire.set(rep)
    nomAffiche.set(os.path.basename(rep))
if __name__ == "__main__":

    root = tk.Tk()

    nomRepertoire = tk.StringVar()
    nomAffiche = tk.StringVar()
    suprFichiers = tk.BooleanVar()
    ouvrirPDF = tk.BooleanVar()

    root.title("Livre numérique")
    root.geometry("500x400")
    root.configure(bg="#f5f6fa")

    #Style
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

    #Layout
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

    tk.Button(
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
        cursor="hand2"
    ).pack(pady=20)

    tk.Checkbutton(
        frame,
        text="Supprimer les images après conversion",
        variable=suprFichiers,
        bg="#f5f6fa",
        fg="#636e72",
        font=FONT_TEXT
    ).pack(pady=10)

    tk.Checkbutton(
        frame,
        text="Ouvrir le PDF après conversion",
        variable=ouvrirPDF,
        bg="#f5f6fa",
        fg="#636e72",
        font=FONT_TEXT
    ).pack(pady=10)



    root.mainloop()