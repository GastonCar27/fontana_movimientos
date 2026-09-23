from collections import defaultdict

from django.core.management.base import BaseCommand

from retenciones.models import Retencion


class Command(BaseCommand):
    help = (
        'Comando de sólo lectura: recorre TODA la tabla retencion agrupando por '
        '(año, numero) -- el mismo criterio que usa la pantalla de Modificar -- y '
        'reporta los grupos donde aparece más de una entidad distinta (numero de '
        'comprobante de retención repetido entre entidades). No modifica nada.'
    )

    def handle(self, *args, **options):
        grupos = defaultdict(list)
        total_filas = 0
        for r in Retencion.objects.all().only('id', 'año', 'numero', 'entidad_id', 'entidad_nombre'):
            total_filas += 1
            grupos[(r.año, r.numero)].append(r)

        self.stdout.write(f'Filas totales en `retencion`: {total_filas}')
        self.stdout.write(f'Grupos (año, numero) distintos: {len(grupos)}\n')

        conflictivos = []
        for (anio, numero), filas in grupos.items():
            entidades = {r.entidad_id for r in filas}
            if len(entidades) > 1:
                conflictivos.append((anio, numero, filas, entidades))

        if not conflictivos:
            self.stdout.write(self.style.SUCCESS('No se encontró ningún grupo (año, numero) con más de una entidad.'))
            return

        conflictivos.sort(key=lambda t: (t[0] or 0, t[1] or 0))
        self.stdout.write(self.style.ERROR(
            f'{len(conflictivos)} grupo(s) (año, numero) con MÁS DE UNA ENTIDAD (se mezclan al '
            f'editar/eliminar/imprimir desde la pantalla que agrupa por año+numero):\n'
        ))
        for anio, numero, filas, entidades in conflictivos:
            self.stdout.write(f'  {anio}-{numero}: {len(filas)} fila(s), entidades {sorted(e for e in entidades if e is not None)}')
            for r in filas:
                entidad_txt = r.entidad_nombre or (str(r.entidad_id) if r.entidad_id else 'SIN ENTIDAD')
                self.stdout.write(f'      id={r.id}  entidad_id={r.entidad_id}  entidad="{entidad_txt}"')
