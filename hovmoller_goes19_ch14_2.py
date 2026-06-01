#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import glob
import numpy as np
from datetime import datetime

import matplotlib.pyplot as plt
import matplotlib.gridspec as gridspec

import cartopy.crs as ccrs
import cartopy.feature as cfeature

from PIL import Image

# ==========================================================
# CONFIGURACION
# ==========================================================

HIST_DIR = "./historico"

os.makedirs(HIST_DIR, exist_ok=True)

REMAP_DIR = "./remap_cache"

LOGO_PATH = "logo.png"

EXTENT = [-120, 5, 0, 25]

CMAP = "Greys"

VMIN = -90
VMAX = 40

FIGSIZE = (18, 26)

DPI = 150

FOOTER_FRAC = 0.14

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

# Leer extent geográfico del primer archivo (igual para todos)
_d0 = np.load(files[0])
_lon0 = _d0["lon"]
_lat0 = _d0["lat"]
_dx = _lon0[1] - _lon0[0]
_dy = abs(_lat0[1] - _lat0[0])
IMG_EXTENT = [
    _lon0.min() - _dx / 2,
    _lon0.max() + _dx / 2,
    _lat0.min() - _dy / 2,
    _lat0.max() + _dy / 2,
]

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

    geoax.coastlines(resolution="50m", color="white", linewidth=0.40, zorder=5)
    geoax.add_feature(cfeature.BORDERS, edgecolor="white", linewidth=0.20, zorder=5)
    # geoax.gridlines(
    #     draw_labels=False,
    #     linewidth=0.15,
    #     color="white",
    #     alpha=0.15,
    #     linestyle=":",
    #     zorder=4,
    # )
    from matplotlib.ticker import FixedLocator

    gl = geoax.gridlines(
        draw_labels=(i == n - 1),
        # draw_labels=False,
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

    if i != n - 1:
        gl.bottom_labels = True
        gl.left_labels = True

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
    # gl = geoax.gridlines(
    #     draw_labels=False,
    #     linewidth=0.20,
    #     color="white",
    #     alpha=0.25,
    #     linestyle=":",
    #     zorder=4,
    # )

    # gl.xlocator = plt.FixedLocator([-120, -100, -80, -60, -40, -20, 0])

    # gl.ylocator = plt.FixedLocator([5, 10, 15, 20, 25])

    # if i == n - 1:

    #     geoax.set_xticks([-120, -100, -80, -60, -40, -20, 0], crs=ccrs.PlateCarree())

    #     geoax.set_yticks([5, 10, 15, 20, 25], crs=ccrs.PlateCarree())

    #     geoax.set_xticklabels(
    #         ["120W", "100W", "80W", "60W", "40W", "20W", "0"], fontsize=8, color="white"
    #     )

    #     geoax.set_yticklabels(
    #         ["5N", "10N", "15N", "20N", "25N"], fontsize=8, color="white"
    #     )

    # else:

    #     geoax.set_xticks([])
    #     geoax.set_yticks([])
    # geoax.set_xticks([])
    # geoax.set_yticks([])
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

""" # ==========================================================
# FOOTER
# ==========================================================

F = FOOTER_FRAC

# Logo
logo_ax = fig.add_axes([0.01, 0.01, 0.12, F - 0.02])
logo_ax.set_facecolor("black")
if os.path.exists(LOGO_PATH):
    logo_ax.imshow(plt.imread(LOGO_PATH))
logo_ax.axis("off")

# Texto
text_ax = fig.add_axes([0.15, 0.025, 0.7, F - 0.03])
text_ax.set_facecolor("black")
text_ax.axis("off")
text_ax.text(0.0, 0.90, "GOES-19 / ABI", fontsize=18, color="white", fontweight="bold")
text_ax.text(
    0.0, 0.68, "CANAL 14 (IR 11.2 µm)", fontsize=12, color="white", fontweight="bold"
)
text_ax.text(0.0, 0.48, "Hovmöller - Últimos 7 días", fontsize=11, color="white")
# text_ax.text(
#     0.0, 0.28, "8 km de resolución", fontsize=11, color="gold", fontweight="bold"
# )
# text_ax.text(
#     0.0, 0.10, "Extensión: 120°W - 0° / 5°N - 25°N", fontsize=10, color="white"
# )

# Mapa regional
# map_ax = fig.add_axes(
#     [0.46, 0.022, 0.52, F - 0.02],
#     projection=ccrs.PlateCarree(),
# )
# map_ax.set_facecolor("black")
# map_ax.set_extent(IMG_EXTENT)
# map_ax.coastlines(resolution="50m", color="white", linewidth=0.5)
# map_ax.add_feature(cfeature.BORDERS, edgecolor="white", linewidth=0.25)
# gl = map_ax.gridlines(
#     draw_labels=True,
#     linewidth=0.25,
#     color="white",
#     alpha=0.35,
#     linestyle=":",
# )
# gl.top_labels = False
# gl.right_labels = False
# gl.xlabel_style = {"size": 8, "color": "white"}
# gl.ylabel_style = {"size": 8, "color": "white"}

# Colorbar
cax = fig.add_axes([0.12, 0.003, 0.78, 0.012])
norm = plt.Normalize(vmin=VMIN, vmax=VMAX)
cb = plt.colorbar(
    plt.cm.ScalarMappable(norm=norm, cmap=CMAP),
    cax=cax,
    orientation="horizontal",
)
cb.set_label("Temperatura (°C)", color="white", fontsize=10, fontweight="bold")
cb.ax.tick_params(colors="white", labelsize=8)
cb.outline.set_edgecolor("white")
cax.set_facecolor("black") """

# ==========================================================
# SALIDA
# ==========================================================

timestamp = datetime.utcnow().strftime("%Y%m%d%H")

png_hist = f"./historico/hovmoller_goes19_c14_{timestamp}.png"
# webp_hist = f"./historico/hovmoller_goes19_c14_{timestamp}.webp"

png_current = "hovmoller_goes19_c14.png"
# webp_current = "hovmoller_goes19_c14.webp"

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
# img = Image.open(png_file)
# img.save(webp_file, quality=95, method=6)

print("\nGenerados:")
print(png_hist)
# print(webp_hist)
