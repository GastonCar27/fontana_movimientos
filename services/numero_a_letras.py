"""
Conversión de números a letras, en formato moneda argentina.

Portado tal cual desde el sistema de escritorio "Fontana 1.0"
(Mixin/Numero_a_letras.py), que es el que arma el texto "Recibí conforme en
Pesos: ..." de las liquidaciones impresas. Se mantiene la lógica original
sin modificaciones (solo se quitó el bloque de demostración __main__) para
que el texto generado en la liquidación en PDF de este sistema sea idéntico
al que ya conocen los usuarios del sistema de escritorio.
"""

MONEDA_SINGULAR = ''
MONEDA_PLURAL = ''

CENTIMOS_SINGULAR = 'CENTAVO'
CENTIMOS_PLURAL = 'CENTAVOS'

MAX_NUMERO = 999999999999

UNIDADES = (
    'CERO',
    'UNO',
    'DOS',
    'TRES',
    'CUATRO',
    'CINCO',
    'SEIS',
    'SIETE',
    'OCHO',
    'NUEVE'
)

DECENAS = (
    'DIEZ',
    'ONCE',
    'DOCE',
    'TRECE',
    'CATORCE',
    'QUINCE',
    'DIECISEIS',
    'DIECISIETE',
    'DIECIOCHO',
    'DIECINUEVE'
)

DIEZ_DIEZ = (
    'CERO',
    'DIEZ',
    'VEINTE',
    'TREINTA',
    'CUARENTA',
    'CINCUENTA',
    'SESENTA',
    'SETENTA',
    'OCHENTA',
    'NOVENTA'
)

CIENTOS = (
    '_',
    'CIENTO',
    'DOSCIENTOS',
    'TRESCIENTOS',
    'CUATROSCIENTOS',
    'QUINIENTOS',
    'SEISCIENTOS',
    'SETECIENTOS',
    'OCHOCIENTOS',
    'NOVECIENTOS'
)


def numero_a_letras(numero):
    numero_entero = int(numero)
    if numero_entero > MAX_NUMERO:
        raise OverflowError('Número demasiado alto')
    if numero_entero < 0:
        negativo_letras = numero_a_letras(abs(numero))
        return f"MENOS {negativo_letras}"
    letras_decimal = ''
    parte_decimal = int(round((abs(numero) - abs(numero_entero)) * 100))
    if parte_decimal > 9:
        letras_decimal = f"PUNTO {numero_a_letras(parte_decimal)}"
    elif parte_decimal > 0:
        letras_decimal = f"PUNTO CERO {numero_a_letras(parte_decimal)}"
    if numero_entero <= 99:
        resultado = leer_decenas(numero_entero)
    elif numero_entero <= 999:
        resultado = leer_centenas(numero_entero)
    elif numero_entero <= 999999:
        resultado = leer_miles(numero_entero)
    elif numero_entero <= 999999999:
        resultado = leer_millones(numero_entero)
    else:
        resultado = leer_millardos(numero_entero)
    resultado = resultado.replace('UNO MIL', 'UN MIL')
    resultado = resultado.strip()
    resultado = resultado.replace(' _ ', ' ')
    resultado = resultado.replace('  ', ' ')
    if parte_decimal > 0:
        resultado = f"{resultado} {letras_decimal}"
    ##VEINTIUNO me toma como veinticero
    if "VEINTICERO" in resultado.upper():
        resultado = resultado.replace("VEINTICERO", "VEINTE")

    return resultado


def numero_a_moneda(numero):
    numero_entero = int(numero)
    parte_decimal = int(round((abs(numero) - abs(numero_entero)) * 100))
    centimos = CENTIMOS_SINGULAR if parte_decimal == 1 else CENTIMOS_PLURAL
    moneda = MONEDA_SINGULAR if numero_entero == 1 else MONEDA_PLURAL
    letras = numero_a_letras(numero_entero)
    letras = letras.replace('UNO', 'UN')
    aux_decimal = numero_a_letras(parte_decimal).replace('UNO', 'UN')
    letras_decimal = f"con {aux_decimal} {centimos}"
    letras = f"{letras} {letras_decimal} {moneda}"

    return letras


def numero_a_letras_para_cheque(numero):
    letras = numero_a_moneda(numero)
    indice_parte_centavos_en_letras = letras.find(" con ")
    indice_parte_centavos_en_numero = str(numero).find(".")
    numero_centavos = str(numero)[indice_parte_centavos_en_numero + 1:]
    letras = f'{letras[:indice_parte_centavos_en_letras]} con {numero_centavos}/100 ctvs'
    return letras


def leer_decenas(numero):
    if numero < 10:
        return UNIDADES[numero]
    decena, unidad = divmod(numero, 10)
    if numero <= 19:
        resultado = DECENAS[unidad]
    elif numero <= 29:
        resultado = f"VEINTI{UNIDADES[unidad]}"
    else:
        resultado = DIEZ_DIEZ[decena]
        if unidad > 0:
            resultado = f"{resultado} y {UNIDADES[unidad]}"
    return resultado


def leer_centenas(numero):
    centena, decena = divmod(numero, 100)
    if numero == 0:
        resultado = 'CIEN'
    else:
        resultado = CIENTOS[centena]
        if decena > 0:
            decena_letras = leer_decenas(decena)
            resultado = f"{resultado} {decena_letras}"
    return resultado


def leer_miles(numero):
    millar, centena = divmod(numero, 1000)
    resultado = ''
    if millar == 1:
        resultado = ''
    if (millar >= 2) and (millar <= 9):
        resultado = UNIDADES[millar]
    elif (millar >= 10) and (millar <= 99):
        resultado = leer_decenas(millar)
    elif (millar >= 100) and (millar <= 999):
        resultado = leer_centenas(millar)
    resultado = f"{resultado} MIL"
    if centena > 0:
        centena_letras = leer_centenas(centena)
        resultado = f"{resultado} {centena_letras}"
    return resultado.strip()


def leer_millones(numero):
    millon, millar = divmod(numero, 1000000)
    resultado = ''
    if millon == 1:
        resultado = ' UN MILLON '
    if (millon >= 2) and (millon <= 9):
        resultado = UNIDADES[millon]
    elif (millon >= 10) and (millon <= 99):
        resultado = leer_decenas(millon)
    elif (millon >= 100) and (millon <= 999):
        resultado = leer_centenas(millon)
    if millon > 1:
        resultado = f"{resultado} MILLONES"
    if (millar > 0) and (millar <= 999):
        centena_letras = leer_centenas(millar)
        resultado = f"{resultado} {centena_letras}"
    elif (millar >= 1000) and (millar <= 999999):
        miles_letras = leer_miles(millar)
        resultado = f"{resultado} {miles_letras}"
    return resultado


def leer_millardos(numero):
    millardo, millon = divmod(numero, 1000000)
    miles_letras = leer_miles(millardo)
    millones_letras = leer_millones(millon)
    return f"{miles_letras} MILLONES {millones_letras}"


def numero_a_moneda_sunat(numero):
    numero_entero = int(numero)
    parte_decimal = int(round((abs(numero) - abs(numero_entero)) * 100))
    moneda = MONEDA_SINGULAR if numero_entero == 1 else MONEDA_PLURAL

    letras = numero_a_letras(numero_entero)
    letras = letras.replace('UNO', 'UN')
    letras = f"{letras} Y {parte_decimal}/100 {moneda}"
    return letras
