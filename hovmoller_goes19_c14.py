#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import glob
import argparse
from datetime import datetime, timedelta, timezone
import s3fs
from netCDF4 import Dataset
from remap import remap
import numpy as np
import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec
import cartopy.crs as ccrs
import cartopy.feature as cfeature

# ==========================================================
# CONFIGURACION
# ==========================================================
BASE_TIME = None

CACHE_DIR = "./goes_cache"
REMAP_DIR = "./remap_cache"
HIST_DIR = "./historico"

SATELLITE = "noaa-goes19"
PRODUCT = "ABI-L2-CMIPF"
CHANNEL = "C14"

EXTENT = [-120, 5, 0, 25]
RESOLUTION = 4
MAX_RAW_FILES = 10

LOGO_PATH = "logo.png"

CMAP = "Greys"
VMIN = -90
VMAX = 40

FIGSIZE = (18, 26)
DPI = 150
FOOTER_FRAC = 0.14


def get_base_datetime():

    global BASE_TIME

    if BASE_TIME is not None:
        return BASE_TIME

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--datetime",
        help="YYYYMMDDHH",
        required=False,
    )

    args = parser.parse_args()

    if args.datetime:

        BASE_TIME = datetime.strptime(args.datetime, "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )

    else:

        BASE_TIME = datetime.now(timezone.utc)

    return BASE_TIME


def update_remap_cache():

    os.makedirs(CACHE_DIR, exist_ok=True)
    os.makedirs(REMAP_DIR, exist_ok=True)

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

        except Exception:

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

    today = get_base_datetime()

    for i in range(9, -1, -1):

        dt = today - timedelta(hours=12 * i)

        times.append(
            datetime(
                dt.year,
                dt.month,
                dt.day,
                dt.hour,
            )
        )

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

            grid = remap(
                ncfile, "CMI", EXTENT, RESOLUTION, h, a, b, lon0, x1, y1, x2, y2
            )

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

            file.close()

            print(f"Guardado: {outfile}")

        except Exception as e:

            print(f"ERROR {timestamp}: {e}")

    print("\nFINALIZADO")

    try:
        cleanup_cache()
        cleanup_remap()
    except Exception as e:
        print(e)


def generate_hovmoller():

    os.makedirs(HIST_DIR, exist_ok=True)

    # ==========================================================
    # MESES ESPAÑOL
    # ==========================================================

    MESES = {
        1: "ENE",
        2: "FEB",
        3: "MAR",
        4: "ABR",
        5: "MAY",
        6: "JUN",
        7: "JUL",
        8: "AGO",
        9: "SEP",
        10: "OCT",
        11: "NOV",
        12: "DIC",
    }

    # ==========================================================
    # LEER ARCHIVOS
    # ==========================================================

    files = sorted(glob.glob(os.path.join(REMAP_DIR, "*.npz")))

    if len(files) == 0:
        raise RuntimeError("No hay archivos en remap_cache")

    n = len(files)

    print(f"{n} paneles encontrados")

    # ==========================================================
    # FIGURA
    # ==========================================================

    fig = plt.figure(figsize=FIGSIZE, dpi=DPI, facecolor="black")

    gs = gridspec.GridSpec(
        n,
        2,
        width_ratios=[0.07, 0.93],
        hspace=0.0,
        wspace=0.0,
        left=0.0,
        right=1.0,
        top=1.0,
        bottom=FOOTER_FRAC,
    )

    # ==========================================================
    # LOOP DE PANELES
    # ==========================================================

    for i, file in enumerate(files):

        timestamp = os.path.basename(file).replace(".npz", "")
        dt = datetime.strptime(timestamp, "%Y%m%d%H%M")

        d = np.load(file)
        arr = d["data"]
        lon = d["lon"]
        lat = d["lat"]

        dx = lon[1] - lon[0]
        dy = abs(lat[1] - lat[0])

        img_extent = [
            lon.min() - dx / 2,
            lon.max() + dx / 2,
            lat.min() - dy / 2,
            lat.max() + dy / 2,
        ]

        # ----------------------------------------------------------
        # Etiqueta de fecha
        # ----------------------------------------------------------
        ax_label = fig.add_subplot(gs[i, 0])
        ax_label.set_facecolor("black")
        ax_label.set_xticks([])
        ax_label.set_yticks([])
        for s in ax_label.spines.values():
            s.set_visible(False)

        fecha = f"{dt.day:02d}\n{MESES[dt.month]}\n{dt:%H} UTC"
        ax_label.text(
            0.5,
            0.5,
            fecha,
            color="orange",
            fontsize=13,
            ha="center",
            va="center",
            fontweight="bold",
            transform=ax_label.transAxes,
        )

        # ----------------------------------------------------------
        # Eje imagen: imshow con extent geográfico, aspect="auto"
        # Ocupa 100% del área del GridSpec sin recorte de Cartopy
        # ----------------------------------------------------------
        ax = fig.add_subplot(gs[i, 1])
        ax.set_facecolor("black")
        ax.set_xticks([])
        ax.set_yticks([])
        for s in ax.spines.values():
            s.set_visible(False)

        ax.imshow(
            arr,
            origin="upper",
            extent=img_extent,  # coordenadas geográficas reales
            aspect="auto",  # llena el panel completo
            cmap=CMAP,
            vmin=VMIN,
            vmax=VMAX,
            interpolation="nearest",
            zorder=1,
        )

        # Limites explícitos = extent de la imagen
        ax.set_xlim(img_extent[0], img_extent[1])
        ax.set_ylim(img_extent[2], img_extent[3])

        # ----------------------------------------------------------
        # Eje Cartopy transparente encima: solo cartografía
        # Se ancla exactamente a la posición del ax anterior
        # ----------------------------------------------------------
        geoax = fig.add_axes(
            ax.get_position(),
            projection=ccrs.PlateCarree(),
            zorder=10,
        )
        geoax.patch.set_alpha(0)  # fondo totalmente transparente
        geoax.set_extent(img_extent, crs=ccrs.PlateCarree())

        # Forzar mismo aspect que ax (auto) para que los bordes coincidan
        geoax.set_aspect("auto")

        geoax.coastlines(resolution="50m", color="white", linewidth=0.50, zorder=5)
        geoax.add_feature(cfeature.BORDERS, edgecolor="white", linewidth=0.30, zorder=5)

        from matplotlib.ticker import FixedLocator

        gl = geoax.gridlines(
            draw_labels=(i == n - 1),
            linewidth=0.5,
            color="white",
            alpha=0.6,
            linestyle=":",
            zorder=4,
        )

        gl.xlocator = FixedLocator(
            [-120, -110, -100, -90, -80, -70, -60, -50, -40, -30, -20, -10, 0]
        )

        gl.ylocator = FixedLocator([5, 10, 15, 20, 25])

        gl.top_labels = False
        gl.right_labels = False

        gl.xlabel_style = {
            "size": 8,
            "color": "white",
            "weight": "bold",
        }

        gl.ylabel_style = {
            "size": 8,
            "color": "white",
            "weight": "bold",
        }

        for s in geoax.spines.values():
            s.set_visible(False)

    # ==========================================================
    # FOOTER
    # ==========================================================

    F = FOOTER_FRAC

    # ----------------------------------------------------------
    # LOGO
    # ----------------------------------------------------------

    logo_ax = fig.add_axes([0.07, 0.01, 0.15, F - 0.015])

    logo_ax.set_facecolor("black")

    if os.path.exists(LOGO_PATH):
        logo_ax.imshow(plt.imread(LOGO_PATH))

    logo_ax.axis("off")

    # ----------------------------------------------------------
    # TEXTO
    # ----------------------------------------------------------

    text_ax = fig.add_axes([0.24, 0.02, 0.25, F - 0.015])

    text_ax.set_facecolor("black")
    text_ax.axis("off")

    text_ax.text(
        0.0,
        0.5,
        "GOES-19 / ABI",
        fontsize=18,
        color="white",
        fontweight="bold",
    )

    text_ax.text(
        0.0,
        0.4,
        "CANAL 14 (IR 11.2 µm)",
        fontsize=12,
        color="white",
        fontweight="bold",
    )

    text_ax.text(
        0.0,
        0.3,
        "Hovmöller - Últimos 5 días",
        fontsize=11,
        color="white",
    )

    # ----------------------------------------------------------
    # COLORBAR
    # ----------------------------------------------------------

    cax = fig.add_axes([0.42, 0.07, 0.5, 0.015])

    norm = plt.Normalize(
        vmin=VMIN,
        vmax=VMAX,
    )

    cb = plt.colorbar(
        plt.cm.ScalarMappable(
            norm=norm,
            cmap=CMAP,
        ),
        cax=cax,
        orientation="horizontal",
    )
    cb.ax.invert_xaxis()

    cb.set_label(
        "Temperatura (°C)",
        color="white",
        fontsize=10,
        fontweight="bold",
    )

    cb.ax.tick_params(
        colors="white",
        labelsize=8,
    )

    cb.outline.set_edgecolor("white")

    cax.set_facecolor("black")

    # ==========================================================
    # SALIDA
    # ==========================================================

    timestamp = get_base_datetime().strftime("%Y%m%d%H")

    png_hist = f"./historico/hovmoller_goes19_c14_{timestamp}.png"

    png_current = "hovmoller_goes19_c14.png"

    plt.savefig(
        png_hist,
        dpi=DPI,
        bbox_inches="tight",
        pad_inches=0,
        facecolor="black",
    )
    plt.close()

    import shutil

    shutil.copy2(
        png_hist,
        png_current,
    )

    print("\nGenerados:")
    print(png_hist)


def main():

    try:
        update_remap_cache()
        generate_hovmoller()

    except Exception as e:
        print(e)


if __name__ == "__main__":
    main()
