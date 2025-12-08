import re

import PyPDF2
import re
import pandas as pd

import PyPDF2
import pandas as pd
import datetime


 # PROCESAR FACTURAS

MESES = {
    "enero": 1, "febrero": 2, "marzo": 3,
    "abril": 4, "mayo": 5, "junio": 6,
    "julio": 7, "agosto": 8, "septiembre": 9,
    "octubre": 10, "noviembre": 11, "diciembre": 12
}

def leer_pdf(pdf_path):
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        lines = []
        for page in reader.pages:
            text = page.extract_text()
            if text:
                lines.extend(text.split("\n"))
        return [l.strip() for l in lines if l.strip()]

def extraer_fecha_emision(lines):
    for line in lines:
        if "fecha emision" in line.lower():
            # Ejemplo capturado:
            # Fecha Emision: 20 de Febrero del 2025
            m = re.search(r"(\d{1,2})\s+de\s+([A-Za-z]+)\s+del\s+(\d{4})", line, re.IGNORECASE)
            if m:
                dia = int(m.group(1))
                mes_txt = m.group(2).lower()
                año = int(m.group(3))

                mes = MESES.get(mes_txt, None)
                if mes:
                    return datetime.date(año, mes, dia).isoformat()

    return None

def a_float(x):
    x = x.strip()
    x = x.replace(".", "")
    x = x.replace(",", ".")
    return float(x)

def extraer_num_factura(lines):
    for l in lines:
        m = re.search(r"Nº\s*(\d+)", l)
        if m:
            return m.group(1)
    return None


def parse_embonor(lines):
    items = []
    num_re = re.compile(r"^[\d\.,]+$")
    i = 0

    while i < len(lines)-1:
        lineA = lines[i]
        partsA = lineA.split()

        if len(partsA) > 1 and re.match(r"^INT1-[A-Za-z0-9\-]+$", partsA[0]):
            codigo = partsA[0]
            descripcion = " ".join(partsA[1:])

            lineB = lines[i+1]
            if "|" not in lineB:
                i += 1
                continue

            bloques = lineB.split()[0]
            last_block = bloques.split("|")[-1]
            cantidad = int(last_block[-1])

            nums = [t for t in lineB.split() if num_re.match(t)]
            valor_final = a_float(nums[-1])

            items.append({
                "codigo_proveedor": codigo,
                "descripcion_item": descripcion,
                "cantidad": cantidad,
                "valor_final": valor_final
            })

            i += 2
            continue

        i += 1

    return items


def parse_libesa(lines):
    items = []
    num_re = re.compile(r"^[\d\.,]+$")
    
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        tokens = line.split()

        # Caso 1: línea completa con todo
        if len(tokens) > 3 and re.match(r"^INT1-[A-Za-z0-9\-]+$", tokens[0]):

            # buscar números de la línea → valor final es último número
            nums = [t for t in tokens if num_re.match(t)]
            if len(nums) >= 2:
                valor_final = a_float(nums[-1])
                
                # detectar cantidad pegada tipo 25Uni.
                cantidad = None
                cantidad_idx = None
                for idx, tok in enumerate(tokens):
                    m = re.match(r"^(\d+)\s*[A-Za-z]+\.?$", tok)
                    if m:
                        cantidad = int(m.group(1))
                        cantidad_idx = idx
                        break

                # si se encontró cantidad: línea completa
                if cantidad is not None:
                    descripcion = " ".join(tokens[1:cantidad_idx])
                    codigo = tokens[0]
                    items.append({
                        "codigo_proveedor": codigo,
                        "descripcion_item": descripcion,
                        "cantidad": cantidad,
                        "valor_final": valor_final
                    })
                    i += 1
                    continue

            # Caso 2: línea rota: INT1... sin cantidad ni valor

            # la siguiente línea tiene UNI12Uni. precio valor
            if i + 1 < len(lines):
                next_line = lines[i+1].strip()
                next_tokens = next_line.split()

                # detectar cantidad pegada en la segunda línea
                cantidad = None
                for tok in next_tokens:
                    m = re.match(r"^(\d+)\s*[A-Za-z]+\.?$", tok)
                    if m:
                        cantidad = int(m.group(1))
                        break

                # buscar valor final en segunda línea
                nums2 = [t for t in next_tokens if num_re.match(t)]
                if cantidad is not None and len(nums2) >= 1:
                    valor_final = a_float(nums2[-1])
                    codigo = tokens[0]
                    descripcion = " ".join(tokens[1:])

                    items.append({
                        "codigo_proveedor": codigo,
                        "descripcion_item": descripcion,
                        "cantidad": cantidad,
                        "valor_final": valor_final
                    })

                    i += 2
                    continue

        i += 1

    return items


def procesar_factura(pdf_path):
    lines = leer_pdf(pdf_path)

    proveedor = lines[0]     # línea de arriba SIEMPRE es nombre proveedor
    num_factura = extraer_num_factura(lines)
    fecha_emision = extraer_fecha_emision(lines)
    proveedor_lower = proveedor.lower()

    # Selección por proveedor
    if "embonor" in proveedor_lower:
        items = parse_embonor(lines)
    elif "libesa" in proveedor_lower:
        items = parse_libesa(lines)
    else:
        items = parse_generico(lines)

    df = pd.DataFrame(items)
    df.rename(columns={"valor_final": "valor_tot"}, inplace=True)
    df["proveedor"] = proveedor
    df["num_factura"] = num_factura
    df["fecha_emision"] = fecha_emision

    return df


# NORMALIZAR TABLA

