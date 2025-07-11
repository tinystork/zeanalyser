# zeanalyser
Gui based Zesee Star Zenalalyser is a standalone analysis module for a lot of light, sorting and filtering ‘Lights’ files to discard low-quality frames and yield optimal star-field composites.available in Zeseestarstacker

## Usage / Utilisation

**English**

1. Create a virtual environment and activate it:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

3. Launch the graphical interface:

   ```bash
   python analyse_gui.py
   ```

**Français**

1. Créez un environnement virtuel et activez-le&nbsp;:

   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   ```

2. Installez les dépendances&nbsp;:

   ```bash
   pip install -r requirements.txt
   ```

3. Lancez l'interface graphique&nbsp;:

   ```bash
   python analyse_gui.py
   ```

## Bortle Classification

When using the helper functions in `bortle_utils.py`, make sure to convert
sky luminance expressed in **µcd/m²** to SQM (mag/arcsec²) before calling
`sqm_to_bortle`. The typical workflow is:

```python
l_ucd = sample_bortle_dataset(dataset, lon, lat)
sqm = ucd_to_sqm(l_ucd)
bortle_class = sqm_to_bortle(sqm)
```

Failing to perform the conversion will result in systematically obtaining a
Bortle class of 1, even with very bright skies.

The Bortle analysis relies on the dataset by:
Falchi, Fabio; Cinzano, Pierantonio; Duriscoe, Dan; Kyba, Christopher C. M.; Elvidge, Christopher D.; Baugh, Kimberly; Portnov, Boris; Rybnikova, Nataliya A.; Furgoni, Riccardo (2016): *Supplement to: The New World Atlas of Artificial Night Sky Brightness. V. 1.1.* GFZ Data Services. <https://doi.org/10.5880/GFZ.1.4.2016.001>
(study: <https://www.science.org/doi/10.1126/sciadv.1600377>). Download their raster to classify your data by Bortle.

L'analyse Bortle repose sur le jeu de données de :
Falchi, Fabio; Cinzano, Pierantonio; Duriscoe, Dan; Kyba, Christopher C. M.; Elvidge, Christopher D.; Baugh, Kimberly; Portnov, Boris; Rybnikova, Nataliya A.; Furgoni, Riccardo (2016) : *Supplement to: The New World Atlas of Artificial Night Sky Brightness. V. 1.1.* GFZ Data Services. <https://doi.org/10.5880/GFZ.1.4.2016.001>
(étude : <https://www.science.org/doi/10.1126/sciadv.1600377>). Il faut télécharger ce raster pour pouvoir classer les données par Bortle.

