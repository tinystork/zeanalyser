import os
import sys
import numpy as np
import rasterio
from rasterio.transform import from_origin
import zipfile
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bortle_utils import load_bortle_raster, sqm_to_bortle, ucd_to_sqm, sample_bortle_dataset
from analyse_logic import _load_bortle_raster

def test_sqm_to_bortle(tmp_path):
    data = np.full((2, 2), 22.0, dtype=np.float32)
    transform = from_origin(0, 0, 1, 1)
    tif = tmp_path / "bortle.tif"
    with rasterio.open(tif, 'w', driver='GTiff', height=2, width=2, count=1, dtype='float32', transform=transform) as dst:
        dst.write(data, 1)
    ds = load_bortle_raster(str(tif))
    val = sample_bortle_dataset(ds, 0.0, 0.0)
    cls = sqm_to_bortle(float(val))
    assert cls == 1


def test_ucd_to_sqm():
    # 174 µcd/m² corresponds roughly to 22 mag/arcsec²
    assert abs(ucd_to_sqm(174.0) - 22.0) < 1e-6


def test_load_bortle_raster_invalid_extension(tmp_path):
    bogus = tmp_path / "bortle.tpk"
    bogus.write_text("dummy")
    with pytest.raises(ValueError):
        load_bortle_raster(str(bogus))


def test_sample_bortle_dataset_transform(tmp_path):
    data = np.array([[22.0]], dtype=np.float32)
    transform = from_origin(1113194.0, 0, 1, 1)
    tif = tmp_path / "bortle_3857.tif"
    with rasterio.open(
        tif,
        'w',
        driver='GTiff',
        height=1,
        width=1,
        count=1,
        dtype='float32',
        crs='EPSG:3857',
        transform=transform,
    ) as dst:
        dst.write(data, 1)
    ds = load_bortle_raster(str(tif))
    val = sample_bortle_dataset(ds, 10.0, 0.0)
    assert val == pytest.approx(22.0)


def test_sample_bortle_dataset_scaling(tmp_path):
    data = np.array([[4.0]], dtype=np.float32)
    transform = from_origin(0, 0, 1, 1)
    tif = tmp_path / "bortle_scaled.tif"
    with rasterio.open(
        tif,
        'w',
        driver='GTiff',
        height=1,
        width=1,
        count=1,
        dtype='float32',
        transform=transform,
    ) as dst:
        dst.write(data, 1)
        dst.update_tags(scale_factor=1000)

    ds = load_bortle_raster(str(tif))
    l_ucd = sample_bortle_dataset(ds, 0.0, 0.0)
    sqm = ucd_to_sqm(l_ucd + 174.0)
    bortle = sqm_to_bortle(sqm)
    assert bortle >= 6


def test_load_bortle_kmz(tmp_path):
    data = np.array([[22.0]], dtype=np.float32)
    img = tmp_path / "img.tif"
    with rasterio.open(img, 'w', driver='GTiff', height=1, width=1, count=1,
                       dtype='float32', crs='EPSG:4326',
                       transform=from_origin(0, 1, 1, 1)) as dst:
        dst.write(data, 1)

    kml = """<?xml version='1.0' encoding='UTF-8'?>
<kml xmlns='http://www.opengis.net/kml/2.2'>
  <GroundOverlay>
    <Icon><href>img.tif</href></Icon>
    <LatLonBox>
      <north>1</north>
      <south>0</south>
      <east>1</east>
      <west>0</west>
    </LatLonBox>
  </GroundOverlay>
</kml>
"""

    kmz = tmp_path / "test.kmz"
    with zipfile.ZipFile(kmz, 'w') as zf:
        zf.writestr('doc.kml', kml)
        zf.write(img, arcname='img.tif')

    ds = _load_bortle_raster(str(kmz))
    assert ds.read(1)[0, 0] == pytest.approx(22.0)

