# zeanalyser
Gui based Zesee Star Zenalalyser is a standalone analysis module for a lot of light, sorting and filtering ‘Lights’ files to discard low-quality frames and yield optimal star-field composites.available in Zeseestarstacker

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
