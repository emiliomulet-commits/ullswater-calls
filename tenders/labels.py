"""Labels for tenders.ullswaterinvestments.com: countries (ISO 3166 alpha-3, as TED uses them) and CPV divisions, EN/ES."""

COUNTRIES = {
    "EU": ("EU institutions & agencies", "Instituciones y agencias de la UE", "eu"),
    "AUT": ("Austria", "Austria", "at"), "BEL": ("Belgium", "Bélgica", "be"), "BGR": ("Bulgaria", "Bulgaria", "bg"),
    "HRV": ("Croatia", "Croacia", "hr"), "CYP": ("Cyprus", "Chipre", "cy"), "CZE": ("Czechia", "Chequia", "cz"),
    "DNK": ("Denmark", "Dinamarca", "dk"), "EST": ("Estonia", "Estonia", "ee"), "FIN": ("Finland", "Finlandia", "fi"),
    "FRA": ("France", "Francia", "fr"), "DEU": ("Germany", "Alemania", "de"), "GRC": ("Greece", "Grecia", "gr"),
    "HUN": ("Hungary", "Hungría", "hu"), "IRL": ("Ireland", "Irlanda", "ie"), "ITA": ("Italy", "Italia", "it"),
    "LVA": ("Latvia", "Letonia", "lv"), "LTU": ("Lithuania", "Lituania", "lt"), "LUX": ("Luxembourg", "Luxemburgo", "lu"),
    "MLT": ("Malta", "Malta", "mt"), "NLD": ("Netherlands", "Países Bajos", "nl"), "POL": ("Poland", "Polonia", "pl"),
    "PRT": ("Portugal", "Portugal", "pt"), "ROU": ("Romania", "Rumanía", "ro"), "SVK": ("Slovakia", "Eslovaquia", "sk"),
    "SVN": ("Slovenia", "Eslovenia", "si"), "ESP": ("Spain", "España", "es"), "SWE": ("Sweden", "Suecia", "se"),
    "NOR": ("Norway", "Noruega", "no"), "ISL": ("Iceland", "Islandia", "is"), "LIE": ("Liechtenstein", "Liechtenstein", "li"),
    "CHE": ("Switzerland", "Suiza", "ch"), "GBR": ("United Kingdom", "Reino Unido", "uk"), "MKD": ("North Macedonia", "Macedonia del Norte", "mk"),
    "SRB": ("Serbia", "Serbia", "rs"), "MNE": ("Montenegro", "Montenegro", "me"), "ALB": ("Albania", "Albania", "al"),
    "BIH": ("Bosnia and Herzegovina", "Bosnia y Herzegovina", "ba"), "UKR": ("Ukraine", "Ucrania", "ua"), "MDA": ("Moldova", "Moldavia", "md"),
    "GEO": ("Georgia", "Georgia", "ge"), "TUR": ("Türkiye", "Turquía", "tr"), "XKX": ("Kosovo", "Kosovo", "xk"),
}


def country(code, lang="en"):
    c = COUNTRIES.get(code)
    if not c:
        return code
    return c[1] if lang == "es" else c[0]


def country_slug(code):
    c = COUNTRIES.get(code)
    return c[2] if c else code.lower()


CPV = {  # CPV 2008 divisions
    "03": ("Agriculture, farming & fishing products", "Productos agrícolas, ganaderos y pesqueros"),
    "09": ("Petroleum, fuel, electricity & energy", "Petróleo, combustibles, electricidad y energía"),
    "14": ("Mining & minerals", "Minería y minerales"),
    "15": ("Food & beverages", "Alimentos y bebidas"),
    "16": ("Agricultural machinery", "Maquinaria agrícola"),
    "18": ("Clothing & accessories", "Ropa y accesorios"),
    "19": ("Leather, textiles, plastics & rubber", "Cuero, textiles, plásticos y caucho"),
    "22": ("Printed matter", "Impresos"),
    "24": ("Chemical products", "Productos químicos"),
    "30": ("Office & computing equipment", "Equipos de oficina e informáticos"),
    "31": ("Electrical machinery & lighting", "Maquinaria eléctrica e iluminación"),
    "32": ("Radio, TV & telecom equipment", "Equipos de radio, TV y telecomunicaciones"),
    "33": ("Medical equipment & pharmaceuticals", "Equipos médicos y farmacéuticos"),
    "34": ("Transport equipment", "Equipos de transporte"),
    "35": ("Security, defence & police equipment", "Equipos de seguridad, defensa y policía"),
    "37": ("Musical, sport & leisure goods", "Instrumentos musicales, deporte y ocio"),
    "38": ("Laboratory & precision equipment", "Equipos de laboratorio y precisión"),
    "39": ("Furniture & domestic appliances", "Mobiliario y electrodomésticos"),
    "41": ("Water", "Agua"),
    "42": ("Industrial machinery", "Maquinaria industrial"),
    "43": ("Mining & construction machinery", "Maquinaria de minería y construcción"),
    "44": ("Construction materials & structures", "Materiales y estructuras de construcción"),
    "45": ("Construction work", "Obras de construcción"),
    "48": ("Software & information systems", "Software y sistemas de información"),
    "50": ("Repair & maintenance services", "Reparación y mantenimiento"),
    "51": ("Installation services", "Servicios de instalación"),
    "55": ("Hotel, catering & restaurant services", "Hostelería y restauración"),
    "60": ("Transport services", "Servicios de transporte"),
    "63": ("Logistics & travel services", "Logística y agencias de viajes"),
    "64": ("Postal & telecom services", "Servicios postales y de telecomunicaciones"),
    "65": ("Utilities", "Servicios públicos (agua, gas, electricidad)"),
    "66": ("Financial & insurance services", "Servicios financieros y seguros"),
    "70": ("Real estate services", "Servicios inmobiliarios"),
    "71": ("Architecture, engineering & inspection", "Arquitectura, ingeniería e inspección"),
    "72": ("IT services & consulting", "Servicios TI y consultoría informática"),
    "73": ("Research & development services", "Servicios de investigación y desarrollo"),
    "75": ("Public administration & defence services", "Administración pública y defensa"),
    "76": ("Oil & gas industry services", "Servicios para la industria del petróleo y gas"),
    "77": ("Agricultural, forestry & horticultural services", "Servicios agrícolas, forestales y de jardinería"),
    "79": ("Business services: consulting, legal, marketing", "Servicios a empresas: consultoría, jurídicos, marketing"),
    "80": ("Education & training", "Educación y formación"),
    "85": ("Health & social work", "Servicios sanitarios y sociales"),
    "90": ("Sewage, waste, cleaning & environment", "Alcantarillado, residuos, limpieza y medio ambiente"),
    "92": ("Recreational, cultural & sporting services", "Servicios recreativos, culturales y deportivos"),
    "98": ("Other community & personal services", "Otros servicios comunitarios y personales"),
}


def cpv_label(code, lang="en"):
    d = CPV.get(str(code or "")[:2])
    return (d[1] if lang == "es" else d[0]) if d else ""


NATURE = {"services": ("Services", "Servicios"), "supplies": ("Supplies", "Suministros"), "works": ("Works", "Obras")}
