
function buscar_en_input(e,i,sel,to){
    let input = i
    let select = sel
    let timeout = to
    function delay_buscar(){
    clearTimeout(timeout);

    // 4. Iniciar un nuevo temporizador (ej. 1 segundo = 1000ms)
    timeout = setTimeout(function () {
    cambio_en_input()
    }, 400);
}

    function cambio_en_input() {
        let valor = input.value
        es_primero = true
        for (const elemento of lista)
            {
            if (elemento!== undefined){
                let valor_en_lista = elemento['value']
                    if (contiene(valor,elemento['text'])===false){
                        if (elemento['value']!== ''){
                            select.querySelector('option[value="'+ valor_en_lista +'"]').hidden = true
                        }
                    }
                    else{
                        select.querySelector('option[value="'+ valor_en_lista +'"]').hidden = false
                            if (es_primero==true){
                                select.querySelector('option[value="'+ valor_en_lista +'"]').selected = true
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

    if (select){
            lista = Array.from(select.options).map(option => {
            return {
                    value: option.value,
                    text: option.text
                    }
            })
    delay_buscar()
    }
}
