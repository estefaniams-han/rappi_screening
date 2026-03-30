# Rappi Intelligence — AI Engineer Screening

Asistente conversacional + sistema de insights automáticos para equipos de Operations & Strategy de Rappi.

## Arquitectura

```
rappi_screening/
├── app.py              # UI Streamlit (chatbot + insights)
├── data_loader.py      # Carga y limpieza de datos
├── bot/
│   ├── agent.py        # Agente conversacional (Groq + function calling)
│   ├── tools.py        # Herramientas de análisis sobre pandas (6 tools)
│   └── prompts.py      # System prompt del asistente
├── insights/
│   ├── analyzer.py     # Detección automática de anomalías, tendencias, etc.
│   ├── reporter.py     # Generación de reporte ejecutivo con LLM
│   └── pdf_export.py   # Exportación a PDF (insights y resultados del chat)
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

Incluye reporte narrativo generado por LLM y exportación a Excel y PDF.

## Modelo LLM y costos

Usa `meta-llama/llama-4-scout-17b-16e-instruct` vía [Groq API](https://console.groq.com/) (tier gratuito disponible).
El modelo selecciona y ejecuta herramientas de análisis pandas mediante function calling.

**Costo estimado por uso:**

| Escenario | Costo |
|-----------|-------|
| Sesión de 10 preguntas al chatbot | ~$0.00 (Llama 4 Scout en Groq es gratuito en el free tier) |
| Generación de reporte de insights | ~$0.00 (una llamada de ~1,000 tokens) |

Groq ofrece un free tier generoso (actualmente sin costo para modelos Llama). Si se escala a producción con mayor volumen, el costo sería de ~$0.11 por millón de tokens de entrada y ~$0.34 por millón de tokens de salida según los precios actuales de Groq.
