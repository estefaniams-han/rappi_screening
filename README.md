# Rappi Intelligence — AI Engineer Screening

Asistente conversacional + sistema de insights automáticos para equipos de Operations & Strategy de Rappi.

## Arquitectura

```
rappi_screening/
├── app.py              # UI Streamlit (chatbot + insights)
├── data_loader.py      # Carga y limpieza de datos
├── bot/
│   ├── agent.py        # Agente conversacional (Groq + function calling)
│   ├── tools.py        # Herramientas de análisis sobre pandas
│   └── prompts.py      # System prompt del asistente
├── insights/
│   ├── analyzer.py     # Detección automática de anomalías, tendencias, etc.
│   └── reporter.py     # Generación de reporte ejecutivo con LLM
└── data/raw/           # Dataset Excel (no incluido en el repo)
```

## Requisitos

- Python 3.10+
- Cuenta en [Groq](https://console.groq.com/) (gratuita)

## Instalación

```bash
# 1. Clonar y entrar al proyecto
git clone <repo-url>
cd rappi_screening

# 2. Crear entorno virtual
python -m venv venv
source venv/bin/activate       # macOS/Linux
# venv\Scripts\activate        # Windows

# 3. Instalar dependencias
pip install -r requirements.txt

# 4. Configurar API key
echo "GROQ_API_KEY=tu_api_key_aqui" > .env

# 5. Colocar el dataset
# Copiar el archivo Excel en: data/raw/Rappi Operations Analysis Dummy Data.xlsx
```

## Uso

```bash
streamlit run app.py
```

La app estará disponible en `http://localhost:8501`.

## Funcionalidades

### Chatbot (pestaña principal)

El asistente responde preguntas en lenguaje natural sobre métricas operacionales:

| Tipo | Ejemplo |
|------|---------|
| Filtrado | "Top 5 zonas con mayor Lead Penetration" |
| Comparación | "Perfect Orders: Wealthy vs Non Wealthy en México" |
| Tendencia | "Evolución de Gross Profit UE en Chapinero, últimas 8 semanas" |
| Agregación | "Promedio de Lead Penetration por país" |
| Multivariable | "Zonas con alto Lead Penetration pero bajo Perfect Orders" |
| Órdenes | "Zonas con mayor crecimiento en órdenes en Colombia" |

Características:
- Memoria conversacional (historial completo por sesión)
- Fuzzy matching de zonas, ciudades y métricas
- Gráficas automáticas según el tipo de consulta
- Redirección de preguntas fuera de dominio

### Insights Automáticos (segunda pestaña)

Genera un análisis ejecutivo semanal con:

- **Anomalías**: cambios bruscos >10% semana a semana
- **Tendencias preocupantes**: deterioro consistente en 3+ semanas consecutivas
- **Benchmarking**: zonas por debajo de su grupo (z-score > 1.5)
- **Correlaciones**: pares de métricas que se mueven juntas (r > 0.65)
- **Oportunidades**: zonas de alto volumen con métricas rezagadas

Incluye reporte narrativo generado por LLM y exportación a Excel.

## Modelo LLM

Usa `meta-llama/llama-4-scout-17b-16e-instruct` vía Groq API (gratuita).
El modelo selecciona y ejecuta herramientas de análisis pandas mediante function calling.
