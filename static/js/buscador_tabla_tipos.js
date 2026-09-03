// Buscador dinámico (sin recargar la página) para las tablas de listado de
// los catálogos "tipo" (producto_tipo, sector_tipo, Ret. Impuestos,
// Ret. Regimenes, etc.): filtra las filas por Id o por Nombre a medida
// que se escribe, sin pegarle al servidor.
//
// Se activa solo, para cualquier input que tenga el atributo
// data-buscador-tabla="<id de la tabla a filtrar>". Las filas con datos
// reales deben tener data-fila-dato, y opcionalmente puede existir una
// fila con data-fila-sin-coincidencias que se muestra cuando el filtro no
// encuentra nada (para no confundirla con la fila "no hay registros" que
// ya pone Django cuando la tabla está vacía de entrada).
document.addEventListener('DOMContentLoaded', function () {
    document.querySelectorAll('[data-buscador-tabla]').forEach(function (input) {
        var tabla = document.getElementById(input.getAttribute('data-buscador-tabla'));
        if (!tabla) {
            return;
        }

        var filas = Array.prototype.slice.call(tabla.querySelectorAll('tbody tr[data-fila-dato]'));
        var filaSinCoincidencias = tabla.querySelector('tbody tr[data-fila-sin-coincidencias]');

        input.addEventListener('input', function () {
            var termino = input.value.trim().toUpperCase();
            var visibles = 0;

            filas.forEach(function (fila) {
                var id = (fila.cells[0] ? fila.cells[0].textContent : '').toUpperCase();
                var nombre = (fila.cells[1] ? fila.cells[1].textContent : '').toUpperCase();
                var coincide = termino === '' || id.indexOf(termino) !== -1 || nombre.indexOf(termino) !== -1;
                fila.hidden = !coincide;
                if (coincide) {
                    visibles++;
                }
            });

            if (filaSinCoincidencias) {
                filaSinCoincidencias.hidden = !(filas.length > 0 && visibles === 0);
            }
        });
    });
});
