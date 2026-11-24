import json
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import psycopg
import streamlit as st

# -----------------------------------------------------------------------------
# 1. CONFIGURACIÓN DE PÁGINA Y ESTILOS HTML/CSS
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Biodiversidad de Invertebrados en México",
    page_icon="🦋",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
        /* Fondo general y espaciado */
        .block-container {
            padding-top: 3.5rem;
            padding-bottom: 2rem;
        }
        /* Encabezados */
        .dash-title {
            font-size: 3.1rem;
            font-weight: 700;
            color: #27C2F5;
            margin-bottom: 0.1rem;
            letter-spacing: -0.02em;
        }
        .dash-subtitle {
            font-size: 0.95rem;
            color: #9CA3AF;
            margin-bottom: 1.5rem;
        }
        /* Tarjetas KPI */
        .kpi-card {
            background: linear-gradient(145deg, #161B22 0%, #1C232E 100%);
            border: 1px solid #2D3748;
            border-radius: 12px;
            padding: 1.2rem 1rem;
            text-align: center;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.25);
            margin-bottom: 1rem;
        }
        .kpi-card.highlight-teal {
            background: linear-gradient(145deg, #112A26 0%, #161B22 100%);
            border-color: #10B98155;
        }
        .kpi-value {
            font-size: 2.2rem;
            font-weight: 800;
            line-height: 1.1;
            margin-bottom: 0.35rem;
        }
        .kpi-label {
            font-size: 0.9rem;
            font-weight: 600;
            color: #E5E7EB;
        }
        .kpi-sub {
            font-size: 0.78rem;
            color: #9CA3AF;
            margin-top: 0.2rem;
        }
        /* Contenedores de gráficas */
        .chart-box {
            background-color: #161B22;
            border: 1px solid #2D3748;
            border-radius: 12px;
            padding: 1rem;
            margin-bottom: 1rem;
        }
        /* Pestañas superiores */
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
            border-bottom: 1px solid #2D3748;
        }
        .stTabs [data-baseweb="tab"] {
            padding-top: 10px;
            padding-bottom: 10px;
            font-weight: 600;
            color: #9CA3AF;
        }
        .stTabs [aria-selected="true"] {
            color: #F9FAFB !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi_card(valor: str, titulo: str, subtitulo: str = "", color: str = "#10B981", destacado: bool = False):
    clase_extra = "highlight-teal" if destacado else ""
    st.markdown(
        f"""
        <div class="kpi-card {clase_extra}">
            <div class="kpi-value" style="color: {color};">{valor}</div>
            <div class="kpi-label">{titulo}</div>
            <div class="kpi-sub">{subtitulo}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


# -----------------------------------------------------------------------------
# 2. CONEXIÓN A NEON Y CARGA DE GEOJSON
# -----------------------------------------------------------------------------
@st.cache_data(ttl=3600, show_spinner=False)
def run_query(query: str, params: tuple = None) -> pd.DataFrame:
    with psycopg.connect(st.secrets["DATABASE_URL"]) as conn:
        with conn.cursor() as cur:
            cur.execute(query, params)
            cols = [desc[0] for desc in cur.description]
            return pd.DataFrame(cur.fetchall(), columns=cols)


@st.cache_data
def load_geojson():
    with open("data/estados_simplificado.geojson", "r", encoding="utf-8") as f:
        return json.load(f)


geojson_estados = load_geojson()

# Catálogos para los filtros del sidebar
df_cat_estados = run_query("SELECT cve_ent, nombre FROM estados ORDER BY nombre;")
df_cat_ordenes = run_query("SELECT DISTINCT orden FROM especies WHERE orden IS NOT NULL ORDER BY orden;")

# -----------------------------------------------------------------------------
# 3. SIDEBAR DE FILTROS GLOBALES
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Filtros")
    rango_anios = st.slider("Año (2016-2026)", 2016, 2026, (2016, 2026))

    opciones_estado = ["Todos"] + df_cat_estados["nombre"].tolist()
    estado_sel = st.selectbox("Estado", opciones_estado)

    opciones_orden = ["Todos"] + df_cat_ordenes["orden"].tolist()
    orden_sel = st.selectbox("Orden taxonómico", opciones_orden)

    solo_anp = st.toggle("Solo en Áreas Naturales Protegidas (ANP)", value=False)

    st.markdown("---")
    st.caption("Datos: GBIF / iNaturalist México, CONABIO, INEGI y Open-Meteo.")

# Construcción segura de cláusula WHERE dinámica
def build_where(extra_conditions=None):
    conds = ["o.anio BETWEEN %s AND %s"]
    params = [rango_anios[0], rango_anios[1]]

    if estado_sel != "Todos":
        cve = df_cat_estados.loc[df_cat_estados["nombre"] == estado_sel, "cve_ent"].values[0]
        conds.append("o.cve_ent = %s")
        params.append(cve)

    if orden_sel != "Todos":
        conds.append("e.orden = %s")
        params.append(orden_sel)

    if solo_anp:
        conds.append("o.en_anp = TRUE")

    if extra_conditions:
        conds.extend(extra_conditions)

    return " WHERE " + " AND ".join(conds), tuple(params)


# Estilo común para gráficas Plotly
PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#E5E7EB"),
    margin=dict(l=10, r=10, t=35, b=10),
)

# -----------------------------------------------------------------------------
# 4. PESTAÑAS PRINCIPALES
# -----------------------------------------------------------------------------
tab1, tab2, tab3, tab4 = st.tabs([
    "Resumen General",
    "Fenología y Clima",
    "Importancia Médica",
    "Especies Invasoras",
])

# =============================================================================
# PESTAÑA 1: RESUMEN GENERAL
# =============================================================================
with tab1:
    st.markdown('<div class="dash-title">Biodiversidad de Invertebrados en México</div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-subtitle">Panorama general de observaciones, riqueza de especies y cobertura en ANP</div>', unsafe_allow_html=True)

    where_sql, params = build_where()

    df_kpi1 = run_query(
        f"""
        SELECT
            COUNT(*) AS total_obs,
            COUNT(DISTINCT o.especie_id) AS especies_unicas,
            SUM(CASE WHEN o.en_anp THEN 1 ELSE 0 END) AS obs_anp,
            COUNT(DISTINCT CASE WHEN e.es_importancia_medica THEN o.especie_id END) AS especies_im
        FROM observaciones o
        JOIN especies e ON o.especie_id = e.especie_id
        {where_sql};
        """,
        params,
    )

    total_obs = int(df_kpi1["total_obs"].iloc[0] or 0)
    esp_unicas = int(df_kpi1["especies_unicas"].iloc[0] or 0)
    obs_anp = int(df_kpi1["obs_anp"].iloc[0] or 0)
    pct_anp = (obs_anp / total_obs * 100) if total_obs > 0 else 0
    esp_im = int(df_kpi1["especies_im"].iloc[0] or 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card(f"{total_obs:,}", "Observaciones", f"{rango_anios[0]}–{rango_anios[1]}", "#10B981")
    with c2:
        kpi_card(f"{esp_unicas:,}", "Especies Únicas", "Taxones registrados", "#38BDF8")
    with c3:
        kpi_card(f"{pct_anp:.1f}%", "En ANP", f"{obs_anp:,} registros protegidos", "#10B981", destacado=True)
    with c4:
        kpi_card(f"{esp_im:,}", "Importancia Médica", "Especies con riesgo sanitario", "#F59E0B")

    col_map, col_bar = st.columns([1.15, 1])

    with col_map:
        df_mapa = run_query(
            f"""
            SELECT o.cve_ent, est.nombre, COUNT(*) AS registros
            FROM observaciones o
            JOIN especies e ON o.especie_id = e.especie_id
            JOIN estados est ON o.cve_ent = est.cve_ent
            {where_sql}
            GROUP BY o.cve_ent, est.nombre;
            """,
            params,
        )
        fig_map = px.choropleth(
            df_mapa,
            geojson=geojson_estados,
            locations="cve_ent",
            featureidkey="properties.cve_ent",
            color="registros",
            hover_name="nombre",
            color_continuous_scale=["#0F292E", "#0D9488", "#34D399", "#A7F3D0"],
            title="Mapa de Densidad por Estado",
        )
        fig_map.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
        fig_map.update_layout(**PLOTLY_LAYOUT, coloraxis_colorbar=dict(title="Registros", thickness=12))
        st.plotly_chart(fig_map, use_container_width=True)

    with col_bar:
        df_anual = run_query(
            f"""
            SELECT o.anio, o.en_anp, COUNT(*) AS registros
            FROM observaciones o
            JOIN especies e ON o.especie_id = e.especie_id
            {where_sql}
            GROUP BY o.anio, o.en_anp
            ORDER BY o.anio;
            """,
            params,
        )
        df_anual["Zona"] = df_anual["en_anp"].map({True: "En ANP", False: "Fuera de ANP"})
        fig_bar = px.bar(
            df_anual,
            x="anio",
            y="registros",
            color="Zona",
            barmode="stack",
            color_discrete_map={"En ANP": "#10B981", "Fuera de ANP": "#0F766E"},
            title="Crecimiento Anual de Observaciones (ANP vs. No ANP)",
            labels={"anio": "Año", "registros": "Registros"},
        )
        fig_bar.update_layout(**PLOTLY_LAYOUT, legend=dict(orientation="h", y=1.08, x=0.6))
        st.plotly_chart(fig_bar, use_container_width=True)


# =============================================================================
# PESTAÑA 2: FENOLOGÍA Y CLIMA
# =============================================================================
with tab2:
    st.markdown('<div class="dash-title">Fenología y Relación Climática</div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-subtitle">Patrones estacionales (Día del Año) cruzados con temperatura y precipitación histórica</div>', unsafe_allow_html=True)

    where_sql, params = build_where()

    df_feno_mes = run_query(
        f"""
        WITH obs_mes AS (
            SELECT o.mes, COUNT(*) AS registros
            FROM observaciones o
            JOIN especies e ON o.especie_id = e.especie_id
            {where_sql}
            GROUP BY o.mes
        ),
        clima_mes AS (
            SELECT mes, AVG(temp_media) AS temp_media, AVG(precipitacion_mm) AS precip_mm
            FROM clima_mensual
            WHERE anio BETWEEN %s AND %s
            GROUP BY mes
        )
        SELECT o.mes, o.registros, ROUND(c.temp_media::numeric, 2) AS temp_media, ROUND(c.precip_mm::numeric, 1) AS precip_mm
        FROM obs_mes o
        LEFT JOIN clima_mes c ON o.mes = c.mes
        ORDER BY o.mes;
        """,
        params + (rango_anios[0], rango_anios[1]),
    )

    df_feno_anio = run_query(
        f"""
        WITH feno AS (
            SELECT
                o.anio,
                PERCENTILE_CONT(0.1) WITHIN GROUP (ORDER BY o.doy) AS doy_p10,
                PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY o.doy) AS doy_pico,
                PERCENTILE_CONT(0.9) WITHIN GROUP (ORDER BY o.doy) AS doy_p90
            FROM observaciones o
            JOIN especies e ON o.especie_id = e.especie_id
            {where_sql}
            GROUP BY o.anio
        ),
        clima AS (
            SELECT anio, AVG(temp_media) AS temp_anual, SUM(precipitacion_mm) / COUNT(DISTINCT cve_ent) AS precip_anual
            FROM clima_mensual
            WHERE anio BETWEEN %s AND %s
            GROUP BY anio
        )
        SELECT f.*, ROUND(c.temp_anual::numeric, 2) AS temp_anual, ROUND(c.precip_anual::numeric, 1) AS precip_anual
        FROM feno f
        LEFT JOIN clima c ON f.anio = c.anio
        ORDER BY f.anio;
        """,
        params + (rango_anios[0], rango_anios[1]),
    )

    doy_med = int(df_feno_anio["doy_pico"].median()) if not df_feno_anio.empty else 0
    temp_prom = float(df_feno_anio["temp_anual"].mean()) if not df_feno_anio.empty else 0.0
    precip_prom = float(df_feno_anio["precip_anual"].mean()) if not df_feno_anio.empty else 0.0

    k1, k2, k3 = st.columns(3)
    with k1:
        kpi_card(f"{doy_med}", "Día Pico (DOY)", "Mediana histórica de actividad", "#10B981", destacado=True)
    with k2:
        kpi_card(f"{temp_prom:.1f} °C", "Temperatura Media", "Promedio del periodo seleccionado", "#F59E0B")
    with k3:
        kpi_card(f"{precip_prom:.0f} mm", "Precipitación Anual", "Promedio acumulado anual", "#38BDF8")

    # Gráfica combinada de doble eje
    meses_lbl = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    df_feno_mes["mes_nombre"] = df_feno_mes["mes"].apply(lambda m: meses_lbl[m - 1])

    fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
    fig_dual.add_trace(
        go.Bar(x=df_feno_mes["mes_nombre"], y=df_feno_mes["registros"], name="Observaciones", marker_color="#10B981", opacity=0.75),
        secondary_y=False,
    )
    fig_dual.add_trace(
        go.Scatter(x=df_feno_mes["mes_nombre"], y=df_feno_mes["temp_media"], name="Temp. Media (°C)", line=dict(color="#F59E0B", width=3)),
        secondary_y=True,
    )
    fig_dual.update_layout(**PLOTLY_LAYOUT, title="Observaciones Mensuales vs. Temperatura Media", legend=dict(orientation="h", y=1.12, x=0.65))
    fig_dual.update_yaxes(title_text="Registros", secondary_y=False, showgrid=False)
    fig_dual.update_yaxes(title_text="Temperatura (°C)", secondary_y=True, showgrid=False)
    st.plotly_chart(fig_dual, use_container_width=True)

    c_izq, c_der = st.columns(2)
    with c_izq:
        fig_rango = go.Figure()
        fig_rango.add_trace(go.Scatter(x=df_feno_anio["anio"], y=df_feno_anio["doy_p90"], line=dict(width=0), showlegend=False))
        fig_rango.add_trace(
            go.Scatter(
                x=df_feno_anio["anio"], y=df_feno_anio["doy_p10"], fill="tonexty",
                fillcolor="rgba(16, 185, 129, 0.2)", line=dict(width=0), name="Ventana activa (P10–P90)"
            )
        )
        fig_rango.add_trace(
            go.Scatter(x=df_feno_anio["anio"], y=df_feno_anio["doy_pico"], mode="lines+markers", line=dict(color="#10B981", width=3), name="Día Pico (Mediana)")
        )
        fig_rango.update_layout(**PLOTLY_LAYOUT, title="Ventana de Actividad (DOY) por Año", xaxis_title="Año", yaxis_title="Día del Año (1-366)")
        st.plotly_chart(fig_rango, use_container_width=True)

    with c_der:
        fig_scat = px.scatter(
            df_feno_anio,
            x="temp_anual",
            y="doy_pico",
            text="anio",
            title="Temperatura Media Anual vs. Día Pico (DOY)",
            labels={"temp_anual": "Temperatura Media (°C)", "doy_pico": "Día Pico (DOY)"},
            color_discrete_sequence=["#38BDF8"],
        )
        fig_scat.update_traces(textposition="top center", marker=dict(size=10))
        fig_scat.update_layout(**PLOTLY_LAYOUT)
        st.plotly_chart(fig_scat, use_container_width=True)


# =============================================================================
# PESTAÑA 3: IMPORTANCIA MÉDICA
# =============================================================================
with tab3:
    st.markdown('<div class="dash-title">Especies de Importancia Médica y Expansión Municipal</div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-subtitle">Distribución de géneros de riesgo sanitario y proporción de avistamientos fuera de ANP</div>', unsafe_allow_html=True)

    where_im, params_im = build_where(["e.es_importancia_medica = TRUE"])

    df_kpi_im = run_query(
        f"""
        SELECT
            COUNT(DISTINCT o.especie_id) AS especies_im,
            COUNT(DISTINCT o.cvegeo) AS municipios_im,
            ROUND(AVG(CASE WHEN NOT o.en_anp THEN 1.0 ELSE 0.0 END) * 100, 1) AS pct_fuera_anp
        FROM observaciones o
        JOIN especies e ON o.especie_id = e.especie_id
        {where_im};
        """,
        params_im,
    )

    m1, m2, m3 = st.columns(3)
    with m1:
        kpi_card(f"{int(df_kpi_im['especies_im'].iloc[0] or 0):,}", "Especies Médicas", "Con registros en el periodo", "#F59E0B")
    with m2:
        kpi_card(f"{float(df_kpi_im['pct_fuera_anp'].iloc[0] or 0):.1f}%", "Fuera de ANP", "Zonas urbanas / periurbanas", "#FB7185")
    with m3:
        kpi_card(f"{int(df_kpi_im['municipios_im'].iloc[0] or 0):,}", "Municipios con Presencia", "Cobertura municipal detectada", "#38BDF8")

    col_heat, col_right = st.columns([1.2, 1])

    with col_heat:
        df_heat = run_query(
            f"""
            SELECT
                ROUND(o.latitud::numeric, 2) AS lat,
                ROUND(o.longitud::numeric, 2) AS lon,
                COUNT(*) AS densidad
            FROM observaciones o
            JOIN especies e ON o.especie_id = e.especie_id
            {where_im}
            GROUP BY 1, 2;
            """,
            params_im,
        )
        fig_heat = px.density_map(
            df_heat,
            lat="lat",
            lon="lon",
            z="densidad",
            radius=12,
            center=dict(lat=23.6, lon=-102.5),
            zoom=4,
            map_style="carto-darkmatter",
            color_continuous_scale="Inferno",
            title="Mapa de Calor: Avistamientos de Importancia Médica",
        )
        fig_heat.update_layout(**PLOTLY_LAYOUT, height=520)
        st.plotly_chart(fig_heat, use_container_width=True)

    with col_right:
        df_top_gen = run_query(
            f"""
            SELECT e.genero, COUNT(*) AS registros
            FROM observaciones o
            JOIN especies e ON o.especie_id = e.especie_id
            {where_im}
            GROUP BY e.genero
            ORDER BY registros DESC
            LIMIT 8;
            """,
            params_im,
        )
        fig_gen = px.bar(
            df_top_gen.sort_values("registros"),
            x="registros",
            y="genero",
            orientation="h",
            color="registros",
            color_continuous_scale=["#FB7185", "#F59E0B"],
            title="Top Géneros de Importancia Médica",
            labels={"registros": "Registros", "genero": ""},
        )
        fig_gen.update_layout(**PLOTLY_LAYOUT, height=250, coloraxis_showscale=False)
        st.plotly_chart(fig_gen, use_container_width=True)

        df_exp_im = run_query(
            f"""
            WITH primer AS (
                SELECT o.cvegeo, MIN(o.anio) AS anio_llegada
                FROM observaciones o
                JOIN especies e ON o.especie_id = e.especie_id
                {where_im}
                GROUP BY o.cvegeo
            )
            SELECT anio_llegada, SUM(COUNT(*)) OVER (ORDER BY anio_llegada) AS municipios_acumulados
            FROM primer
            GROUP BY anio_llegada
            ORDER BY anio_llegada;
            """,
            params_im,
        )
        df_exp_im["anio_llegada"] = df_exp_im["anio_llegada"].astype(int)
        df_exp_im["municipios_acumulados"] = df_exp_im["municipios_acumulados"].astype(int)

        fig_area = px.area(
            df_exp_im,
            x="anio_llegada",
            y="municipios_acumulados",
            orientation="v",
            title="Expansión Territorial: Municipios Acumulados",
            labels={"anio_llegada": "Año", "municipios_acumulados": "Municipios"},
            color_discrete_sequence=["#FB7185"],
        )
        fig_area.update_layout(**PLOTLY_LAYOUT, height=250)
        fig_area.update_xaxes(dtick=1)
        st.plotly_chart(fig_area, use_container_width=True)


# =============================================================================
# PESTAÑA 4: ESPECIES INVASORAS
# =============================================================================
with tab4:
    st.markdown('<div class="dash-title">Monitoreo de Especies Invasoras</div>', unsafe_allow_html=True)
    st.markdown('<div class="dash-subtitle">Avance municipal de especies exóticas invasoras registradas en México</div>', unsafe_allow_html=True)

    where_inv, params_inv = build_where(["e.es_invasora = TRUE"])

    df_inv_top = run_query(
        f"""
        SELECT
            e.especie,
            e.clase,
            COUNT(*) AS avistamientos,
            COUNT(DISTINCT o.cve_ent) AS estados,
            COUNT(DISTINCT o.cvegeo) AS municipios
        FROM observaciones o
        JOIN especies e ON o.especie_id = e.especie_id
        {where_inv}
        GROUP BY e.especie, e.clase
        ORDER BY municipios DESC
        LIMIT 15;
        """,
        params_inv,
    )

    if df_inv_top.empty:
        st.info("No se encontraron registros de especies invasoras con los filtros actuales.")
    else:
        col_t, col_e = st.columns([1.1, 1])
        with col_t:
            st.dataframe(df_inv_top, use_container_width=True, hide_index=True)

        with col_e:
            especie_sel = st.selectbox("Analizar expansión municipal de:", df_inv_top["especie"].tolist())
            df_exp_sp = run_query(
                """
                WITH primer AS (
                    SELECT o.cvegeo, MIN(o.anio) AS anio_llegada
                    FROM observaciones o
                    JOIN especies e ON o.especie_id = e.especie_id
                    WHERE e.especie = %s
                    GROUP BY o.cvegeo
                )
                SELECT
                    anio_llegada,
                    COUNT(*) AS nuevos,
                    SUM(COUNT(*)) OVER (ORDER BY anio_llegada) AS acumulados
                FROM primer
                GROUP BY anio_llegada
                ORDER BY anio_llegada;
                """,
                (especie_sel,),
            )
            df_exp_sp["anio_llegada"] = df_exp_sp["anio_llegada"].astype(int)
            df_exp_sp["acumulados"] = df_exp_sp["acumulados"].astype(int)

            fig_inv = px.area(
                df_exp_sp,
                x="anio_llegada",
                y="acumulados",
                orientation="v",
                title=f"Municipios Acumulados: {especie_sel}",
                labels={"anio_llegada": "Año", "acumulados": "Municipios"},
                color_discrete_sequence=["#F59E0B"],
            )
            fig_inv.update_layout(**PLOTLY_LAYOUT)
            fig_inv.update_xaxes(dtick=1)
            st.plotly_chart(fig_inv, use_container_width=True)