# patch_zeanalyser_safe_recos.py
import io, os, re, sys

TARGET = os.path.join(os.path.dirname(__file__), "analyse_gui.py")

def read_text(p):
    with io.open(p, "r", encoding="utf-8") as f:
        return f.read()

def write_text(p, s):
    with io.open(p, "w", encoding="utf-8", newline="\n") as f:
        f.write(s)

code = read_text(TARGET)

# ---------- 1) Durcir update_starcount_slider_state() ----------
# We wrap the final "update_recos()" call in a try/except tk.TclError
def wrap_update_starcount(m):
    body = m.group(0)
    # already patched?
    if "try:\n                    update_recos()" in body or "try:\n                        update_recos()" in body:
        return body
    # replace the *last* 'update_recos()' inside this function
    new_body = re.sub(
        r"(\bupdate_starcount_slider_state\(\):.*?)(\n\s*)update_recos\(\)",
        r"\1\2try:\n\2    update_recos()\n\2except tk.TclError:\n\2    return",
        body,
        flags=re.DOTALL
    )
    return new_body

code = re.sub(
    r"def\s+update_starcount_slider_state\(\):.*?^\s*\n",
    wrap_update_starcount,
    code,
    flags=re.DOTALL | re.MULTILINE
)

# ---------- 2) Remplacer entièrement le corps de update_recos() par une version robuste ----------
safe_update_recos_body = r"""
def update_recos():
    import numpy as np, tkinter as tk
    try:
        recos, snr_p, fwhm_p, ecc_p, sc_p = self._compute_recommended_subset()

        txt = self._("visu_recom_text_all", count=len(recos))
        if txt.startswith("_visu_recom_text_all_"):
            txt = f"Images recommandées : {len(recos)}"
        if snr_p is not None and is_finite_number(snr_p):
            txt += f"  |  SNR ≥ {snr_p:.2f}"
        if fwhm_p is not None and is_finite_number(fwhm_p):
            txt += f"  |  FWHM ≤ {fwhm_p:.2f}"
        if ecc_p is not None and is_finite_number(ecc_p):
            txt += f"  |  e ≤ {ecc_p:.3f}"
        if self.use_starcount_filter.get() and sc_p is not None and is_finite_number(sc_p):
            txt += f"  |  Starcount ≥ {sc_p:.0f}"
        resume_var.set(txt)

        # Clear Treeview safely
        try:
            items = rec_tree.get_children()
        except tk.TclError:
            return
        for iid in items:
            try:
                rec_tree.delete(iid)
            except tk.TclError:
                # If the widget dies mid-loop, just stop updating.
                return

        # Refill Treeview safely
        for r in recos:
            vals = (
                r.get('rel_path', os.path.basename(r.get('file', '?'))),
                f"{r.get('snr', 0):.2f}" if is_finite_number(r.get('snr', np.nan)) else "N/A",
                f"{r.get('fwhm', 0):.2f}" if is_finite_number(r.get('fwhm', np.nan)) else "N/A",
                f"{r.get('ecc', 0):.3f}" if is_finite_number(r.get('ecc', np.nan)) else "N/A",
                f"{r.get('starcount', 0):.0f}" if is_finite_number(r.get('starcount', np.nan)) else "N/A",
            )
            try:
                rec_tree.insert("", tk.END, values=vals)
            except tk.TclError:
                return

        state = tk.NORMAL if recos else tk.DISABLED

        # Buttons may already be destroyed: guard each call
        try:
            if self.apply_reco_button and self.apply_reco_button.winfo_exists():
                self.apply_reco_button.config(state=state)
        except tk.TclError:
            pass

        try:
            if hasattr(self, 'visual_apply_reco_button') and self.visual_apply_reco_button and self.visual_apply_reco_button.winfo_exists():
                self.visual_apply_reco_button.config(state=state)
        except tk.TclError:
            pass

        try:
            if self.main_apply_reco_button and self.main_apply_reco_button.winfo_exists():
                self.main_apply_reco_button.config(state=state)
        except tk.TclError:
            pass

    except tk.TclError:
        # Any late callback hitting a dead widget should just no-op.
        return
"""

# Replace the inner function body between "def update_recos():" and the end of that def block.
def replace_update_recos(match):
    # Keep original indentation level for def line
    def_line = match.group(1)
    indent = re.match(r"(\s*)def", def_line).group(1)
    # Indent our safe body to the same level
    safe_body_indented = "\n".join(
        (indent + line if line.strip() else line)
        for line in safe_update_recos_body.strip("\n").splitlines()
    ) + "\n"
    return safe_body_indented

code = re.sub(
    r"(^\s*def\s+update_recos\(\):)(.*?)(?=^\s*def\s+\w+\(|^\s*update_starcount_slider_state\(\)|^\s*#|\Z)",
    replace_update_recos,
    code,
    flags=re.DOTALL | re.MULTILINE
)

# ---------- 3) Sauvegarde ----------
write_text(TARGET, code)
print("Patch applied successfully to analyse_gui.py")
