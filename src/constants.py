"""Dominios cerrados y constantes compartidas entre entrenamiento e inferencia.

Los nombres de columnas (canal_ingreso, area_practica, ...) y los valores de dominio se mantienen
en español porque son el modelo de datos documentado en el TFG.
"""

DOMAINS = {
    "canal_ingreso": ["Formulario web", "Teléfono", "Referido"],
    "area_practica": ["Civil", "Laboral", "Consumidor", "Otro"],
    "jurisdiccion": ["CABA", "Provincia de Buenos Aires", "Otra"],
    "estado_prescripcion": ["Vigente", "Por vencer (menos de 6 meses)", "Vencido", "No aplica"],
    "documentacion_aportada": ["Ninguna", "Parcial", "Completa"],  # orden = orden ordinal
    "tipo_reclamo": [
        "Cobro de deuda", "Incumplimiento contractual", "Responsabilidad profesional",
        "Daños por accidente de tránsito", "Daños por filtraciones", "Daños por producto defectuoso",
        "Reclamo de daños y perjuicios", "Débitos no reconocidos", "Reintegro por cobros bancarios indebidos",
        "Servicio técnico contratado e incumplido", "Servicio no prestado", "Incumplimiento de oferta",
        "Reintegro contractual de prestación", "Despido sin causa", "Indemnización por despido",
        "Diferencias salariales", "Diferencias salariales por trabajo no registrado", "Horas extras impagas",
        "Prestaciones por accidente de trabajo", "Créditos laborales por acoso",
        "Alquileres impagos (canon individual)", "Sucesión compleja", "Conflicto tributario",
        "Trámite migratorio", "Consulta penal",
    ],
    "motivo_rechazo": [
        "Documentación insuficiente", "Falta de viabilidad probatoria", "Plazo vencido",
        "Jurisdicción fuera de cobertura", "Fuera del área de práctica",
        "Conflicto de intereses", "Derivado a otra especialidad", "Monto no justifica litigio",
    ],
}

ACCEPTED, REJECTED = "Aceptada", "Rechazada"

# Las 7 variables predictoras oficiales (Estructura de Datos, TFG). Ni una más.
PREDICTORS = [
    "canal_ingreso", "area_practica", "tipo_reclamo", "jurisdiccion",
    "monto_estimado", "estado_prescripcion", "documentacion_aportada",
]

# Columnas que NUNCA pueden llegar al dataframe de features (fuga de información / metadato del proceso).
FORBIDDEN_COLUMNS = {"resultado_final_caso", "socio_evaluador", "motivo_rechazo", "resultado_admision"}

# Campos obligatorios del formulario de intake (HU-001).
# estado_prescripcion y documentacion_aportada no tienen nulos en el histórico de entrenamiento: el modelo no
# aprendió qué hacer si faltan (vacío en prescripción se lee como "Vencido" y en documentación como "Completa"),
# por eso son obligatorios. jurisdiccion y monto_estimado siguen recomendados: su ausencia no distorsiona el puntaje.
REQUIRED_FIELDS = ["fecha_consulta", "canal_ingreso", "area_practica", "tipo_reclamo",
                   "estado_prescripcion", "documentacion_aportada"]

# Predictores sin los cuales el modelo no debe puntuar una consulta (control en src/prediction.py).
REQUIRED_PREDICTORS = [f for f in REQUIRED_FIELDS if f in PREDICTORS]

# Mapeo columna Excel -> columna del modelo de datos (sql/schema.sql)
EXCEL_COLUMNS = {
    "ID de consulta": "id_consulta",
    "Fecha de consulta": "fecha_consulta",
    "Canal de ingreso": "canal_ingreso",
    "Área de práctica": "area_practica",
    "Tipo de reclamo": "tipo_reclamo",
    "Jurisdicción": "jurisdiccion",
    "Monto estimado (ARS)": "monto_estimado",
    "Estado del plazo de prescripción": "estado_prescripcion",
    "Documentación aportada": "documentacion_aportada",
    "Socio evaluador": "socio_evaluador",
    "Resultado de admisión": "resultado_admision",
    "Motivo de rechazo": "motivo_rechazo",
    "Resultado final del caso": "resultado_final_caso",
    "Observaciones": "observaciones",
}

# Etiquetas en lenguaje natural para la explicación SHAP (HU-004 AC2)
NATURAL_LABELS = {
    "canal_ingreso": "Canal por el que ingresó la consulta",
    "area_practica": "Área de práctica",
    "tipo_reclamo": "Tipo de reclamo",
    "jurisdiccion": "Jurisdicción",
    "monto_estimado": "Monto estimado del reclamo",
    "monto_informado": "Si se informó un monto estimado",
    "estado_prescripcion": "Estado del plazo de prescripción",
    "documentacion_aportada": "Nivel de documentación aportada",
}

POC_WARNING = (
    "Puntaje estimado a modo de prueba de concepto sobre datos simulados — "
    "no representa una probabilidad real."
)

# Cada tipo de reclamo pertenece a una única área en el dataset simulado: el formulario filtra los tipos por área.
CLAIM_TYPES_BY_AREA = {
    "Civil": [
        "Cobro de deuda", "Incumplimiento contractual", "Responsabilidad profesional",
        "Daños por accidente de tránsito", "Daños por filtraciones", "Reclamo de daños y perjuicios",
        "Alquileres impagos (canon individual)",
    ],
    "Laboral": [
        "Despido sin causa", "Indemnización por despido", "Diferencias salariales",
        "Diferencias salariales por trabajo no registrado", "Horas extras impagas",
        "Prestaciones por accidente de trabajo", "Créditos laborales por acoso",
    ],
    "Consumidor": [
        "Daños por producto defectuoso", "Débitos no reconocidos", "Reintegro por cobros bancarios indebidos",
        "Servicio técnico contratado e incumplido", "Servicio no prestado", "Incumplimiento de oferta",
        "Reintegro contractual de prestación",
    ],
    "Otro": ["Sucesión compleja", "Conflicto tributario", "Trámite migratorio", "Consulta penal"],
}
assert sorted(sum(CLAIM_TYPES_BY_AREA.values(), [])) == sorted(DOMAINS["tipo_reclamo"])
