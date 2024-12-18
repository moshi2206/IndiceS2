from decouple import config
from requests.adapters import HTTPAdapter
from shapely.geometry import Polygon
from urllib3.util import Retry
import requests
import json
import os
import zipfile


retries = Retry(
    total=3,
    backoff_factor=0.1,
    status_forcelist=[502, 503, 504],
    allowed_methods={'GET'},
)


def get_access_token(username: str, password: str) -> str:
    """
    Acceso a dataspace copernicus
    """
    data = {
        "client_id": "cdse-public",
        "username": username,
        "password": password,
        "grant_type": "password",
        }
    try:
        r = requests.post(
            "https://identity.dataspace.copernicus.eu/auth/realms/CDSE/protocol/openid-connect/token",
            data=data,
        )
        r.raise_for_status()
    except Exception as e:
        raise Exception(
            f"""Access token creation failed.
Reponse from the server was: {r.json()}
Error: {e}"""
        )
    return r.json()["access_token"]


def filter_by_date_box(
        start: str, end: str, polygon: Polygon, cloud: str) -> json:
    """
    Filtrar por fechas, poligono, nubes
    """
    string = F"""https://catalogue.dataspace.copernicus.eu/odata/v1/Products?\
$filter=Attributes/OData.CSC.DoubleAttribute/any(att:att/Name eq 'cloudCover' \
and att/OData.CSC.DoubleAttribute/Value lt {cloud}) \
and Attributes/OData.CSC.StringAttribute/any(att:att/Name eq 'productType' \
and att/OData.CSC.StringAttribute/Value eq 'S2MSI2A') \
and Collection/Name eq 'SENTINEL-2' \
and OData.CSC.Intersects(area=geography'SRID=4326;{str(polygon)}') \
and ContentDate/Start gt {start} \
and ContentDate/Start lt {end}"""
    s = requests.Session()
    s.mount('https://', HTTPAdapter(max_retries=retries))
    json = s.get(string).json()
    return json


def download_all(da: dict) -> str:
    if os.path.exists(F"{os.getcwd()}/s2files/" + da["Name"]):
        pass
    else:
        # Se obtiene un token por cada descarga, el token caduca cada x minutos
        token = get_access_token(
            config("USER_DATASPACE", None), config("PASSWORD_DATASPACE", None))
        # Hacer request para descargar archivo
        url = f"https://zipper.dataspace.copernicus.eu/odata/v1/Products({da['Id']})/$value"
        headers = {"Authorization": f"Bearer {token}"}
        session = requests.Session()
        session.mount('https://', HTTPAdapter(max_retries=retries))
        session.headers.update(headers)
        response = session.get(url, headers=headers, stream=True)
        # Obtener tamanho de archivo
        total_size = int(response.headers['Content-Length'])
        downloaded_size = 0
        # Escribir archivo
        with open(
            F"{os.getcwd()}/s2files/" + da['Name'] + ".zip", "wb"
        ) as file:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded_size += len(chunk)
                    percentage = (downloaded_size / total_size) * 100
                    print(F"{da['Name']}: {percentage:.2f}%\r")
                    file.write(chunk)
        try:
            # Descomprimir archivo
            with zipfile.ZipFile(
                F"{os.getcwd()}/s2files/" + da["Name"] + ".zip", "r"
            ) as zip_file:
                zip_file.extractall(F"{os.getcwd()}/s2files/")
            os.remove(F"{os.getcwd()}/s2files/" + da["Name"] + ".zip")
        except:
            print(F"{da['Name']} No se descargo correctamente...")
            print("Reintentando")
            os.remove(F"{os.getcwd()}/s2files/" + da["Name"] + ".zip")
            download_all(da, token)
