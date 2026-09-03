from django.db import models


class Empleado(models.Model):
    """Empleados de la empresa.

    Por ahora tiene lo mínimo necesario para poder elegir un empleado como
    solicitante/responsable de retiro en una solicitud de compra. Es un
    modelo aparte de Entidad (que representa proveedores/clientes/terceros,
    no personal propio) a propósito: cuando se arme el módulo de Recursos
    Humanos, este mismo modelo se amplía (legajo, puesto, fecha de alta/
    baja, etc.) sin tener que migrar ni tocar Entidad para nada.
    """
    nombre = models.CharField(max_length=100)
    apellido = models.CharField(max_length=100)
    documento = models.CharField('DNI', max_length=20, blank=True)
    activo = models.BooleanField(default=True)
    creado = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'empleado'
        ordering = ['apellido', 'nombre']

    def __str__(self):
        return f'{self.apellido}, {self.nombre}'.strip(', ')

    @property
    def nombre_completo(self):
        return f'{self.nombre} {self.apellido}'.strip()
