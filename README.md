# Fenología y Expansión de Invertebrados en México
https://observatorio-biodiversidad-mx.streamlit.app/

Dashboard interactivo desarrollado en **Streamlit** para el análisis espacio-temporal de más de 1 millón de observaciones con grado de investigación (*Research Grade*) de **insectos, arácnidos y moluscos** en México durante la última década (2016–2026), utilizando datos abiertos de **GBIF / iNaturalist**.

## Módulos principales

1. **Fenología y cambios en la estacionalidad:** 
   Analiza el desplazamiento de los picos de aparición anuales (Día del Año / DOY) y la amplitud de las temporadas por orden taxonómico, corrigiendo el sesgo de crecimiento de usuarios en ciencia ciudadana mediante tasas relativas.
2. **Expansión de especies invasoras e importancia médica:** 
   Rastrea la dispersión geográfica año con año de especies clave (como *Loxosceles*, *Latrodectus* o *Lissachatina fulica*), midiendo la colonización de nuevas zonas y patrones de encuentro en áreas urbanas.

## Stack tecnológico
* **Frontend / App:** Streamlit
* **Procesamiento de datos:** Python, Pandas, Parquet
* **Visualización y análisis espacial:** Plotly / PyDeck / GeoPandas
* **Fuente de datos:** GBIF (iNaturalist Research-grade Observations)
