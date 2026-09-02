"""
cliente_api.py — La capa de DATOS del front.

Es al front lo que el repositorio es al back: la ÚNICA pieza que sabe dónde
viven los datos —en la API, nunca en la base— y la única que habla HTTP.
Traduce cada respuesta a una tupla `(ok, datos, errores)` para que las vistas
no tengan que saber qué es un código 422.

Aquí no se decide negocio. Si algo se puede o no se puede hacer, lo dice la
API; este archivo solo pregunta y traduce la respuesta.
"""

import os

import requests

# El hostname INTERNO del compose (api-facturas), jamás localhost: dentro de
# un contenedor, localhost es él mismo. El valor de respaldo sirve para correr
# el front fuera de Docker.
URL_API = os.environ.get("API_FACTURAS_URL", "http://localhost:8007")

# Si la API no contesta en este tiempo, el front lo dice en pantalla en vez de
# quedarse colgado esperando.
TIEMPO_MAXIMO = 10  # segundos


def _llamar(metodo: str, ruta: str, **kwargs):
    """Ejecuta la petición y unifica un solo caso: 'la API no responde'.

    Devuelve None cuando no hubo respuesta —API caída, DNS, timeout—, que es
    distinto de 'respondió con un error'. Esa diferencia importa: un 404 es la
    API funcionando y diciendo que no existe; un None es que no hay con quién
    hablar.
    """
    try:
        return requests.request(
            metodo, f"{URL_API}{ruta}", timeout=TIEMPO_MAXIMO, **kwargs
        )
    except requests.RequestException:
        return None


def _cuerpo(respuesta):
    """El JSON de la respuesta, o un diccionario vacío si no vino JSON.

    Un 500 del servidor puede llegar como HTML; sin esto, el front se caería
    justo cuando tiene que explicar que algo falló.
    """
    try:
        return respuesta.json()
    except ValueError:
        return {}


def _mensajes(respuesta) -> list[str]:
    """Traduce a texto los dos formatos de error que produce esta API.

    FastAPI anida SIEMPRE bajo la llave `detail`, pero con dos formas distintas:

    1. Los errores que la API escribe a propósito (400, 404, 500) llegan como
       un diccionario:
           {"detail": {"estado": 404, "mensaje": "…", "detalle": "…"}}

    2. Los 422 los genera Pydantic solo, y llegan como una LISTA, con el campo
       culpable en `loc` y la explicación en `msg`, en inglés:
           {"detail": [{"loc": ["body", "stock"], "msg": "…", …}]}

    Que este archivo conozca las dos formas es justamente su trabajo: es la
    frontera. Las vistas reciben una lista de frases y no se enteran de nada.
    """
    detalle = _cuerpo(respuesta).get("detail")

    if isinstance(detalle, dict):
        texto = detalle.get("mensaje", "")
        extra = detalle.get("detalle", "")
        return [t for t in (texto, extra) if t] or ["No se pudo completar la operación."]

    if isinstance(detalle, list):
        frases = []
        for error in detalle:
            campo = error.get("loc", ["", ""])[-1]
            frases.append(f"{campo}: {error.get('msg', 'valor inválido')}")
        return frases or ["Datos inválidos."]

    if isinstance(detalle, str) and detalle:
        return [detalle]

    return ["No se pudo completar la operación."]


NO_DISPONIBLE = ["El servicio no está disponible. ¿Está arriba la API?"]


def listar_productos():
    """GET /api/producto → (ok, lista, errores).

    El 204 NO es un error: es la tabla vacía. Se devuelve como lista vacía y
    la pantalla dirá 'no hay productos', no 'algo falló'.
    """
    respuesta = _llamar("GET", "/api/producto")
    if respuesta is None:
        return False, [], NO_DISPONIBLE
    if respuesta.status_code == 204:
        return True, [], []
    if respuesta.status_code == 200:
        return True, _cuerpo(respuesta).get("datos", []), []
    return False, [], _mensajes(respuesta)


def obtener_producto(codigo: str):
    """GET /api/producto/{codigo} → (ok, producto, errores)."""
    respuesta = _llamar("GET", f"/api/producto/{codigo}")
    if respuesta is None:
        return False, None, NO_DISPONIBLE
    if respuesta.status_code == 200:
        return True, _cuerpo(respuesta), []
    return False, None, _mensajes(respuesta)


def crear_producto(datos: dict):
    """POST /api/producto → (ok, errores). Los cuatro campos son obligatorios."""
    respuesta = _llamar("POST", "/api/producto", json=datos)
    if respuesta is None:
        return False, NO_DISPONIBLE
    if respuesta.status_code == 200:
        return True, []
    return False, _mensajes(respuesta)


def reemplazar_producto(codigo: str, datos: dict):
    """PUT /api/producto/{codigo} → (ok, errores).

    Reemplazo COMPLETO: los tres campos viajan siempre. Omitir uno es 422, y
    eso es lo que se quiere mostrar en pantalla junto al PATCH de abajo.
    """
    respuesta = _llamar("PUT", f"/api/producto/{codigo}", json=datos)
    if respuesta is None:
        return False, NO_DISPONIBLE
    if respuesta.status_code == 200:
        return True, []
    return False, _mensajes(respuesta)


def actualizar_producto(codigo: str, datos: dict):
    """PATCH /api/producto/{codigo} → (ok, errores).

    Actualización PARCIAL: viaja SOLO lo que el usuario diligenció. El mismo
    formulario que por PUT daría 422 aquí responde 200, y esa pareja es la
    lección de la pantalla de edición.
    """
    respuesta = _llamar("PATCH", f"/api/producto/{codigo}", json=datos)
    if respuesta is None:
        return False, NO_DISPONIBLE
    if respuesta.status_code == 200:
        return True, []
    return False, _mensajes(respuesta)


def eliminar_producto(codigo: str):
    """DELETE /api/producto/{codigo} → (ok, errores)."""
    respuesta = _llamar("DELETE", f"/api/producto/{codigo}")
    if respuesta is None:
        return False, NO_DISPONIBLE
    if respuesta.status_code == 200:
        return True, []
    return False, _mensajes(respuesta)
