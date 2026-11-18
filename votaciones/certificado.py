"""Certificado de resultados en PDF (P-12).

Un PDF con el resultado de cada votación publicada de la edición: quién gana, el detalle por opción
y una "huella" (código SHA-256) calculada con los datos de MySQL. Si alguien cambia un número del
documento, al volver a generarlo la huella ya no coincide: así se puede comprobar que no fue alterado.

- Si todas las votaciones están cerradas, el documento es un CERTIFICADO (resultados definitivos).
- Si alguna sigue abierta o no ha abierto, es un REPORTE PARCIAL y lo dice en grande.
No incluye ningún dato de los votantes.
"""
import hashlib
from io import BytesIO

from django.utils import timezone
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import cm
from reportlab.platypus import KeepTogether, Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Calificacion

VERDE_OSCURO = colors.HexColor("#0F2A1E")
VERDE = colors.HexColor("#1E4D36")
SOL = colors.HexColor("#F5B800")
RIO = colors.HexColor("#2BB3A0")
ROJO = colors.HexColor("#E63B2E")
GRIS = colors.HexColor("#6B7280")
BORDE = colors.HexColor("#D5DED8")
CEBRA = colors.HexColor("#F3F7F4")
DEFINITIVO = (colors.HexColor("#C6EFCE"), colors.HexColor("#006100"))
PARCIAL = (colors.HexColor("#FFEB9C"), colors.HexColor("#9C5700"))
PROXIMO = (colors.HexColor("#DDEBF7"), colors.HexColor("#1F4E79"))
PUBLICO = (colors.HexColor("#D9F2EE"), colors.HexColor("#0F6B5C"))

_base = dict(fontName="Helvetica", fontSize=9.5, leading=12.5)
TXT = ParagraphStyle("txt", **_base)
TXT_B = ParagraphStyle("txtb", **{**_base, "fontName": "Helvetica-Bold"})
CELDA = ParagraphStyle("celda", **{**_base, "fontSize": 9, "leading": 11.5})
CELDA_B = ParagraphStyle("celdab", parent=CELDA, fontName="Helvetica-Bold")
ENC = ParagraphStyle("enc", parent=CELDA_B, textColor=colors.white)
H2 = ParagraphStyle("h2", fontName="Helvetica-Bold", fontSize=13, leading=16, textColor=VERDE_OSCURO, spaceBefore=12, spaceAfter=5)
NOTA = ParagraphStyle("nota", **{**_base, "fontSize": 8.5, "leading": 11, "textColor": GRIS})


def _nombres(g):
    if g is None or not g["opciones"]:
        return ""
    nombres = " / ".join(o.nombre for o in g["opciones"])
    return f"Empate: {nombres}" if g["empate"] else nombres


def _pct(x):
    return "—" if x is None else f"{x:.1f} %".replace(".", ",")


def _datos(votaciones):
    """Calcula una sola vez los resultados de cada votación."""
    datos = []
    for v in votaciones:
        filas, total = v.resultados_ponderados()
        datos.append({
            "v": v, "filas": filas, "total": total, "g": v.ganadores(filas),
            "n_calif": Calificacion.objects.filter(votacion=v).values("jurado").distinct().count(),
        })
    return datos


def huella(edicion, datos):
    """SHA-256 de los datos que respaldan el certificado (mismos datos → misma huella)."""
    partes = [f"edicion:{edicion.pk}:{edicion.nombre}"]
    for d in datos:
        v = d["v"]
        partes.append(f"votacion:{v.pk}:{v.nombre}:{v.modo}:{v.peso_jurado}:{v.estado}:{d['total']}")
        for o in sorted(d["filas"], key=lambda o: o.pk):
            partes.append(f"opcion:{o.pk}:{o.nombre}:{o.n_votos}:{o.suma_puntaje}:{o.n_calif}")
    return hashlib.sha256("\n".join(partes).encode("utf-8")).hexdigest()


def _tabla(filas, anchos, estilos_extra=()):
    t = Table(filas, colWidths=anchos, repeatRows=1)
    t.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), VERDE),
        ("GRID", (0, 0), (-1, -1), 0.5, BORDE),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, CEBRA]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
        ("TOPPADDING", (0, 0), (-1, -1), 5), ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        *estilos_extra,
    ]))
    return t


def _pill(texto, colores):
    fondo, letra = colores
    return Paragraph(f'<font color="{letra.hexval()}"><b>{texto}</b></font>',
                     ParagraphStyle("pill", parent=CELDA, backColor=fondo, borderPadding=(2, 4, 2, 4), alignment=TA_CENTER))


