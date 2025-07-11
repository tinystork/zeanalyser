import os
import sys
import numpy as np
import rasterio
from rasterio.transform import from_origin
from tempfile import NamedTemporaryFile
import pytest
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
from bortle_utils import load_bortle_raster, sqm_to_bortle

def test_sqm_to_bortle(tmp_path):
    data = np.full((2, 2), 22.0, dtype=np.float32)
    transform = from_origin(0, 0, 1, 1)
    tif = tmp_path / "bortle.tif"
    with rasterio.open(tif, 'w', driver='GTiff', height=2, width=2, count=1, dtype='float32', transform=transform) as dst:
        dst.write(data, 1)
    ds = load_bortle_raster(str(tif))
    val = list(ds.sample([(0, 0)]))[0][0]
    cls = sqm_to_bortle(float(val))
    assert cls == 1


def test_load_bortle_raster_invalid_extension(tmp_path):
    bogus = tmp_path / "bortle.tpk"
    bogus.write_text("dummy")
    with pytest.raises(ValueError):
        load_bortle_raster(str(bogus))

