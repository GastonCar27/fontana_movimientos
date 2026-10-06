"""
Carga las reglas "cuenta + concepto -> destinatario" (ReglaDestinatarioConcepto)
para un banco, con los mismos conceptos que usa el comando de corrección
asignar_destinatario_banco_macro (06/10/2026):

    cheque pago clearing, comision pago proveedores, comision valores al cobro,
    echeq emision, mantenimiento cuenta, comision transferencia,
    comision adm. de chequeras  -> sin tope
    comercio exterior            -> sólo si el monto es menor a $100.000

Desde que existen las reglas, los movimientos nuevos con esos conceptos
reciben el destinatario solos al guardarlos (y su IVA / percepción del mismo
día también). No pisa reglas que ya existan para la misma cuenta + concepto.

Por defecto es DRY RUN. Pasar --aplicar para guardar.

Uso:
    python manage.py cargar_reglas_destinatario                    # Banco Macro
    python manage.py cargar_reglas_destinatario --banco nacion
    python manage.py cargar_reglas_destinatario --banco nacion --aplicar
"""
from django.core.management.base import BaseCommand

from movimientos_caja.management.commands.asignar_destinatario_banco_macro import (
    CONCEPTOS, CONCEPTOS_CON_TOPE, TOPE_COMERCIO_EXTERIOR, Command as AsignarCommand, _normalizar,
)
from movimientos_caja.models import MovimientoCajaConceptoTipo, ReglaDestinatarioConcepto


class Command(BaseCommand):
    help = 'Crea las reglas de destinatario por concepto para la cuenta de un banco. Dry-run salvo --aplicar.'

    def add_arguments(self, parser):
        parser.add_argument('--banco', default='macro')
        parser.add_argument('--caja', type=int)
        parser.add_argument('--entidad', type=int)
        parser.add_argument('--aplicar', action='store_true')

    def handle(self, *args, **o):
        banco = (o.get('banco') or 'macro').strip()
        auxiliar = AsignarCommand()
        caja = auxiliar._caja_macro(o.get('caja'), banco)
        entidad = auxiliar._entidad_macro(o.get('entidad'), banco)
        self.stdout.write(f'Cuenta: {caja}\nDestinatario: {entidad.id} - {entidad.nombre}\n')

        sin_tope = {_normalizar(c) for c in CONCEPTOS}
        con_tope = {_normalizar(c) for c in CONCEPTOS_CON_TOPE}
        a_crear, ya = [], []
        for concepto in MovimientoCajaConceptoTipo.objects.all().order_by('nombre'):
            n = _normalizar(concepto.nombre)
            if n not in sin_tope and n not in con_tope:
                continue
            tope = TOPE_COMERCIO_EXTERIOR if n in con_tope else None
            existente = ReglaDestinatarioConcepto.objects.filter(caja=caja, concepto=concepto).first()
            if existente:
                ya.append(existente)
            else:
                a_crear.append((concepto, tope))

        for concepto, tope in a_crear:
            self.stdout.write(f'  nueva: {concepto.nombre} -> {entidad.nombre}' + (f' (sólo si < {tope})' if tope else ''))
        for r in ya:
            self.stdout.write(f'  ya existe: {r.concepto.nombre} -> {r.entidad.nombre}' +
                              (f' (< {r.monto_maximo})' if r.monto_maximo else '') + ('' if r.activa else ' [inactiva]'))
        if not a_crear:
            self.stdout.write(self.style.SUCCESS('\nNo hay reglas nuevas para crear.'))
            return
        if not o['aplicar']:
            self.stdout.write(self.style.WARNING('\nEsto fue un DRY RUN. Volvé a correr con --aplicar para guardar.'))
            return
        for concepto, tope in a_crear:
            ReglaDestinatarioConcepto.objects.create(caja=caja, concepto=concepto, entidad=entidad, monto_maximo=tope)
        self.stdout.write(self.style.SUCCESS(f'\nListo -- se crearon {len(a_crear)} regla(s).'))
