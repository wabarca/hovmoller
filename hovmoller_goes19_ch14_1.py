#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
from datetime import datetime, timedelta

import numpy as np
import s3fs

from netCDF4 import Dataset

from remap import remap

# ==========================================================
# CONFIGURACION
# ==========================================================

CACHE_DIR = "./goes_cache"
REMAP_DIR = "./remap_cache"

os.makedirs(CACHE_DIR, exist_ok=True)
os.makedirs(REMAP_DIR, exist_ok=True)

SATELLITE = "noaa-goes19"
PRODUCT = "ABI-L2-CMIPF"

CHANNEL = "C14"

EXTENT = [-120, 5, 0, 25]

RESOLUTION = 4

MAX_RAW_FILES = 10

# ==========================================================
# AWS
# ==========================================================

fs = s3fs.S3FileSystem(anon=True)

# ==========================================================
# LIMPIEZA CACHE
# ==========================================================


def cleanup_cache():

    files = sorted(
        [
            os.path.join(CACHE_DIR, f)
            for f in os.listdir(CACHE_DIR)
            if f.endswith(".nc")
        ],
        key=os.path.getmtime,
    )

    while len(files) > MAX_RAW_FILES:

        old = files.pop(0)

        print("Eliminando:", old)

        os.remove(old)


def cleanup_remap():

    files = sorted(
        [
            os.path.join(REMAP_DIR, f)
            for f in os.listdir(REMAP_DIR)
            if f.endswith(".npz")
        ],
        key=os.path.getmtime,
    )

    while len(files) > MAX_RAW_FILES:

        old = files.pop(0)

        print("Eliminando remap:", old)

        os.remove(old)


# ==========================================================
# BUSCAR ESCENA MAS CERCANA
# ==========================================================


def find_best_file(dt):

    year = dt.strftime("%Y")
    doy = dt.strftime("%j")
    hour = dt.strftime("%H")

    path = f"{SATELLITE}/" f"{PRODUCT}/" f"{year}/" f"{doy}/" f"{hour}/"

    try:

        files = fs.ls(path)

    except:

        return None

    files = [f for f in files if CHANNEL in f]

    if len(files) == 0:

        return None

    best = None
    best_diff = 999999

    for f in files:

        m = re.search(r"_s(\d{4})(\d{3})(\d{2})(\d{2})(\d{2})", f)

        if not m:
            continue

        yy = int(m.group(1))
        doyf = int(m.group(2))
        hh = int(m.group(3))
        mm = int(m.group(4))
        ss = int(m.group(5))

        scene_time = datetime(yy, 1, 1) + timedelta(
            days=doyf - 1, hours=hh, minutes=mm, seconds=ss
        )

        diff = abs((scene_time - dt).total_seconds())

        if diff < best_diff:

            best_diff = diff
            best = f

    return best


# ==========================================================
# FECHAS
# ==========================================================

times = []

today = datetime.utcnow()

for d in range(4, -1, -1):

    base = today - timedelta(days=d)

    for hour in [0, 12]:

        times.append(datetime(base.year, base.month, base.day, hour))

# ==========================================================
# DESCARGA
# ==========================================================

downloaded = []

for dt in times:

    print("\n====================================")
    print(dt)
    print("====================================")

    remote = find_best_file(dt)

    if remote is None:

        print("No encontrado")

        continue

    local = os.path.join(CACHE_DIR, os.path.basename(remote))

    if os.path.exists(local):

        print("Ya existe")

    else:

        print("Descargando")

        fs.get(remote, local)

    downloaded.append((dt, local))

cleanup_cache()
cleanup_remap()

# ==========================================================
# REMAP
# ==========================================================

for dt, ncfile in downloaded:

    timestamp = dt.strftime("%Y%m%d%H%M")

    outfile = os.path.join(REMAP_DIR, f"{timestamp}.npz")

    if os.path.exists(outfile):

        print(f"Remap cache existente: {timestamp}")

        continue

    print(f"Remapeando {timestamp}")

    try:

        file = Dataset(ncfile)

        proj = file.variables["goes_imager_projection"]

        h = proj.perspective_point_height

        lon0 = proj.longitude_of_projection_origin

        a = proj.semi_major_axis
        b = proj.semi_minor_axis

        x1 = file.variables["x_image_bounds"][0] * h

        x2 = file.variables["x_image_bounds"][1] * h

        y1 = file.variables["y_image_bounds"][1] * h

        y2 = file.variables["y_image_bounds"][0] * h

        grid = remap(ncfile, "CMI", EXTENT, RESOLUTION, h, a, b, lon0, x1, y1, x2, y2)

        data = grid.ReadAsArray()

        data = data - 273.15

        # Coordenadas geográficas del raster remapeado

        gt = grid.GetGeoTransform()

        nx = grid.RasterXSize
        ny = grid.RasterYSize

        lon = gt[0] + np.arange(nx) * gt[1]
        lat = gt[3] + np.arange(ny) * gt[5]

        np.savez_compressed(
            outfile,
            data=data,
            lon=lon,
            lat=lat,
        )

        print(f"Guardado: {outfile}")

    except Exception as e:

        print(f"ERROR {timestamp}: {e}")

print("\nFINALIZADO")
