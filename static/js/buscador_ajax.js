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
 */

function _inicializarBuscadorEnElementos(input, hidden, resultados, urlBusqueda, onSeleccionar, minCaracteres) {
    if (!input || !hidden || !resultados || !urlBusqueda) {
        return;
    }
    var minimo = minCaracteres === undefined ? 2 : minCaracteres;
    var timeoutId = null;

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
            fetch(urlBusqueda + '?q=' + encodeURIComponent(q))
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
