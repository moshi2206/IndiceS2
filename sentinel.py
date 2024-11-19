from copernicus import filter_by_date_box, download_all
from datetime import date, timedelta, datetime
from osgeo import ogr, osr, gdal
from osgeo import gdal_array as ga
from numba import jit
from shapely.geometry import Polygon
import rasterio.mask
import numpy as np
import cv2
import glob
import os
import rasterio


@jit(nopython=True)
def ndvi(nir, red):
    return np.divide((nir - red), (nir + red))


def operate_clouds(clouds, raster):
    for i in range(0, len(clouds)):
        for j in range(0, len(clouds[i])):
            if clouds[i][j] == 10:
                raster[i][j] = np.NaN
    return raster


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
    Reduce vertice
    Es una funcion para reducir vertices de un
    poligono irregular al minimo posible
    """
    poly2 = np.array(poly, dtype=np.float32)
    rect = cv2.minAreaRect(poly2)
    box = cv2.boxPoints(rect)
    box = box.tolist()
    if box[0] != box[-1]:
        box.append(box[0])
    return [box]


def transform_shap(shap, output):
    """
    Convertir el AOI (Area of Interest) EPSG (Geodistico)
    """
    inputEPSG = 4326
    outputEPSG = output
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
            coordTransform = osr.CoordinateTransformation(
                inSpatialRef,
                outSpatialRef
            )

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
        """
        Se aplica funcion cuantil
        para mejorar a una distribucion porcentual de colores
        """
        ndvi_data = srcband.ReadAsArray()
        ndvi_data_flat = ndvi_data.flatten()
        ndvi_data_filtered = ndvi_data_flat[
            ndvi_data_flat != srcband.GetNoDataValue()]
        colors = ['red', 'orange', 'yellow', 'green', '76 132 60']
        quantiles = np.quantile(
            ndvi_data_filtered,
            np.linspace(0, 1, len(colors) + 1)[1:]
        )
        texto = ""
        for (color, quantile) in zip(colors, quantiles):
            texto += F"{quantile} {color}\n"
        print("Colores definidos")
        filetxt = open(F"{os.getcwd()}/s2files/NDVI.txt", "w")
        filetxt.write(texto)
        filetxt.close()
        gdal.Translate(
            F"{os.getcwd()}/s2files/final1NDVI.vrt",
            F"{os.getcwd()}/s2files/NDVI.tif",
            options=gdal.TranslateOptions(
                format="VRT",
                noData="0 0 0"
            )
        )
        gdal.DEMProcessing(
            F"{os.getcwd()}/s2files/final2NDVI.tif",
            F"{os.getcwd()}/s2files/final1NDVI.vrt",
            "color-relief",
            options=gdal.DEMProcessingOptions(
                colorFilename=F"{os.getcwd()}/s2files/NDVI.txt",
                colorSelection="nearest_color_entry"
            )
        )
        with rasterio.open(F"{os.getcwd()}/s2files/final2NDVI.tif") as nf:
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
        with rasterio.open(
            F"{os.getcwd()}/s2files/final3NDVI.tif", "w", **out_meta
        ) as nc:
            nc.write(out_image2)
        gdal.Translate(
            F"{os.getcwd()}/s2files/final3NDVI.png",
            F"{os.getcwd()}/s2files/final3NDVI.tif",
            options=gdal.TranslateOptions(
                format="PNG",
                outputType=gdal.GDT_Byte,
                maskBand=1,
                noData="0 0 0"
            )
        )
    except Exception as e:
        print(e)


def merge_images(resp):
    try:
        print(shap)
        li_red = []
        li_nir = []
        li_scl = []
        pos = 0
        for element in resp["adjuntado"]:
            pos += 1
            red_file = glob.glob(
                F"{os.getcwd()}/s2files/{element['name']}/GRANULE/**/*B04_10m.jp2",
                recursive=True,
            )
            nir_file = glob.glob(
                F"{os.getcwd()}/s2files/{element['name']}/GRANULE/**/*B08_10m.jp2",
                recursive=True,
            )
            cld_file = glob.glob(
                F"{os.getcwd()}/s2files/{element['name']}/GRANULE/**/*SCL_20m.jp2",
                recursive=True,
            )
            if red_file and nir_file and cld_file:
                with rasterio.open(
                    red_file[0]
                ) as rc:
                    if type(resp["poligono"][0]["coordinates"][0][0]) == list:
                        shap = transform_shap(resp["poligono"], int(str(rc.crs).split(":")[1]))
                    else:
                        shap = resp["poligono"]
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
                with rasterio.open(
                    F"{os.getcwd()}/s2files/red{pos}", "w", **red_meta
                ) as rcf:
                    rcf.write(red_image)
                with rasterio.open(
                    nir_file[0]
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
                with rasterio.open(
                    F"{os.getcwd()}/s2files/nir{pos}", "w", **nir_meta
                ) as ncf:
                    ncf.write(nir_image)
                with rasterio.open(
                    cld_file[0]
                ) as cl:
                    cld_image, cld_transform = rasterio.mask.mask(
                        dataset=cl,
                        shapes=shap,
                        crop=True,
                        all_touched=False,
                        pad=False,
                        pad_width=1,
                        nodata=0
                    )
                    cld_meta = cl.meta
                    cld_meta.update(
                        {
                            "driver": "GTiff",
                            "height": cld_image.shape[1],
                            "width": cld_image.shape[2],
                            "transform": cld_transform,
                        }
                    )
                with rasterio.open(
                    F"{os.getcwd()}/s2files/cld{pos}", "w", **cld_meta
                ) as cld:
                    cld.write(cld_image)
                gdal.Translate(
                    F"{os.getcwd()}/s2files/scl{pos}",
                    F"{os.getcwd()}/s2files/cld{pos}",
                    xRes=10, yRes=10, resampleAlg="near", format="GTiff"
                )
                li_red.append(F"{os.getcwd()}/s2files/red{pos}")
                li_nir.append(F"{os.getcwd()}/s2files/nir{pos}")
                li_scl.append(F"{os.getcwd()}/s2files/scl{pos}")
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
        gdal.BuildVRT(
            F"{os.getcwd()}/s2files/scl.vrt",
            li_scl,
            options=build
        )
        translate = gdal.TranslateOptions()
        gdal.Translate(
            F"{os.getcwd()}/s2files/red",
            F"{os.getcwd()}/s2files/red.vrt",
            options=translate
        )
        gdal.Translate(
            F"{os.getcwd()}/s2files/nir",
            F"{os.getcwd()}/s2files/nir.vrt",
            options=translate
        )
        gdal.Translate(
            F"{os.getcwd()}/s2files/scl",
            F"{os.getcwd()}/s2files/scl.vrt",
            options=translate
        )
        print("archivos obtenidos")

        with rasterio.open(
            F"{os.getcwd()}/s2files/red"
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
        with rasterio.open(
            F"{os.getcwd()}/s2files/red", "w", **red_meta
        ) as rcf:
            rcf.write(red_image)
        with rasterio.open(
            F"{os.getcwd()}/s2files/nir"
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
        with rasterio.open(
            F"{os.getcwd()}/s2files/nir", "w", **nir_meta
        ) as ncf:
            ncf.write(nir_image)
        with rasterio.open(
            F"{os.getcwd()}/s2files/scl"
        ) as sc:
            scl_image, scl_transform = rasterio.mask.mask(
                dataset=sc,
                shapes=shap,
                crop=True,
                all_touched=False,
                pad=False,
                pad_width=1,
                nodata=0
            )
            scl_meta = sc.meta
            scl_meta.update(
                {
                    "driver": "GTiff",
                    "height": scl_image.shape[1],
                    "width": scl_image.shape[2],
                    "transform": scl_transform,
                }
            )
        with rasterio.open(
            F"{os.getcwd()}/s2files/scl", "w", **scl_meta
        ) as scf:
            scf.write(scl_image)
        red_link = gdal.Open(F"{os.getcwd()}/s2files/red")
        nir_link = gdal.Open(F"{os.getcwd()}/s2files/nir")
        # scl_link = gdal.Open(F"{os.getcwd()}/s2files/scl")
        np.seterr(divide="ignore", invalid="ignore")
        red = red_link.ReadAsArray().astype(np.float32)
        nir = nir_link.ReadAsArray().astype(np.float32)
        # scl = scl_link.ReadAsArray().astype(np.int8)

        ndvi_ = ndvi(nir, red)
        # ndvi_ = operate_clouds(scl, ndvi_)
        print("NDVI Generado")
        ndvi1 = ga.numpy.nan_to_num(ndvi_)
        ga.SaveArray(
            ndvi1,
            F"{os.getcwd()}/s2files/NDVI.tif",
            format="GTiff",
            prototype=F"{os.getcwd()}/s2files/red"
        )
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
        odate = datetime.strptime(
            da['OriginDate'].split("T")[0], "%Y-%m-%d").date()
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
end = date(2024, 8, 18)
start = end - timedelta(days=3)
downloadsentinel(poligono, start, end)
