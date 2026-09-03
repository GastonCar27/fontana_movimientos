let selectEmisor
let emisor_buscador
let emisor_valor
let lista_emisores
let timeout = null;
function inicio(){
    selectEmisor = document.querySelector('[name=elemento_donde_buscar]')
    emisor_buscador = document.getElementById('buscador_emisor')
    emisor_buscador.addEventListener('input', delay_buscar)
        if (selectEmisor){
             listaEmisores = Array.from(selectEmisor.options).map(option => {
                return {
                        value: option.value,
                        text: option.text
                        }
             })
        }
    }

function cambio_en_input_emisor() {
    emisor_valor = emisor_buscador.value
    es_primero = true
    for (const elemento of listaEmisores)
        {
         if (elemento!== undefined){
             let valor = elemento['value']
                if (contiene(emisor_valor,elemento['text'])===false){

                    if (elemento['value']!== ''){
                        selectEmisor.querySelector('option[value="'+ valor +'"]').hidden = true

                    }
                }
                else{
                     selectEmisor.querySelector('option[value="'+ valor +'"]').hidden = false
                        if (es_primero==true){
                            selectEmisor.querySelector('option[value="'+ valor +'"]').selected = true
                            es_primero=false
                        }
                    }

            }
        }
}

function contiene(valor_en_input,valor_en_lista){
    if ((valor_en_lista.toUpperCase()).includes(valor_en_input.toUpperCase())){
        return true
    }
    else
    {
        return false
    }
}

function delay_buscar(){
    clearTimeout(timeout);

    // 4. Iniciar un nuevo temporizador (ej. 1 segundo = 1000ms)
    timeout = setTimeout(function () {
    console.log('El usuario dejó de escribir:');
    cambio_en_input_emisor()
    }, 400);
}

window.addEventListener('load', inicio)
