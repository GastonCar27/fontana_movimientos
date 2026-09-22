"""Helpers de formato de texto reutilizados por los distintos generadores
de PDF/Excel de la aplicación (liquidaciones, solicitudes de compra, etc.),
para no reescribir la misma lógica en cada módulo de documentos."""

DIAS_SEMANA = ['lunes', 'martes', 'miércoles', 'jueves', 'viernes', 'sábado', 'domingo']
MESES = [
    'enero', 'febrero', 'marzo', 'abril', 'mayo', 'junio',
    'julio', 'agosto', 'septiembre', 'octubre', 'noviembre', 'diciembre',
]


def numero_con_puntos(valor):
    """Formatea un número entero (ej. un DNI) separando los miles con un
    punto, como se usa habitualmente en Argentina (ej. 28.333.444). Si no
    es un número válido, devuelve el valor tal cual vino."""
    if not valor:
        return ''
    try:
        entero = int(valor)
    except (TypeError, ValueError):
        return str(valor)
    return f'{entero:,}'.replace(',', '.')


def cuit_con_guiones(cuit):
    """Formatea un CUIT como XX-XXXXXXXX-X. Si no tiene 11 dígitos (dato
    incompleto o mal cargado), devuelve el valor tal cual vino."""
    if not cuit:
        return ''
    digitos = ''.join(ch for ch in str(cuit) if ch.isdigit())
    if len(digitos) == 11:
        return f'{digitos[0:2]}-{digitos[2:10]}-{digitos[10:]}'
    return str(cuit)


def fecha_larga(fecha):
    """Formatea una fecha en español, ej. 'miércoles, 26 de agosto de 2026',
    sin depender del locale del sistema operativo (que puede no estar
    configurado en español en el servidor)."""
    if not fecha:
        return ''
    dia_semana = DIAS_SEMANA[fecha.weekday()]
    return f'{dia_semana}, {fecha.day} de {MESES[fecha.month - 1]} de {fecha.year}'
