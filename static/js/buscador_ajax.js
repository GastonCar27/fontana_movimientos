/*
 * Buscador genérico con autocompletado por AJAX: un <input type="text"> +
 * un <input type="hidden"> (el que realmente viaja en el <form>) + un <div>
 * donde se listan los resultados. Al tipear, consulta un endpoint que
 * devuelve JSON {"resultados": [{"id": N, "text": "..."}]} y al elegir un
 * resultado completa el input oculto con el id.
 *
 * Es la misma lógica que ya se usaba (copiada) en comprobante_form.html,
 * comprobante_renglon_form.html y liquidaciones/form.html, centralizada acá
 * para no reescribirla en cada pantalla nueva. Esos 3 templates definen su
 * propia copia local de "inicializarBuscador" (no hace falta tocarlos: al
 * ser funciones con el mismo nombre, la definición propia de cada template
 * pisa a esta sin romper nada).
 *
 * 'urlBusqueda' admite además una FUNCIÓN (en vez de un string fijo) que
 * devuelve la URL en el momento de cada búsqueda -- lo usa, por ejemplo, el
 * buscador de acoplado del alta de Remito, que arma la URL con el vehículo
 * elegido en ESE momento (ver remito_form.html).
 *
 * Si se edita el texto de un campo que ya tenía una selección válida pero
 * se sale del campo (blur) SIN volver a elegir una opción de la lista, se
 * restaura la última selección válida en vez de dejar "colgado" un texto
 * que en realidad no corresponde a nada elegido (ver 'blur', más abajo) --
 * si no, se puede perder en silencio un transportista/chofer/etc. ya
 * cargado con sólo tocar el texto sin querer. Para sacar la selección a
 * propósito hay que borrar el campo por completo.
 */

function _inicializarBuscadorEnElementos(input, hidden, resultados, urlBusqueda, onSeleccionar, minCaracteres) {
    if (!input || !hidden || !resultados || !urlBusqueda) {
        return;
    }
    var minimo = minCaracteres === undefined ? 2 : minCaracteres;
    var timeoutId = null;
    // Última selección confirmada (id + texto), para poder restaurarla en
    // el 'blur' de acá abajo. Si el campo ya venía con un valor cargado
    // (ej. al editar un remito existente), arranca con ese.
    var confirmado = hidden.value ? { id: hidden.value, text: input.value } : null;

    input.addEventListener('input', function () {
        hidden.value = '';  // si el usuario vuelve a escribir, invalidamos la selección anterior
        var q = input.value.trim();

        clearTimeout(timeoutId);
        if (q.length < minimo) {
            resultados.style.display = 'none';
            resultados.innerHTML = '';
            return;
        }

        timeoutId = setTimeout(function () {
            // Si 'urlBusqueda' ya trae sus propios parámetros (ej.
            // '?rol=5', para filtrar por tipo de entidad) hay que agregar
            // 'q' con '&' y no con otro '?' -- si no, el query string queda
            // roto (todo después del primer '?' se toma como un único
            // parámetro) y el backend no recibe ni 'rol' ni 'q' bien.
            var url = typeof urlBusqueda === 'function' ? urlBusqueda() : urlBusqueda;
            var separador = url.indexOf('?') === -1 ? '?' : '&';
            fetch(url + separador + 'q=' + encodeURIComponent(q))
                .then(function (resp) { return resp.json(); })
                .then(function (data) {
                    resultados.innerHTML = '';
                    var lista = data.resultados || [];
                    if (lista.length === 0) {
                        resultados.style.display = 'none';
                        return;
                    }
                    lista.forEach(function (item) {
                        var div = document.createElement('div');
                        div.textContent = item.text;
                        div.addEventListener('click', function () {
                            input.value = item.text;
                            hidden.value = item.id;
                            confirmado = { id: item.id, text: item.text };
                            resultados.style.display = 'none';
                            if (onSeleccionar) {
                                onSeleccionar(item);
                            }
                        });
                        resultados.appendChild(div);
                    });
                    resultados.style.display = 'block';
                });
        }, 250);
    });

    input.addEventListener('blur', function () {
        if (hidden.value) {
            // Selección válida (se acaba de elegir un resultado): no hay
            // nada que restaurar.
            confirmado = { id: hidden.value, text: input.value };
            return;
        }
        if (input.value.trim() === '') {
            // Campo vaciado del todo: se interpreta como "sacar la
            // selección" a propósito (estos campos son opcionales).
            confirmado = null;
            return;
        }
        // Quedó un texto a medio editar, sin elegir ninguna opción nueva:
        // se descarta y se restaura la última selección válida (si había
        // una) en vez de guardar en silencio "nada" con un texto que
        // todavía parece un dato cargado.
        input.value = confirmado ? confirmado.text : '';
        hidden.value = confirmado ? confirmado.id : '';
    });

    document.addEventListener('click', function (e) {
        if (!resultados.contains(e.target) && e.target !== input) {
            resultados.style.display = 'none';
        }
    });
}

/** Variante por IDs de elemento (un solo buscador en la página). */
function inicializarBuscador(inputId, hiddenId, resultadosId, urlBusqueda, onSeleccionar, minCaracteres) {
    _inicializarBuscadorEnElementos(
        document.getElementById(inputId),
        document.getElementById(hiddenId),
        document.getElementById(resultadosId),
        urlBusqueda,
        onSeleccionar,
        minCaracteres
    );
}

/** Variante por elementos ya resueltos (para filas repetidas de un formset,
 * donde el id cambia por índice pero los elementos ya se ubicaron con
 * querySelector dentro de la fila). */
function inicializarBuscadorEnElementos(input, hidden, resultados, urlBusqueda, onSeleccionar, minCaracteres) {
    _inicializarBuscadorEnElementos(input, hidden, resultados, urlBusqueda, onSeleccionar, minCaracteres);
}
