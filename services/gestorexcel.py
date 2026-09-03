import openpyxl
from openpyxl.styles import NamedStyle, Border, Font, PatternFill, Side

def crear_excel():
    # 1. Crear un libro de trabajo y una hoja
    return openpyxl.Workbook()

def crear_response_excel():
    from django.http import HttpResponse
    response = HttpResponse(
        content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    )

    response['Content-Disposition'] = 'attachment; filename=reporte.xlsx'

    return response

def formatear_celda_fecha(wb,ws,celda):
    #si no existe el formato de fecha lo crea
    date_style = obtener_formato_fecha(wb)
    for cell in ws[celda]:
        if cell.row == 1:
            continue  # Skip header
        cell.style = date_style
    return wb     


def obtener_formato_fecha(wb):
    if 'custom_date' not in wb.named_styles:
            date_style = NamedStyle(name="custom_date", number_format="DD/MM/YYYY",font=Font(name="Arial", size=8))
            wb.add_named_style(date_style)
        # Apply it to the column cells en este caso la columna es la C
    else:
   
        # 2. Recuperar el estilo iterando sobre la lista si ya existe
        date_style = next(s for s in wb.named_styles if s == 'custom_date')
    return date_style

      
      
def definir_estilo_general(ws):
    # Definir estilos
    fuente_general = Font(name='Arial', size=8, color='000000')
    relleno_celda = PatternFill(
    start_color='F2F2F2', end_color='F2F2F2', fill_type='solid'
    )
    borde_delgado = Border(
    left=Side(style='thin', color='DDDDDD'),
    right=Side(style='thin', color='DDDDDD'),
    top=Side(style='thin', color='DDDDDD'),
    bottom=Side(style='thin', color='DDDDDD'),
    )

    # Aplicar formato a todas las celdas que contienen datos/rango usado
    for row in ws.iter_rows(
        min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column
        ):
        for cell in row:
            cell.font = fuente_general
            cell.fill = relleno_celda
            cell.border = borde_delgado
    return ws

def formatear_celda_numero(ws,columna):
    for cell in ws[columna]:
        if cell.row > 1:
            # Formato de miles con punto y decimales con coma
            cell.number_format = '#,##0.00' 
    return ws
    
