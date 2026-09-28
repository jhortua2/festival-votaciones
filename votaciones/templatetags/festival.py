"""Etiquetas de plantilla: íconos SVG, clase de estado y tiempo restante."""
from django import template
from django.utils import timezone
from django.utils.safestring import mark_safe

register = template.Library()

_ICONOS = {
    "acordeon": '<svg viewBox="0 0 64 64" fill="none" stroke="{t}" stroke-width="3" stroke-linejoin="round" aria-hidden="true"><rect x="6" y="14" width="12" height="36" rx="3" fill="{f}"/><rect x="46" y="14" width="12" height="36" rx="3" fill="{f}"/><path d="M18 16l5 32 5-32 4 32 4-32 5 32 5-32"/></svg>',
    "pollera": '<svg viewBox="0 0 64 64" fill="none" stroke="{t}" stroke-width="3" stroke-linejoin="round" aria-hidden="true"><circle cx="32" cy="12" r="6" fill="{f}"/><path d="M26 22h12l4 14H22z" fill="{f}"/><path d="M22 36c-8 6-12 14-12 20h44c0-6-4-14-12-20"/><path d="M14 48c6 3 30 3 36 0"/></svg>',
    "sombrero": '<svg viewBox="0 0 64 64" fill="none" stroke="{t}" stroke-width="3" stroke-linejoin="round" aria-hidden="true"><ellipse cx="32" cy="42" rx="26" ry="8" fill="{f}"/><path d="M20 40c0-14 4-22 12-22s12 8 12 22"/><path d="M21 34h22M22 28h20"/></svg>',
    "caja": '<svg viewBox="0 0 64 64" fill="none" stroke="{t}" stroke-width="3" stroke-linejoin="round" aria-hidden="true"><path d="M16 14h32l-4 40H20z" fill="{f}"/><ellipse cx="32" cy="14" rx="16" ry="5" fill="{f}"/><path d="M18 26l28 8M18 34l28-8"/></svg>',
}


@register.simple_tag
def icono(nombre, trazo="#ffffff", relleno="#0D271E"):
    svg = _ICONOS.get(nombre, _ICONOS["acordeon"])
    return mark_safe(svg.format(t=trazo, f=relleno))


@register.filter
def pill(estado):
    return f"pill pill-{estado}"


@register.simple_tag
def restante(votacion):
    """Días, horas y minutos hasta el cierre."""
    delta = votacion.cierre - timezone.now()
    s = max(int(delta.total_seconds()), 0)
    return {"dias": s // 86400, "horas": (s % 86400) // 3600, "minutos": (s % 3600) // 60}
