# IndiceS2
Proyecto de muestra para descargar y procesar imagenes satelitales de Sentinel-2

* [Funciones esenciales: ](copernicus.py) Funciones para obtener token, obtener listas de archivos, descargarlos y descomprimirlos.
* [Funciones para pasar datos: ](sentinel.py) Funciones para pasar parametros de polígono [arreglos], desde [fecha] y hasta [fecha].

# Requisitos
* Python https://www.python.org/
* GDAL https://gdal.org/en/latest/
* Registrarse en https://dataspace.copernicus.eu/ para acceder a las imagenes satelitales

# Instalacion
* git clone https://github.com/moshi2206/IndiceS2.git
* Crear un Virtual Environment: python -m venv env
* Activar env: source env/bin/activate
* Instalar dependencias: pip install -r requirements.txt
* Crear un archivo .env en la raiz del proyecto y agregar el siguiente contenido con los datos de registro en https://dataspace.copernicus.eu/
    USER_DATASPACE='correo registrado'
    PASSWORD_DATASPACE='password registrado'
* [Ejecutar ](sentinel.py)

# TODO
* Crear imágenes NDVI.
* Clasificación y Teledetección de nubes.

# PD
* Cada coleccion de raster puede pesar aproximadamente 1 GB.
* Es un proyecto de muestra, no prometo actualizar y/o agregar nuevas funciones.
* Use y abuse