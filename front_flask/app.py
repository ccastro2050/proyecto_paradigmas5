"""
app.py — La capa de PRESENTACIÓN del sistema.

Estas son las vistas: reciben lo que el usuario hizo en el navegador, se lo
piden a `cliente_api`, y eligen qué plantilla mostrar. Nada más.

Las tres reglas de este archivo:

1. **No habla con la base de datos.** Ni siquiera sabe que existen tres
   motores. Todo lo pide por HTTP a la API. Ese es el punto entero de la v5.
2. **No valida negocio.** Si un stock negativo está mal, lo dice la API con un
   422 y aquí solo se muestra. Duplicar la regla en el front es tener dos
   dueños de la misma verdad.
3. **No arma SQL, ni JSON de la base.** Recibe diccionarios ya traducidos.
"""

import os

from flask import Flask, flash, redirect, render_template, request, url_for

import cliente_api

app = Flask(__name__)

# `flash` guarda los avisos en la sesión, y la sesión va firmada: sin clave,
# Flask no arranca. En un proyecto real esto vive en un .env fuera de git.
app.secret_key = os.environ.get("CLAVE_SESION", "Paradigmas123!Sesion")

PUERTO = int(os.environ.get("PUERTO", 8008))


def _avisar(errores: list[str]) -> None:
    """Cada error de la API se muestra como un aviso rojo, uno por línea."""
    for mensaje in errores:
        flash(mensaje, "error")


# ----------------------------------------------------------------------
# La raíz lleva a lo único que existe en esta versión
# ----------------------------------------------------------------------
@app.route("/")
def inicio():
    return redirect(url_for("listar"))


# ----------------------------------------------------------------------
# RF1 — Listar productos
# ----------------------------------------------------------------------
@app.route("/productos")
def listar():
    ok, productos, errores = cliente_api.listar_productos()
    if not ok:
        _avisar(errores)
    # Aun con error se renderiza la página: el usuario ve el aviso dentro de
    # la aplicación, no una pantalla de excepción de Flask.
    return render_template("productos/lista.html", productos=productos)


# ----------------------------------------------------------------------
# RF2 — Crear un producto
# ----------------------------------------------------------------------
@app.route("/productos/nuevo", methods=["GET", "POST"])
def crear():
    if request.method == "GET":
        return render_template("productos/formulario.html", producto=None)

    datos = {
        "codigo": request.form.get("codigo", "").strip(),
        "nombre": request.form.get("nombre", "").strip(),
        # Se envían como texto tal cual llegan del formulario: convertirlos
        # aquí sería adelantarse a la validación de la API. Si "abc" no es un
        # entero, que lo diga el 422 — así el estudiante VE la frontera.
        "stock": request.form.get("stock", "").strip(),
        "valorunitario": request.form.get("valorunitario", "").strip(),
    }

    ok, errores = cliente_api.crear_producto(datos)
    if ok:
        flash(f"Producto {datos['codigo']} creado.", "exito")
        return redirect(url_for("listar"))

    _avisar(errores)
    # Se devuelve el formulario CON lo que el usuario había escrito: perder lo
    # digitado por un error de validación es castigar al usuario dos veces.
    return render_template("productos/formulario.html", producto=datos)


# ----------------------------------------------------------------------
# RF3 y RF4 — Editar: la MISMA pantalla, dos botones, dos verbos
# ----------------------------------------------------------------------
@app.route("/productos/<codigo>/editar", methods=["GET", "POST"])
def editar(codigo):
    if request.method == "GET":
        ok, producto, errores = cliente_api.obtener_producto(codigo)
        if not ok:
            _avisar(errores)
            return redirect(url_for("listar"))
        return render_template("productos/formulario.html", producto=producto)

    # Qué botón se oprimió decide el verbo. La diferencia NO está en un if de
    # negocio: está en qué se envía.
    verbo = request.form.get("verbo", "patch")

    campos = {
        "nombre": request.form.get("nombre", "").strip(),
        "stock": request.form.get("stock", "").strip(),
        "valorunitario": request.form.get("valorunitario", "").strip(),
    }

    if verbo == "put":
        # PUT: reemplazo COMPLETO. Los tres campos viajan aunque estén vacíos,
        # y por eso un campo en blanco responde 422. Es la semántica de PUT.
        ok, errores = cliente_api.reemplazar_producto(codigo, campos)
        hecho = "reemplazado (PUT)"
    else:
        # PATCH: viaja SOLO lo diligenciado. El mismo formulario a medio
        # llenar que el PUT rechaza, aquí funciona.
        parciales = {k: v for k, v in campos.items() if v != ""}
        if not parciales:
            flash("No diligenció ningún campo: no hay nada que actualizar.", "error")
            return redirect(url_for("editar", codigo=codigo))
        ok, errores = cliente_api.actualizar_producto(codigo, parciales)
        hecho = "actualizado (PATCH)"

    if ok:
        flash(f"Producto {codigo} {hecho}.", "exito")
        return redirect(url_for("listar"))

    _avisar(errores)
    return render_template(
        "productos/formulario.html", producto={"codigo": codigo, **campos}
    )


# ----------------------------------------------------------------------
# RF5 — Eliminar
# ----------------------------------------------------------------------
@app.route("/productos/<codigo>/eliminar", methods=["POST"])
def eliminar(codigo):
    # Se exige POST a propósito: un enlace GET que borra lo puede disparar el
    # navegador solo al precargar la página.
    ok, errores = cliente_api.eliminar_producto(codigo)
    if ok:
        flash(f"Producto {codigo} eliminado.", "exito")
    else:
        _avisar(errores)
    return redirect(url_for("listar"))


if __name__ == "__main__":
    # host 0.0.0.0: dentro del contenedor hay que escuchar en todas las
    # interfaces, o el puerto publicado no llega a ninguna parte.
    app.run(host="0.0.0.0", port=PUERTO, debug=True)
