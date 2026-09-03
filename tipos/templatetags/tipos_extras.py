from django import template

register = template.Library()


@register.filter
def attr(objeto, nombre_campo):
    """Permite acceder a un atributo de un objeto usando un nombre de
    campo que llega como variable (los templates de Django no soportan
    {{ objeto.nombre_campo }} cuando 'nombre_campo' es una variable, solo
    cuando es literal), para poder dibujar el listado genérico de
    tipo_listado.html con las columnas que indique cada caso del
    registro."""
    return getattr(objeto, nombre_campo, '')