def parse_generico(lines):
    items = []
    empezar = False
    
    num_re = re.compile(r"^[\d\.,]+$")
    unidades = {"un", "und", "uni", "cj", "cj.", "uni.", "und.", "unid", "unid."}

    for line in lines:

        # Activar parser solo después de "Valor"
        if "valor" in line.lower():
            empezar = True
            continue

        if not empezar:
            continue

        tokens = line.split()
        if len(tokens) < 3:
            continue

        # valor_final = último número
        nums = [t for t in tokens if num_re.match(t)]
        if len(nums) == 0:
            continue

        valor_final = a_float(nums[-1])

        # detectar código
        primer = tokens[0]

        if re.match(r"^INT1-[A-Za-z0-9\-]+$", primer):
            codigo = primer
            desc_start = 1
        elif primer == "-":
            codigo = None
            desc_start = 1
        else:
            codigo = None
            desc_start = 0

        # detectar cantidad basada en unidad
        # patrones:
        # "5 UN", "12 UND", "1 CJ", "25 Uni.", etc.
        cantidad = None
        cantidad_idx = None

        for i in range(desc_start, len(tokens) - 1):
            tok = tokens[i]
            next_tok = tokens[i+1].lower().strip(".,")

            if tok.isdigit() and next_tok in unidades:
                cantidad = int(tok)
                cantidad_idx = i
                break
            
            # Caso 1b: "12un", "25und", "8cj"
            m = re.match(r"^(\d+)([A-Za-z]+)$", tok)
            if m:
                num = m.group(1)
                unit = m.group(2).lower().strip(".")
                if unit in unidades:
                    cantidad = int(num)
                    cantidad_idx = i
                    break

        # fallback: en caso de no haber unidad pero número seguido de número
        if cantidad is None:
            for i in range(desc_start, len(tokens)-1):
                if tokens[i].isdigit() and num_re.match(tokens[i+1]):
                    cantidad = int(tokens[i])
                    cantidad_idx = i
                    break

        if cantidad is None:
            continue

        # descripción = todo entre código y cantidad
        descripcion = " ".join(tokens[desc_start:cantidad_idx])

        items.append({
            "codigo_proveedor": codigo,
            "descripcion_item": descripcion,
            "cantidad": cantidad,
            "valor_final": valor_final
        })

    return items

def normalizar_tabla(df):
    df = df.copy()

    # nueva columna cantidad_final inicial
    df["cantidad_final"] = df["cantidad"].astype(int)

    # recorrer por fila
    for idx, row in df.iterrows():
        desc = row["descripcion_item"]
        prov = row["proveedor"].lower()

        multiplicador = None
        nuevo_desc = desc

        #       CASO CCU
        if "ccu" in prov:
            # X30 o X 30
            m = re.search(r"[Xx]\s*(\d+)", desc)
            if m:
                multiplicador = int(m.group(1))
                nuevo_desc = re.sub(r"[Xx]\s*\d+", "", desc)

            # 30PC
            if multiplicador is None:
                m = re.search(r"(\d+)PC", desc, flags=re.IGNORECASE)
                if m:
                    multiplicador = int(m.group(1))
                    nuevo_desc = re.sub(r"\d+PC", "", desc, flags=re.IGNORECASE)

        #       CASO FRUNA
        if "fruna" in prov:
            # 24UN, 24U
            base_desc=desc
            m = re.search(r"(\d+)\s*[Uu][Nn]?", desc)
            if m:
                multiplicador = int(m.group(1))
                base_desc = re.sub(r"\d+\s*[Uu][Nn]?", "", desc)

            # X40U
            m = re.search(r"[Xx]\s*(\d+)\s*[Uu]", desc)
            if m:
                multiplicador = int(m.group(1))
                base_desc = re.sub(r"[Xx]\s*\d+\s*[Uu]", "", desc)

            desc_norm = base_desc

            # 1) Expandir abreviaciones con espacio
            reemplazos = {
                "GALL.": "GALLETA ",
                "FAM.": "FAMILIAR ",
                "FRU.": "FRUNA ",
                "COST.": "COSTA ",
                "HEL.": "HELADO ",
                "CHOC.": "CHOCOLATE ",
            }
            for abrev, completo in reemplazos.items():
                desc_norm = desc_norm.replace(abrev, completo)

            # 2) Borrar palabras no deseadas
            desc_norm = re.sub(r"\bDISPL\.?\b", "", desc_norm, flags=re.IGNORECASE)
            desc_norm = re.sub(r"\bIMPUL\.?\b", "", desc_norm, flags=re.IGNORECASE)

            # 3) Quitar todos los signos %
            desc_norm = desc_norm.replace("%", "")

            # 4) Limpieza final de espacios
            desc_norm = " ".join(desc_norm.split())

            # guardar descripción limpia
            df.at[idx, "descripcion_item"] = desc_norm

            nuevo_desc=desc_norm

        #       CASO COCA COLA
        if "coca" in prov or "embonor" in prov or "andina" in prov:
            m = re.search(r"[Xx]\s*(\d+)", desc)
            if m:
                multiplicador = int(m.group(1))
                nuevo_desc = re.sub(r"[Xx]\s*\d+", "", desc)

        # SI SE ENCONTRÓ MULTIPLICADOR → actualizar cantidad
        if multiplicador:
            df.at[idx, "cantidad_final"] = row["cantidad"] * multiplicador
        else:
            df.at[idx, "cantidad_final"] = row["cantidad"]

        # limpiar descripción
        df.at[idx, "descripcion_item"] = " ".join(nuevo_desc.split())

    # Calcular valor_unitario
    df["valor_unitario"] = round(df["valor_tot"]*1.19 / df["cantidad_final"])

    return df