def pdf_resultados(edicion, votaciones, generado_por):
    """Devuelve (bytes del PDF, huella, es_certificado)."""
    datos = _datos(votaciones)
    codigo = huella(edicion, datos)
    abiertas = [d for d in datos if not d["g"]["definitivo"]]
    es_certificado = bool(datos) and not abiertas
    ahora = timezone.localtime().strftime("%d/%m/%Y %I:%M %p").lower()
    titulo = "Certificado de resultados" if es_certificado else "Reporte parcial de resultados"

    contenido = []

    # --- Estado del documento ---
    if es_certificado:
        aviso, (fondo, letra) = ("<b>CERTIFICADO.</b> Todas las votaciones están cerradas: los resultados son definitivos.",
                                 DEFINITIVO)
    elif not datos:
        aviso, (fondo, letra) = ("<b>SIN DATOS.</b> No hay votaciones publicadas en esta edición.", PROXIMO)
    else:
        aviso, (fondo, letra) = (f"<b>REPORTE PARCIAL — NO ES UN CERTIFICADO.</b> Hay {len(abiertas)} "
                                 f"{'votación' if len(abiertas) == 1 else 'votaciones'} sin cerrar: los resultados pueden cambiar.",
                                 PARCIAL)
    contenido.append(Paragraph(aviso, ParagraphStyle("aviso", parent=TXT, fontSize=10.5, leading=14, textColor=letra,
                                                      backColor=fondo, borderPadding=(8, 10, 8, 10))))
    contenido.append(Spacer(1, 14))

    # --- Resumen ---
    contenido.append(Paragraph("Resumen: quién gana en cada votación", H2))
    filas = [[Paragraph(t, ENC) for t in ("Categoría", "Votación", "Estado", "Ganador / va ganando")]]
    for d in datos:
        v, g = d["v"], d["g"]
        estado = {"abierta": PARCIAL, "cerrada": DEFINITIVO, "proxima": PROXIMO}.get(v.estado, PROXIMO)
        ganador = _nombres(g["oficial"]) or ("Jurado aún sin calificar" if v.tiene_jurado else "Sin votos todavía")
        va_ganando = g["oficial"]["opciones"] and not g["definitivo"]
        texto = f"<b>{ganador}</b>" + (' <font color="#9C5700">(va ganando)</font>' if va_ganando else "")
        if v.es_independiente:
            texto += f'<br/><font color="#0F6B5C">Público: {_nombres(g["publico"]) or "sin votos"}</font>'
        filas.append([Paragraph(v.categoria.nombre, CELDA), Paragraph(v.nombre, CELDA_B),
                      _pill(v.estado_etiqueta, estado), Paragraph(texto, CELDA)])
    if not datos:
        filas.append([Paragraph("No hay votaciones publicadas.", CELDA), "", "", ""])
    contenido.append(_tabla(filas, [3.6 * cm, 4.6 * cm, 2.4 * cm, 6.4 * cm]))

    # --- Detalle por votación ---
    for d in datos:
        v, g, total = d["v"], d["g"], d["total"]
        bloque = [Paragraph(f"{v.categoria.nombre} · {v.nombre}", H2),
                  Paragraph(f"{v.modalidad} · {v.estado_etiqueta} · {total} voto{'s' if total != 1 else ''} del público"
                            + (f" · {d['n_calif']}/{v.jurados.count()} jurados calificaron" if v.tiene_jurado else "")
                            + f" · Cierre: {timezone.localtime(v.cierre).strftime('%d/%m/%Y %I:%M %p').lower()}", NOTA),
                  Spacer(1, 5)]
        columnas = [("Opción", 5.2 * cm, lambda o: o.nombre)]
        if v.tiene_publico:
            columnas += [("Votos", 1.6 * cm, lambda o: str(o.n_votos)), ("% público", 2 * cm, lambda o: _pct(o.pct_publico))]
        if v.tiene_jurado:
            columnas += [("Prom. jurado", 2.2 * cm, lambda o: "—" if o.promedio is None else f"{o.promedio:.2f}".replace(".", ",")),
                         ("% jurado", 2 * cm, lambda o: _pct(o.pct_jurado))]
        if v.es_combinado:
            columnas.append(("Final", 1.8 * cm, lambda o: _pct(o.final)))
        sobra = 17 * cm - sum(c[1] for c in columnas)
        columnas.append(("Resultado", max(sobra, 2.4 * cm), None))

        oficiales = set(g["oficial"]["opciones"])
        publicos = set(g["publico"]["opciones"]) if g["publico"] else set()
        palabra = "Ganador" if g["definitivo"] else "Va ganando"
        filas = [[Paragraph(c[0], ENC) for c in columnas]]
        resaltes = []
        for i, o in enumerate(d["filas"], start=1):
            marca = []
            if o in oficiales:
                marca.append(f"{palabra} (jurado)" if v.es_independiente else palabra)
            if o in publicos:
                marca.append(f"{palabra} (público)")
            fila = [Paragraph(f(o), CELDA_B if marca and j == 0 else CELDA) if f else Paragraph(" + ".join(marca), CELDA_B)
                    for j, (_, _, f) in enumerate(columnas)]
            filas.append(fila)
            if marca:
                fondo = (DEFINITIVO if g["definitivo"] else PARCIAL)[0] if o in oficiales else PUBLICO[0]
                resaltes.append(("BACKGROUND", (0, i), (-1, i), fondo))
        bloque.append(_tabla(filas, [c[1] for c in columnas], resaltes))
        if g["oficial"]["empate"] or (g["publico"] and g["publico"]["empate"]):
            bloque.append(Paragraph("Hay un empate. El criterio de desempate está pendiente de definir con la Fundación (RN-12).", NOTA))
        contenido.append(KeepTogether(bloque))

    # --- Huella y firmas ---
    grupos = " ".join(codigo[i:i + 8] for i in range(0, len(codigo), 8))
    contenido.append(Spacer(1, 16))
    contenido.append(KeepTogether([
        Paragraph("Huella de verificación (SHA-256)", H2),
        Paragraph(f'<font name="Courier-Bold" size="10">{grupos}</font>',
                  ParagraphStyle("huella", parent=TXT, backColor=colors.HexColor("#F3F4F6"), borderPadding=(7, 8, 7, 8))),
        Spacer(1, 8),
        Paragraph("Se calcula con los votos y calificaciones guardados en MySQL. Si se vuelve a generar el documento "
                  "con los mismos datos, sale la misma huella; si alguien altera un número, ya no coincide. "
                  "Cada descarga queda registrada en la auditoría con su huella.", NOTA),
    ]))
    if es_certificado:
        firma = [[Paragraph("_____________________________<br/>Delegado de la Fundación", ParagraphStyle("f", parent=CELDA, alignment=TA_CENTER)),
                  Paragraph("_____________________________<br/>Presidente del jurado", ParagraphStyle("f", parent=CELDA, alignment=TA_CENTER)),
                  Paragraph("_____________________________<br/>Administrador del sistema", ParagraphStyle("f", parent=CELDA, alignment=TA_CENTER))]]
        contenido.append(Spacer(1, 30))
        contenido.append(KeepTogether([Table(firma, colWidths=[5.67 * cm] * 3),
                                       Spacer(1, 4),
                                       Paragraph("Firmas propuestas; quiénes firman está pendiente de confirmar con la Fundación (P-12).", NOTA)]))

    def pagina(cv, doc):
        ancho, alto = letter
        cv.saveState()
        cv.setFillColor(VERDE_OSCURO)
        cv.rect(0, alto - 3.1 * cm, ancho, 3.1 * cm, stroke=0, fill=1)
        for i, color in enumerate((ROJO, SOL, RIO)):
            cv.setFillColor(color)
            cv.rect(i * ancho / 3, alto - 3.1 * cm - 5, ancho / 3, 5, stroke=0, fill=1)
        cv.setFillColor(SOL)
        cv.setFont("Helvetica-Bold", 18)
        cv.drawString(2 * cm, alto - 1.45 * cm, titulo)
        cv.setFillColor(colors.white)
        cv.setFont("Helvetica", 9.5)
        cv.drawString(2 * cm, alto - 2.05 * cm, f"Tu Voto Vallenato · {edicion.nombre}")
        cv.drawString(2 * cm, alto - 2.55 * cm, f"Generado el {ahora} por {generado_por}")
        if not es_certificado and datos:
            cv.setFillColor(SOL)
            cv.setFont("Helvetica-Bold", 10)
            cv.drawRightString(ancho - 2 * cm, alto - 1.45 * cm, "NO ES CERTIFICADO")
        cv.setFillColor(GRIS)
        cv.setFont("Helvetica", 8)
        cv.drawString(2 * cm, 1.2 * cm, f"Huella: {codigo[:16]}…  ·  Sin datos de los votantes")
        cv.drawRightString(ancho - 2 * cm, 1.2 * cm, f"Página {doc.page}")
        cv.restoreState()

    salida = BytesIO()
    SimpleDocTemplate(salida, pagesize=letter, leftMargin=2 * cm, rightMargin=2 * cm, topMargin=3.9 * cm,
                      bottomMargin=2 * cm, title=f"{titulo} · {edicion.nombre}", author="Tu Voto Vallenato"
                      ).build(contenido, onFirstPage=pagina, onLaterPages=pagina)
    return salida.getvalue(), codigo, es_certificado
