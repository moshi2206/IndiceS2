from datetime import date, timedelta
from copernicus import filter_by_date_box, download_all
import numpy as np
import cv2
from shapely.geometry import Polygon

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

def downloadsentinel(poly, start, end):
    """
    Funcion para filtrar y descargar imagenes satelitales
    """
    resp = []
    reduce = reduce_vertice([poly[0]])
    data = filter_by_date_box(
        F"{start}T00:00:00.000Z",
        F"{end}T00:00:00.000Z",
        Polygon(list_to_tuple(reduce)[0]),
        '20.00'
    )
    for da in data['value']:
        download_all(da)

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
start = end - timedelta(days=20)
downloadsentinel(poligono, start, end)