from datetime import date, timedelta, datetime
from numba import jit
import rasterio.mask
from copernicus import filter_by_date_box, download_all
import numpy as np
import cv2, glob, os, rasterio
from shapely.geometry import Polygon
from osgeo import ogr, osr, gdal
from osgeo import gdal_array as ga
from osgeo_utils.pct2rgb import pct2rgb

gdal.SetCacheMax(4000000000)

@jit(nopython=True)
def ndvi(nir, red):
    return np.divide((nir - red), (nir + red))

def list_to_tuple(data):
    """
    Convertir lista a tuple
    """
    if isinstance(data, list):
        return tuple(list_to_tuple(item) for item in data)
    else:
        return data

def reduce_vertice(poly):
    """
    Reduce vertice es una funcion para reducir vertices de un poligono irregular al minimo posible
    """
    poly2 = np.array(poly, dtype=np.float32)
    rect = cv2.minAreaRect(poly2)
    box = cv2.boxPoints(rect)
    box = box.tolist()
    if box[0] != box[-1]:
        box.append(box[0])
    return [box]

def transform_shap(shap):
    """
    Convertir el AOI (Area of Interest) EPSG (Geodistico)
    """
    inputEPSG = 4326
    outputEPSG = 32721
    pos1 = 0
    pos2 = 0
    for coord in shap[0]["coordinates"]:
        for coor in coord:
            point = ogr.Geometry(ogr.wkbPoint)
            point.AddPoint(coor[1], coor[0])

            inSpatialRef = osr.SpatialReference()
            inSpatialRef.ImportFromEPSG(inputEPSG)

            outSpatialRef = osr.SpatialReference()
            outSpatialRef.ImportFromEPSG(outputEPSG)
            coordTransform = osr.CoordinateTransformation(inSpatialRef, outSpatialRef)

            point.Transform(coordTransform)
            coor = (point.GetX(), point.GetY())
            shap[0]["coordinates"][pos1][pos2] = coor
            pos2 += 1
        pos2 = 0
        pos1 += 1
    return shap

def cut_tile_final(poligono):
    try:
        with rasterio.open(F"{os.getcwd()}/s2files/NDVI.tif") as nf:
            out_image2, out_transform2 = rasterio.mask.mask(
                dataset=nf,
                shapes=poligono,
                crop=True,
                all_touched=False,
                pad=False,
                pad_width=1,
                nodata=0
            )
            out_meta = nf.meta
            out_meta.update(
                {
                    "driver": "GTiff",
                    "height": out_image2.shape[1],
                    "width": out_image2.shape[2],
                    "transform": out_transform2
                }
            )
        gtif = gdal.Open(F"{os.getcwd()}/s2files/NDVI.tif")
        srcband = gtif.GetRasterBand(1)
        srcband.SetNoDataValue(0)
        # Se aplica quantiles para mejor distribucion de pixeles
        ndvi_data = srcband.ReadAsArray()
        ndvi_data_flat = ndvi_data.flatten()
        ndvi_data_filtered = ndvi_data_flat[ndvi_data_flat != srcband.GetNoDataValue()]
        colors = ['red', 'orange', 'yellow', 'green', '76 132 60']
        quantiles = np.quantile(ndvi_data_filtered, np.linspace(0, 1, len(colors) + 1)[1:])
        texto = ""
        for i, (color, quantile) in enumerate(zip(colors, quantiles)):
            texto += F"{quantile} {color}\n"
        print("Colores definidos")
        filetxt = open(F"{os.getcwd()}/s2files/NDVI.txt", "w")
        filetxt.write(texto)
        filetxt.close()
        gdal.Translate(
            F"{os.getcwd()}/s2files/final3NDVI.vrt",
            F"{os.getcwd()}/s2files/NDVI.tif",
            options=gdal.TranslateOptions(
                format="VRT",
            )
        )
        gdal.DEMProcessing(
            F"{os.getcwd()}/s2files/final4NDVI.tif",
            F"{os.getcwd()}/s2files/final3NDVI.vrt",
            "color-relief",
            options=gdal.DEMProcessingOptions(
                colorFilename=F"{os.getcwd()}/s2files/NDVI.txt",
                colorSelection="nearest_color_entry"
            )
        )
        with rasterio.open(F"{os.getcwd()}/s2files/final4NDVI.tif") as nf:
            out_image2, out_transform2 = rasterio.mask.mask(
                dataset=nf,
                shapes=poligono,
                crop=True,
                all_touched=False,
                pad=False,
                pad_width=1,
                nodata=0
            )
            out_meta = nf.meta
            out_meta.update(
                {
                    "driver": "GTiff",
                    "height": out_image2.shape[1],
                    "width": out_image2.shape[2],
                    "transform": out_transform2,
                }
            )
        with rasterio.open(F"{os.getcwd()}/s2files/final5NDVI.tif", "w", **out_meta) as nc:
            nc.write(out_image2)
        gdal.Translate(
            F"{os.getcwd()}/s2files/final6NDVI.vrt",
            F"{os.getcwd()}/s2files/final5NDVI.tif",
            options=gdal.TranslateOptions(
                format="VRT",
                outputType=gdal.GDT_Byte,
                maskBand=1
            )
        )
        gdal.Translate(
            F"{os.getcwd()}/s2files/final6NDVI.png",
            F"{os.getcwd()}/s2files/final6NDVI.vrt",
            options=gdal.TranslateOptions(
                format="PNG",
                noData="0 0 0",
                maskBand=1
            )
        )
    except Exception as e:
        print(e)


