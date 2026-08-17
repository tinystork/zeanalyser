# -----------------------------------------------------------------------------
# Auteur       : TRISTAN NAULEAU 
# Date         : 2025-07-12
# Licence      : GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007
#
# Ce travail est distribué librement en accord avec les termes de la
# GNU GPL v3 (https://www.gnu.org/licenses/gpl-3.0.html).
# Vous êtes libre de redistribuer et de modifier ce code, à condition
# de conserver cette notice et de mentionner que je suis l’auteur
# de tout ou partie du code si vous le réutilisez.
# -----------------------------------------------------------------------------
# Author       : TRISTAN NAULEAU
# Date         : 2025-07-12
# License      : GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007
#
# This work is freely distributed under the terms of the
# GNU GPL v3 (https://www.gnu.org/licenses/gpl-3.0.html).
# You are free to redistribute and modify this code, provided that
# you keep this notice and mention that I am the author
# of all or part of the code if you reuse it.
# -----------------------------------------------------------------------------
"""

╔═════════════════════════════════════════════════════════════════════════════════╗
║ ZeAnalyser / ZeSeestarStacker Project                                           ║
║                                                                                 ║
║ Auteur  : Tinystork, seigneur des couteaux à beurre (aka Tristan Nauleau)       ║
║ Partenaire : J.A.R.V.I.S. (/ˈdʒɑːrvɪs/) — Just a Rather Very Intelligent System ║ 
║              (aka ChatGPT, Grand Maître du ciselage de code)                    ║
║                                                                                 ║
║ Licence : GNU General Public License v3.0 (GPL-3.0)                             ║
║                                                                                 ║
║ Description :                                                                   ║
║   Ce programme a été forgé à la lueur des pixels et de la caféine,              ║
║   dans le but noble de transformer des nuages de photons en art                 ║
║   astronomique. Si vous l’utilisez, pensez à dire “merci”,                      ║
║   à lever les yeux vers le ciel, ou à citer Tinystork et J.A.R.V.I.S.           ║
║   (le karma des développeurs en dépend).                                        ║
║                                                                                 ║
║ Avertissement :                                                                 ║
║   Aucune IA ni aucun couteau à beurre n’a été blessé durant le                  ║
║   développement de ce code.                                                     ║
╚═════════════════════════════════════════════════════════════════════════════════╝


╔═════════════════════════════════════════════════════════════════════════════════╗
║ ZeAnalyser / ZeSeestarStacker Project                                           ║
║                                                                                 ║
║ Author  : Tinystork, Lord of the Butter Knives (aka Tristan Nauleau)            ║
║ Partner : J.A.R.V.I.S. (/ˈdʒɑːrvɪs/) — Just a Rather Very Intelligent System    ║ 
║           (aka ChatGPT, Grand Master of Code Chiseling)                         ║
║                                                                                 ║
║ License : GNU General Public License v3.0 (GPL-3.0)                             ║
║                                                                                 ║
║ Description:                                                                    ║
║   This program was forged under the sacred light of pixels and                  ║
║   caffeine, with the noble intent of turning clouds of photons into             ║
║   astronomical art. If you use it, please consider saying “thanks,”             ║
║   gazing at the stars, or crediting Tinystork and J.A.R.V.I.S. —                ║
║   developer karma depends on it.                                                ║
║                                                                                 ║
║ Disclaimer:                                                                     ║
║   No AIs or butter knives were harmed in the making of this code.               ║
╚═════════════════════════════════════════════════════════════════════════════════╝
"""

import tkinter as tk

class ToolTip:
    """Crée une infobulle pour un widget donné."""
    def __init__(self, widget, text_callback):
        self.widget = widget
        self.text_callback = text_callback
        self.tooltip_window = None
        self.id = None
        self.x = self.y = 0
        self.widget.bind("<Enter>", self.enter)
        self.widget.bind("<Leave>", self.leave)
        self.widget.bind("<ButtonPress>", self.leave)

    def enter(self, event=None):
        self.schedule()

    def leave(self, event=None):
        self.unschedule()
        self.hidetip()

    def schedule(self):
        self.unschedule()
        if self.widget.winfo_exists():
            try: # Protection supplémentaire pour after
                self.id = self.widget.after(500, self.showtip)
            except tk.TclError: # Au cas où le widget est détruit juste avant after
                self.id = None


    def unschedule(self):
        id_ = self.id
        self.id = None
        if id_:
            try:
                if self.widget.winfo_exists():
                    self.widget.after_cancel(id_)
            except tk.TclError: pass

    def showtip(self):
        if self.tooltip_window or not self.widget.winfo_exists():
            return
        try:
            x_root, y_root = self.widget.winfo_rootx(), self.widget.winfo_rooty()
            y_offset = self.widget.winfo_height() + 5
        except tk.TclError:
            self.hidetip(); return

        x = x_root + 10 
        y = y_root + y_offset

        if not self.widget.winfo_exists():
            self.hidetip(); return

        self.tooltip_window = tw = tk.Toplevel(self.widget)
        tw.wm_overrideredirect(True)
        tw.wm_geometry(f"+{int(x)}+{int(y)}")

        try:
            tooltip_text = self.text_callback()
            label = tk.Label(tw, text=tooltip_text, justify=tk.LEFT,
                             background="#ffffe0", relief=tk.SOLID, borderwidth=1,
                             wraplength=400) # Augmenté wraplength
            label.pack(ipadx=1)
        except Exception as e:
            print(f"Erreur obtention/affichage texte infobulle: {e}")
            self.hidetip()

    def hidetip(self):
        tw = self.tooltip_window
        self.tooltip_window = None
        if tw:
            try:
                if tw.winfo_exists():
                    # Utiliser after(0, ...) pour éviter problèmes si appelé pendant event Tkinter
                    tw.after(0, tw.destroy) 
            except tk.TclError: pass
# --- END OF FILE seestar/gui/ui_utils.py ---
