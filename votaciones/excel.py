"""Descarga de resultados en Excel (.xlsx) desde el panel.

Una hoja "Resumen" con quién gana (o va ganando) en cada votación publicada de la edición,
y una hoja de detalle por votación. No incluye ningún dato de los votantes.
"""
import re
from io import BytesIO

from django.utils import timezone
from openpyxl import Workbook
from openpyxl.formatting.rule import DataBarRule
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from .models import Calificacion


def _letra(**kw):
    return Font(name="Calibri", size=kw.pop("size", 11), **kw)

# Colores del sistema: verde oscuro del panel, amarillo "sol" y turquesa "río"
VERDE_OSCURO, VERDE, SOL, RIO = "0F2A1E", "1E4D36", "F5B800", "2BB3A0"
BORDE = Border(*(Side(style="thin", color="D5DED8"),) * 4)
CEBRA = PatternFill("solid", fgColor="F3F7F4")
# (relleno, color de letra) para los estados
DEFINITIVO = ("C6EFCE", "006100")
PARCIAL = ("FFEB9C", "9C5700")
PROXIMO = ("DDEBF7", "1F4E79")
NEUTRO = ("EDEDED", "595959")
PUBLICO = ("D9F2EE", "0F6B5C")


def _pinta(celda, colores, negrita=False):
    relleno, letra = colores
    celda.fill = PatternFill("solid", fgColor=relleno)
    celda.font = _letra(bold=negrita, color=letra)


def _nombres(g):
    """Texto del ganador: 'A' o 'Empate: A / B'. Vacío si nadie tiene votos o puntaje."""
    if g is None or not g["opciones"]:
        return ""
    nombres = " / ".join(o.nombre for o in g["opciones"])
    return f"Empate: {nombres}" if g["empate"] else nombres


def _nombre_hoja(texto, usados):
    base = re.sub(r"[\[\]:*?/\\]", "", texto)[:28].strip() or "Votacion"
    nombre, n = base, 2
    while nombre.lower() in usados:
        nombre, n = f"{base[:25]} ({n})", n + 1
    usados.add(nombre.lower())
    return nombre


def _encabezado(ws, fila, columnas):
    for i, texto in enumerate(columnas, start=1):
        celda = ws.cell(row=fila, column=i, value=texto)
        celda.font = _letra(bold=True, color="FFFFFF")
        celda.fill = PatternFill("solid", fgColor=VERDE)
        celda.alignment = Alignment(wrap_text=True, vertical="center", horizontal="center")
        celda.border = BORDE
    ws.row_dimensions[fila].height = 32


def _titulo(ws, titulo, subtitulo, n_columnas):
    """Franja verde oscuro con el título en amarillo, ocupando todo el ancho de la tabla."""
    ultima = get_column_letter(max(n_columnas, 2))
    for fila, texto, fuente, alto in ((1, titulo, _letra(bold=True, size=16, color=SOL), 30),
                                      (2, subtitulo, _letra(size=10, color="FFFFFF"), 20)):
        ws.merge_cells(f"A{fila}:{ultima}{fila}")
        celda = ws.cell(row=fila, column=1, value=texto)
        celda.font, celda.alignment = fuente, Alignment(vertical="center", indent=1)
        for col in range(1, max(n_columnas, 2) + 1):
            ws.cell(row=fila, column=col).fill = PatternFill("solid", fgColor=VERDE_OSCURO)
        ws.row_dimensions[fila].height = alto


def _fila(ws, r, n_columnas, cebra):
    for col in range(1, n_columnas + 1):
        celda = ws.cell(row=r, column=col)
        celda.border = BORDE
        celda.alignment = Alignment(vertical="center")
        if cebra:
            celda.fill = CEBRA
    ws.row_dimensions[r].height = 20


def _hoja_horizontal(ws):
    """Al imprimir: horizontal y todas las columnas en una sola página de ancho."""
    ws.page_setup.orientation = "landscape"
    ws.page_setup.fitToWidth, ws.page_setup.fitToHeight = 1, 0
    ws.sheet_properties.pageSetUpPr.fitToPage = True
    ws.sheet_view.showGridLines = False


def _barras(ws, col, primera, ultima, color):
    if ultima >= primera:
        letra = get_column_letter(col)
        ws.conditional_formatting.add(f"{letra}{primera}:{letra}{ultima}",
                                      DataBarRule(start_type="num", start_value=0, end_type="num", end_value=1,
                                                  color=color, showValue=True))


def _anchos(ws, anchos):
    for i, ancho in enumerate(anchos, start=1):
        ws.column_dimensions[get_column_letter(i)].width = ancho


def _pct(x):
    return round(x / 100, 4) if x is not None else None


