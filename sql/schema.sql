-- =========================================================
-- Esquema: carna_scoring (PostgreSQL — Neon/Supabase)
-- Estructura de Datos del TFG. La app crea estas mismas tablas vía SQLAlchemy (src/db.py)
-- si no existen, por lo que ejecutar este archivo a mano es opcional.
-- =========================================================
CREATE TABLE IF NOT EXISTS socio (
    id_socio    SERIAL PRIMARY KEY,
    nombre      VARCHAR(100) NOT NULL,
    rol         VARCHAR(50)  NOT NULL  -- 'Socio', 'Paralegal', 'Administrativo'
);

CREATE TABLE IF NOT EXISTS consulta (
    id_consulta             VARCHAR(20) PRIMARY KEY,   -- formato C-AAAA-NNNN, generado en la app
    fecha_consulta          DATE NOT NULL DEFAULT CURRENT_DATE,
    canal_ingreso           VARCHAR(30) NOT NULL
        CHECK (canal_ingreso IN ('Formulario web','Teléfono','Referido')),
    area_practica           VARCHAR(30) NOT NULL
        CHECK (area_practica IN ('Civil','Laboral','Consumidor','Otro')),
    tipo_reclamo            VARCHAR(80) NOT NULL,
    jurisdiccion            VARCHAR(40)
        CHECK (jurisdiccion IN ('CABA','Provincia de Buenos Aires','Otra')),
    monto_estimado          NUMERIC(14,2),
    estado_prescripcion     VARCHAR(40)
        CHECK (estado_prescripcion IN ('Vigente','Por vencer (menos de 6 meses)','Vencido','No aplica')),
    documentacion_aportada  VARCHAR(20)
        CHECK (documentacion_aportada IN ('Completa','Parcial','Ninguna')),
    observaciones           TEXT,
    resultado_admision      VARCHAR(10)
        CHECK (resultado_admision IN ('Aceptada','Rechazada')),
    motivo_rechazo          VARCHAR(60)
        CHECK (motivo_rechazo IN (
            'Documentación insuficiente','Falta de viabilidad probatoria','Plazo vencido',
            'Jurisdicción fuera de cobertura','Fuera del área de práctica',
            'Conflicto de intereses','Derivado a otra especialidad','Monto no justifica litigio'
        )),
    resultado_final_caso    VARCHAR(20),   -- NUNCA se usa como predictor (fuga de información)
    fecha_carga             TIMESTAMP NOT NULL DEFAULT now(),  -- HU-002 AC3
    fecha_decision          TIMESTAMP
);

CREATE TABLE IF NOT EXISTS evaluacion (
    id_evaluacion        SERIAL PRIMARY KEY,
    id_consulta          VARCHAR(20) NOT NULL REFERENCES consulta(id_consulta),
    id_socio             INTEGER NOT NULL REFERENCES socio(id_socio),
    resultado_evaluacion VARCHAR(10) CHECK (resultado_evaluacion IN ('Aceptada','Rechazada')),
    fecha_evaluacion     TIMESTAMP NOT NULL DEFAULT now(),
    UNIQUE (id_consulta, id_socio)
);

CREATE TABLE IF NOT EXISTS prediccion (
    id_prediccion     SERIAL PRIMARY KEY,
    id_consulta       VARCHAR(20) NOT NULL REFERENCES consulta(id_consulta),
    puntaje_admision  NUMERIC(5,2) NOT NULL CHECK (puntaje_admision BETWEEN 0 AND 100),
    variables_shap    JSONB NOT NULL,
    fecha_prediccion  TIMESTAMP NOT NULL DEFAULT now(),
    version_modelo    VARCHAR(40) NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_prediccion_consulta ON prediccion(id_consulta);
CREATE INDEX IF NOT EXISTS idx_consulta_pendientes ON consulta(resultado_admision) WHERE resultado_admision IS NULL;