def merge_images(resp):
    try:
        li_red = []
        li_nir = []
        for l in resp["adjuntado"]:
            red_file = glob.glob(
                F"{os.getcwd()}/s2files/{l['name']}/GRANULE/**/*B04_10m.jp2",
                recursive=True,
            )
            nir_file = glob.glob(
                F"{os.getcwd()}/s2files/{l['name']}/GRANULE/**/*B08_10m.jp2",
                recursive=True,
            )
            li_red.append(red_file[0])
            li_nir.append(nir_file[0])
        build = gdal.BuildVRTOptions(
            srcNodata=0,
            hideNodata=None
        )
        gdal.BuildVRT(
            F"{os.getcwd()}/s2files/red.vrt",
            li_red,
            options=build
        )
        gdal.BuildVRT(
            F"{os.getcwd()}/s2files/nir.vrt",
            li_nir,
            options=build
        )
        translate = gdal.TranslateOptions()
        gdal.Translate(
            F"{os.getcwd()}/s2files/red1",
            F"{os.getcwd()}/s2files/red.vrt",
            options=translate
        )
        gdal.Translate(
            F"{os.getcwd()}/s2files/nir1",
            F"{os.getcwd()}/s2files/nir.vrt",
            options=translate
        )
        print("archivos obtenidos")
        if type(resp["poligono"][0]["coordinates"][0][0]) == list:
            shap = transform_shap(resp["poligono"])
        else:
            shap = resp["poligono"]
        with rasterio.open(
            F"{os.getcwd()}/s2files/red1"
        ) as rc:
            red_image, red_transform = rasterio.mask.mask(
                dataset=rc,
                shapes=shap,
                crop=True,
                all_touched=False,
                pad=False,
                pad_width=1,
                nodata=0
            )
            red_meta = rc.meta
            red_meta.update(
                {
                    "driver": "Gtiff",
                    "height": red_image.shape[1],
                    "width": red_image.shape[2],
                    "transform": red_transform,
                }
            )
        with rasterio.open(F"{os.getcwd()}/s2files/red", "w", **red_meta) as rcf:
            rcf.write(red_image)
        with rasterio.open(
            F"{os.getcwd()}/s2files/nir1"
        ) as nc:
            nir_image, nir_transform = rasterio.mask.mask(
                dataset=nc,
                shapes=shap,
                crop=True,
                all_touched=False,
                pad=False,
                pad_width=1,
                nodata=0
            )
            nir_meta = nc.meta
            nir_meta.update(
                {
                    "driver": "GTiff",
                    "height": nir_image.shape[1],
                    "width": nir_image.shape[2],
                    "transform": nir_transform,
                }
            )
        with rasterio.open(F"{os.getcwd()}/s2files/nir", "w", **nir_meta) as ncf:
            ncf.write(nir_image)
        red_link = gdal.Open(F"{os.getcwd()}/s2files/red")
        nir_link = gdal.Open(F"{os.getcwd()}/s2files/nir")
        red = red_link.ReadAsArray().astype(np.float32)
        nir = nir_link.ReadAsArray().astype(np.float32)
        np.seterr(divide="ignore", invalid="ignore")
        ndvi_ = ndvi(nir, red)
        print("NDVI Generado")
        ndvi1 = ga.numpy.nan_to_num(ndvi_)
        ga.SaveArray(ndvi1, F"{os.getcwd()}/s2files/NDVI.tif", format="GTiff", prototype=F"{os.getcwd()}/s2files/red")
        print("Iniciando Corte")
        cut_tile_final(shap)
    except Exception as e:
        print(e)

def downloadsentinel(poly, start, end):
    """
    Funcion para filtrar y descargar imagenes satelitales
    """
    reduce = reduce_vertice([poly[0]])
    data = filter_by_date_box(
        F"{start}T00:00:00.000Z",
        F"{end}T00:00:00.000Z",
        Polygon(list_to_tuple(reduce)[0]),
        '20.00'
    )
    comp = {
        "fecha": "",
        "poligono": [
            {
                "type": "Polygon",
                "coordinates": poly
            }
        ],
        "adjuntado": []
    }
    for da in data['value']:
        odate = datetime.strptime(da['OriginDate'].split("T")[0], "%Y-%m-%d").date()
        comp["fecha"] = odate
        download_all(da)
        comp["adjuntado"].append(
            {
                "name": da["Name"],
                "fecha": odate
            }
            
        )
    if comp["fecha"] != "":
        merge_images(comp)

poligono = [
  [
    [
      -54.78556922011255,
      -25.80897247263852
    ],
    [
      -54.78871175526308,
      -25.8110355503304
    ],
    [
      -54.79110417337074,
      -25.82091298400772
    ],
    [
      -54.78257911349687,
      -25.82344773420636
    ],
    [
      -54.78556922011255,
      -25.80897247263852
    ],
    [
      -54.78556922011255,
      -25.80897247263852
    ],
    [
      -54.78556922011255,
      -25.80897247263852
    ]
  ]
]
end = date.today()
start = end - timedelta(days=6)
downloadsentinel(poligono, start, end)