def libro_resultados(edicion, votaciones):
    """Devuelve los bytes del .xlsx con el resumen y el detalle de cada votación."""
    wb = Workbook()
    resumen = wb.active
    resumen.title = "Resumen"
    ahora = timezone.localtime().strftime("%Y-%m-%d %H:%M")

    columnas = ["Categoría", "Votación", "Modo", "Estado", "Votos del público", "Jurados que calificaron",
                "Resultado", "Ganador / va ganando", "Reconocimiento del público (modo independiente)"]
    _titulo(resumen, f"Resultados · {edicion.nombre}",
            f"Generado: {ahora}  ·  Verde = ganador definitivo  ·  Amarillo = va ganando (votación abierta)",
            len(columnas))
    _encabezado(resumen, 4, columnas)
    _anchos(resumen, [26, 30, 28, 12, 11, 12, 13, 32, 32])
    _hoja_horizontal(resumen)

    usados = {"resumen"}
    for fila, v in enumerate(votaciones, start=5):
        filas, total = v.resultados_ponderados()
        g = v.ganadores(filas)
        n_calif = Calificacion.objects.filter(votacion=v).values("jurado").distinct().count()
        estado = v.estado
        resumen.append([
            v.categoria.nombre, v.nombre, v.modalidad, v.estado_etiqueta, total,
            f"{n_calif}/{v.jurados.count()}" if v.tiene_jurado else "—",
            "Definitivo" if g["definitivo"] else ("Aún no abre" if estado == "proxima" else "Parcial"),
            _nombres(g["oficial"]) or ("Jurado aún sin calificar" if v.tiene_jurado else "Sin votos todavía"),
            (_nombres(g["publico"]) or "Sin votos todavía") if v.es_independiente else "—",
        ])
        _fila(resumen, fila, len(columnas), cebra=fila % 2 == 0)
        resumen.cell(row=fila, column=2).font = _letra(bold=True)
        for col in (4, 5, 6, 7):
            resumen.cell(row=fila, column=col).alignment = Alignment(horizontal="center", vertical="center")
        color_estado = {"abierta": DEFINITIVO, "cerrada": NEUTRO, "proxima": PROXIMO}.get(estado, NEUTRO)
        _pinta(resumen.cell(row=fila, column=4), color_estado, negrita=True)
        color_resultado = DEFINITIVO if g["definitivo"] else (PROXIMO if estado == "proxima" else PARCIAL)
        _pinta(resumen.cell(row=fila, column=7), color_resultado)
        ganador = resumen.cell(row=fila, column=8)
        if g["oficial"]["opciones"]:
            _pinta(ganador, DEFINITIVO if g["definitivo"] else PARCIAL, negrita=True)
        else:
            ganador.font = _letra(italic=True, color="8A8A8A")
        if v.es_independiente and g["publico"] and g["publico"]["opciones"]:
            _pinta(resumen.cell(row=fila, column=9), PUBLICO, negrita=True)

        # Hoja de detalle de la votación
        ws = wb.create_sheet(_nombre_hoja(v.nombre, usados))
        # Columnas según el modo: solo las que aplican a esta votación
        columnas_detalle = [("Opción", 32, None, lambda o: o.nombre)]
        if v.tiene_publico:
            columnas_detalle += [("Votos del público", 12, None, lambda o: o.n_votos),
                                 ("% público", 11, "0.0%", lambda o: _pct(o.pct_publico))]
        if v.tiene_jurado:
            columnas_detalle += [("Promedio jurado", 12, None,
                                  lambda o: round(o.promedio, 2) if o.promedio is not None else None),
                                 ("% jurado", 11, "0.0%", lambda o: _pct(o.pct_jurado))]
        if v.es_combinado:
            columnas_detalle.append(("Resultado final %", 13, "0.0%", lambda o: _pct(o.final)))
        columnas_detalle.append(("Gana", 22, None, None))
        _titulo(ws, f"{v.categoria.nombre} · {v.nombre}",
                f"{v.modalidad}  ·  {v.estado_etiqueta}  ·  {total} votos del público  ·  generado {ahora}",
                len(columnas_detalle))
        _encabezado(ws, 4, [c[0] for c in columnas_detalle])
        _anchos(ws, [c[1] for c in columnas_detalle])
        _hoja_horizontal(ws)
        oficiales = set(g["oficial"]["opciones"])
        publicos = set(g["publico"]["opciones"]) if g["publico"] else set()
        for o in filas:
            marca = []
            texto = "Ganador" if g["definitivo"] else "Va ganando"
            if o in oficiales:
                marca.append(f"{texto} (jurado)" if v.es_independiente else texto)
            if o in publicos:
                marca.append(f"{texto} (público)")
            ws.append([f(o) if f else " + ".join(marca) for _, _, _, f in columnas_detalle])
            r = ws.max_row
            _fila(ws, r, len(columnas_detalle), cebra=r % 2 == 0)
            for col, (_, _, formato, _) in enumerate(columnas_detalle, start=1):
                if formato:
                    ws.cell(row=r, column=col).number_format = formato
            if marca:
                if o in oficiales:
                    colores = DEFINITIVO if g["definitivo"] else PARCIAL
                else:
                    colores = PUBLICO                           # solo reconocimiento del público
                for col in (1, len(columnas_detalle)):
                    _pinta(ws.cell(row=r, column=col), colores, negrita=True)
        # Barras de color dentro de las celdas de porcentaje
        ultima = 4 + len(filas)
        for col, (nombre, _, _, _) in enumerate(columnas_detalle, start=1):
            color = {"% público": RIO, "% jurado": SOL, "Resultado final %": "3F8F5F"}.get(nombre)
            if color:
                _barras(ws, col, 5, ultima, color)
        ws.freeze_panes = "A5"

    if not votaciones:
        resumen.append(["Aún no hay votaciones publicadas."])
    else:
        resumen.auto_filter.ref = f"A4:{get_column_letter(len(columnas))}{4 + len(votaciones)}"
    resumen.freeze_panes = "A5"

    salida = BytesIO()
    wb.save(salida)
    return salida.getvalue()
