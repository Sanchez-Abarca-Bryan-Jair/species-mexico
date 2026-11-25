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
        .block-container {
            padding-top: 3.5rem;
            padding-bottom: 2rem;
        }
        .dash-title {
            font-size: 2.4rem;
            font-weight: 800;
            color: #234235;
            margin-bottom: 0.15rem;
            letter-spacing: -0.02em;
        }
        .dash-subtitle {
            font-size: 0.95rem;
            color: #5C6F65;
            margin-bottom: 1.5rem;
        }
        .kpi-card {
            border-radius: 14px;
            padding: 1.25rem 1rem;
            text-align: center;
            border: 1px solid rgba(35, 66, 53, 0.12);
            box-shadow: 0 3px 10px rgba(35, 66, 53, 0.05);
            margin-bottom: 1rem;
            transition: transform 0.15s ease;
        }
        .kpi-card:hover {
            transform: translateY(-2px);
        }
        .kpi-value {
            font-size: 2.05rem;
            font-weight: 800;
            line-height: 1.15;
            margin-bottom: 0.35rem;
        }
        .kpi-label {
            font-size: 0.92rem;
            font-weight: 700;
            color: #1F2E27;
        }
        .kpi-sub {
            font-size: 0.78rem;
            color: #55665D;
            margin-top: 0.25rem;
        }
        .stTabs [data-baseweb="tab-list"] {
            gap: 24px;
            border-bottom: 1px solid #E2DDD2;
        }
        .stTabs [data-baseweb="tab"] {
            padding-top: 10px;
            padding-bottom: 10px;
            font-weight: 600;
            color: #67786F;
        }
        .stTabs [aria-selected="true"] {
            color: #234235 !important;
        }
    </style>
    """,
    unsafe_allow_html=True,
)


def kpi_card(
    valor: str,
    titulo: str,
    subtitulo: str = "",
    color_texto: str = "#235A45",
    fondo: str = "#E4F1EA",
    borde: str = "#B2D4C2",
):
    st.markdown(
        f"""
        <div class="kpi-card" style="background: {fondo}; border-color: {borde};">
            <div class="kpi-value" style="color: {color_texto};">{valor}</div>
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


@st.cache_data
def load_geojson_mun():
    with open("data/municipios_simplificado.geojson", "r", encoding="utf-8") as f:
        return json.load(f)


geojson_estados = load_geojson()
geojson_municipios = load_geojson_mun()

# Catálogos para los filtros del sidebar
df_cat_estados = run_query("SELECT cve_ent, nombre FROM estados ORDER BY nombre;")
df_cat_clases = run_query("SELECT DISTINCT clase FROM especies WHERE clase IS NOT NULL ORDER BY clase;")
df_cat_ordenes = run_query("SELECT DISTINCT orden FROM especies WHERE orden IS NOT NULL ORDER BY orden;")

# -----------------------------------------------------------------------------
# 3. SIDEBAR DE FILTROS GLOBALES
# -----------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## Filtros")
    rango_anios = st.slider("Año (2016-2026)", 2016, 2026, (2016, 2026))

    opciones_estado = ["Todos"] + df_cat_estados["nombre"].tolist()
    estado_sel = st.selectbox("Estado", opciones_estado)

    opciones_clase = ["Todas"] + df_cat_clases["clase"].tolist()
    clase_sel = st.selectbox("Clase (Insectos, Arácnidos, etc.)", opciones_clase)

    if clase_sel != "Todas":
        df_ord_filt = run_query(
            "SELECT DISTINCT orden FROM especies WHERE clase = %s AND orden IS NOT NULL ORDER BY orden;",
            (clase_sel,),
        )
        opciones_orden = ["Todos"] + df_ord_filt["orden"].tolist()
    else:
        opciones_orden = ["Todos"] + df_cat_ordenes["orden"].tolist()

    orden_sel = st.selectbox("Orden taxonómico", opciones_orden)
    solo_anp = st.toggle("Solo en Áreas Naturales Protegidas (ANP)", value=False)

    st.markdown("---")
    st.caption("Datos: GBIF / iNaturalist México, CONABIO, INEGI y Open-Meteo.")
    st.caption("Nota: El corte de datos no incluye registros para el año 2025.")


def build_where(extra_conditions=None):
    conds = ["o.anio BETWEEN %s AND %s"]
    params = [rango_anios[0], rango_anios[1]]

    if estado_sel != "Todos":
        cve = df_cat_estados.loc[df_cat_estados["nombre"] == estado_sel, "cve_ent"].values[0]
        conds.append("o.cve_ent = %s")
        params.append(cve)

    if clase_sel != "Todas":
        conds.append("e.clase = %s")
        params.append(clase_sel)

    if orden_sel != "Todos":
        conds.append("e.orden = %s")
        params.append(orden_sel)

    if solo_anp:
        conds.append("o.en_anp = TRUE")

    if extra_conditions:
        conds.extend(extra_conditions)

    return " WHERE " + " AND ".join(conds), tuple(params)


PLOTLY_LAYOUT = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(color="#24342C"),
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

    totales_anio = df_anual.groupby("anio")["registros"].sum().sort_index()
    if len(totales_anio) >= 2 and totales_anio.iloc[0] > 0:
        pct_crec = ((totales_anio.iloc[-1] - totales_anio.iloc[0]) / totales_anio.iloc[0]) * 100
        signo = "+" if pct_crec >= 0 else ""
        texto_crec = f"{signo}{pct_crec:,.1f}% ({totales_anio.index[0]} → {totales_anio.index[-1]})"
    else:
        texto_crec = f"{rango_anios[0]}–{rango_anios[1]}"

    total_obs = int(df_kpi1["total_obs"].iloc[0] or 0)
    esp_unicas = int(df_kpi1["especies_unicas"].iloc[0] or 0)
    obs_anp = int(df_kpi1["obs_anp"].iloc[0] or 0)
    pct_anp = (obs_anp / total_obs * 100) if total_obs > 0 else 0
    esp_im = int(df_kpi1["especies_im"].iloc[0] or 0)

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        kpi_card(f"{total_obs:,}", "Observaciones", texto_crec, "#235A45", "#E4F1EA", "#B2D4C2")
    with c2:
        kpi_card(f"{esp_unicas:,}", "Especies Únicas", "Taxones registrados", "#245873", "#E3EFF5", "#B0CFE0")
    with c3:
        kpi_card(f"{pct_anp:.1f}%", "En ANP", f"{obs_anp:,} registros protegidos", "#3B6E3C", "#EAF2E2", "#C2D8B4")
    with c4:
        kpi_card(f"{esp_im:,}", "Importancia Médica", "Especies con riesgo sanitario", "#8A4B2B", "#F9EAE2", "#E5C0AC")

    col_map, col_bar = st.columns([1.15, 1])

    with col_map:
        if estado_sel == "Todos":
            df_mapa = run_query(
                f"""
                SELECT LPAD(o.cve_ent::text, 2, '0') AS cve_ent, est.nombre, COUNT(*) AS registros
                FROM observaciones o
                JOIN especies e ON o.especie_id = e.especie_id
                JOIN estados est ON LPAD(o.cve_ent::text, 2, '0') = LPAD(est.cve_ent::text, 2, '0')
                {where_sql}
                GROUP BY 1, 2;
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
                color_continuous_scale=["#F4F1EA", "#B7D7C7", "#67A98E", "#2D6A4F"],
                title="Mapa de Densidad por Estado",
            )
        else:
            cve_sel = str(df_cat_estados.loc[df_cat_estados["nombre"] == estado_sel, "cve_ent"].values[0]).zfill(2)
            geojson_mun_estado = {
                "type": "FeatureCollection",
                "features": [
                    {
                        **f,
                        "properties": {
                            **f["properties"],
                            "cve_ent": str(f["properties"]["cve_ent"]).zfill(2),
                            "cvegeo": str(f["properties"]["cvegeo"]).zfill(5),
                        },
                    }
                    for f in geojson_municipios["features"]
                    if str(f["properties"]["cve_ent"]).zfill(2) == cve_sel
                ],
            }
            df_mapa = run_query(
                f"""
                SELECT LPAD(o.cvegeo::text, 5, '0') AS cvegeo, m.nombre, COUNT(*) AS registros
                FROM observaciones o
                JOIN especies e ON o.especie_id = e.especie_id
                JOIN municipios m ON LPAD(o.cvegeo::text, 5, '0') = LPAD(m.cvegeo::text, 5, '0')
                {where_sql}
                GROUP BY 1, 2;
                """,
                params,
            )
            fig_map = px.choropleth(
                df_mapa,
                geojson=geojson_mun_estado,
                locations="cvegeo",
                featureidkey="properties.cvegeo",
                color="registros",
                hover_name="nombre",
                color_continuous_scale=["#F4F1EA", "#B7D7C7", "#67A98E", "#2D6A4F"],
                title=f"Densidad Municipal: {estado_sel}",
            )

        fig_map.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
        fig_map.update_layout(**PLOTLY_LAYOUT, coloraxis_colorbar=dict(title="Registros", thickness=12))
        st.plotly_chart(fig_map, use_container_width=True)

    with col_bar:
        anios_ordenados = sorted(df_anual["anio"].astype(int).unique())
        pos_map = {anio: idx for idx, anio in enumerate(anios_ordenados)}

        df_anual["Zona"] = df_anual["en_anp"].map({True: "En ANP", False: "Fuera de ANP"})
        df_anual["x_pos"] = df_anual["anio"].astype(int).map(pos_map)

        df_yoy = totales_anio.reset_index()
        df_yoy["anio_int"] = df_yoy["anio"].astype(int)
        df_yoy["diff_anio"] = df_yoy["anio_int"].diff()
        df_yoy["crec_pct"] = df_yoy["registros"].pct_change() * 100
        df_yoy["x_pos"] = df_yoy["anio_int"].map(pos_map)

        fig_bar = px.bar(
            df_anual,
            x="x_pos",
            y="registros",
            color="Zona",
            barmode="stack",
            color_discrete_map={"En ANP": "#3B7A63", "Fuera de ANP": "#A8C5B8"},
            title="Crecimiento Anual de Observaciones (ANP vs. No ANP)",
            labels={"x_pos": "Año", "registros": "Registros"},
        )

        for _, row in df_yoy.dropna().iterrows():
            if row["diff_anio"] == 1:
                signo = "+" if row["crec_pct"] >= 0 else ""
                fig_bar.add_annotation(
                    x=row["x_pos"],
                    y=row["registros"],
                    text=f"{signo}{row['crec_pct']:.0f}%",
                    showarrow=False,
                    yshift=10,
                    font=dict(size=10, color="#235A45"),
                )

        fig_bar.update_xaxes(
            tickmode="array",
            tickvals=list(range(len(anios_ordenados))),
            ticktext=[str(a) for a in anios_ordenados],
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
        kpi_card(f"{doy_med}", "Día Pico (DOY)", "Mediana histórica de actividad", "#235A45", "#E4F1EA", "#B2D4C2")
    with k2:
        kpi_card(f"{temp_prom:.1f} °C", "Temperatura Media", "Promedio del periodo seleccionado", "#8C5319", "#FBF0E1", "#E7CCA6")
    with k3:
        kpi_card(f"{precip_prom:.0f} mm", "Precipitación Anual", "Promedio acumulado anual", "#245873", "#E3EFF5", "#B0CFE0")

    meses_lbl = ["Ene", "Feb", "Mar", "Abr", "May", "Jun", "Jul", "Ago", "Sep", "Oct", "Nov", "Dic"]
    df_feno_mes["mes_nombre"] = df_feno_mes["mes"].apply(lambda m: meses_lbl[int(m) - 1])

    fig_dual = make_subplots(specs=[[{"secondary_y": True}]])
    fig_dual.add_trace(
        go.Bar(x=df_feno_mes["mes_nombre"], y=df_feno_mes["registros"], name="Observaciones", marker_color="#67A98E", opacity=0.82),
        secondary_y=False,
    )
    fig_dual.add_trace(
        go.Scatter(x=df_feno_mes["mes_nombre"], y=df_feno_mes["temp_media"], name="Temp. Media (°C)", line=dict(color="#D9822B", width=2.8)),
        secondary_y=True,
    )
    fig_dual.update_layout(**PLOTLY_LAYOUT, title="Observaciones Mensuales vs. Temperatura Media", legend=dict(orientation="h", y=1.12, x=0.65))
    fig_dual.update_yaxes(title_text="Registros", secondary_y=False, showgrid=False)
    fig_dual.update_yaxes(title_text="Temperatura (°C)", secondary_y=True, showgrid=False)
    st.plotly_chart(fig_dual, use_container_width=True)

    c_izq, c_der = st.columns(2)
    with c_izq:
        df_feno_anio["anio_str"] = df_feno_anio["anio"].astype(int).astype(str)
        fig_rango = go.Figure()
        fig_rango.add_trace(go.Scatter(x=df_feno_anio["anio_str"], y=df_feno_anio["doy_p90"], line=dict(width=0), showlegend=False))
        fig_rango.add_trace(
            go.Scatter(
                x=df_feno_anio["anio_str"], y=df_feno_anio["doy_p10"], fill="tonexty",
                fillcolor="rgba(103, 169, 142, 0.25)", line=dict(width=0), name="Ventana activa (P10–P90)"
            )
        )
        fig_rango.add_trace(
            go.Scatter(x=df_feno_anio["anio_str"], y=df_feno_anio["doy_pico"], mode="lines+markers", line=dict(color="#2D6A4F", width=3), name="Día Pico (Mediana)")
        )
        fig_rango.update_xaxes(type="category")
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
            color_discrete_sequence=["#3A7CA5"],
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
        kpi_card(f"{int(df_kpi_im['especies_im'].iloc[0] or 0):,}", "Especies Médicas", "Con registros en el periodo", "#8C5319", "#FBF0E1", "#E7CCA6")
    with m2:
        kpi_card(f"{float(df_kpi_im['pct_fuera_anp'].iloc[0] or 0):.1f}%", "Fuera de ANP", "Zonas urbanas / periurbanas", "#8A4B2B", "#F9EAE2", "#E5C0AC")
    with m3:
        kpi_card(f"{int(df_kpi_im['municipios_im'].iloc[0] or 0):,}", "Municipios con Presencia", "Cobertura municipal detectada", "#245873", "#E3EFF5", "#B0CFE0")

    col_heat, col_right = st.columns([1.2, 1])

    with col_heat:
        titulo_coro_im = "Coroplético Municipal" if estado_sel != "Todos" else "Coroplético por Estado"
        tipo_mapa_im = st.radio(
            "Tipo de mapa:",
            ["Mapa de Calor", "Puntos por Género", titulo_coro_im],
            horizontal=True,
            key="mapa_im_tipo",
        )

        if tipo_mapa_im == "Mapa de Calor":
            df_heat = run_query(
                f"""
                SELECT ROUND(o.latitud::numeric, 2) AS lat, ROUND(o.longitud::numeric, 2) AS lon, COUNT(*) AS densidad
                FROM observaciones o
                JOIN especies e ON o.especie_id = e.especie_id
                {where_im}
                GROUP BY 1, 2;
                """,
                params_im,
            )
            center_im = (
                dict(lat=float(df_heat["lat"].mean()), lon=float(df_heat["lon"].mean()))
                if estado_sel != "Todos" and not df_heat.empty
                else dict(lat=23.6, lon=-102.5)
            )
            zoom_im = 7 if estado_sel != "Todos" and not df_heat.empty else 4

            fig_im_map = px.density_map(
                df_heat,
                lat="lat",
                lon="lon",
                z="densidad",
                radius=12,
                center=center_im,
                zoom=zoom_im,
                map_style="carto-positron",
                color_continuous_scale="YlOrRd",
            )

        elif tipo_mapa_im == "Puntos por Género":
            df_pts = run_query(
                f"""
                SELECT
                    ROUND(o.latitud::numeric, 2) AS lat,
                    ROUND(o.longitud::numeric, 2) AS lon,
                    e.genero,
                    e.especie,
                    COALESCE(NULLIF(TRIM(e.nombre_comun), ''), 'Sin nombre común') AS nombre_comun,
                    COUNT(*) AS registros
                FROM observaciones o
                JOIN especies e ON o.especie_id = e.especie_id
                {where_im}
                GROUP BY 1, 2, 3, 4, 5;
                """,
                params_im,
            )
            center_im = (
                dict(lat=float(df_pts["lat"].mean()), lon=float(df_pts["lon"].mean()))
                if estado_sel != "Todos" and not df_pts.empty
                else dict(lat=23.6, lon=-102.5)
            )
            zoom_im = 7 if estado_sel != "Todos" and not df_pts.empty else 4

            fig_im_map = px.scatter_map(
                df_pts,
                lat="lat",
                lon="lon",
                color="genero",
                size="registros",
                size_max=18,
                center=center_im,
                zoom=zoom_im,
                map_style="carto-positron",
                hover_name="especie",
                hover_data={"nombre_comun": True, "genero": True, "registros": True, "lat": False, "lon": False},
            )

        else:
            if estado_sel == "Todos":
                df_coro_im = run_query(
                    f"""
                    SELECT LPAD(o.cve_ent::text, 2, '0') AS cve_ent, est.nombre, COUNT(*) AS registros
                    FROM observaciones o
                    JOIN especies e ON o.especie_id = e.especie_id
                    JOIN estados est ON LPAD(o.cve_ent::text, 2, '0') = LPAD(est.cve_ent::text, 2, '0')
                    {where_im}
                    GROUP BY 1, 2;
                    """,
                    params_im,
                )
                fig_im_map = px.choropleth(
                    df_coro_im,
                    geojson=geojson_estados,
                    locations="cve_ent",
                    featureidkey="properties.cve_ent",
                    color="registros",
                    hover_name="nombre",
                    color_continuous_scale=["#FBF0E1", "#E8A87C", "#C86D51", "#7F3B27"],
                    title="Importancia Médica por Estado",
                )
            else:
                cve_sel = str(df_cat_estados.loc[df_cat_estados["nombre"] == estado_sel, "cve_ent"].values[0]).zfill(2)
                geojson_mun_estado = {
                    "type": "FeatureCollection",
                    "features": [
                        {
                            **f,
                            "properties": {
                                **f["properties"],
                                "cve_ent": str(f["properties"]["cve_ent"]).zfill(2),
                                "cvegeo": str(f["properties"]["cvegeo"]).zfill(5),
                            },
                        }
                        for f in geojson_municipios["features"]
                        if str(f["properties"]["cve_ent"]).zfill(2) == cve_sel
                    ],
                }
                df_coro_im = run_query(
                    f"""
                    SELECT LPAD(o.cvegeo::text, 5, '0') AS cvegeo, m.nombre, COUNT(*) AS registros
                    FROM observaciones o
                    JOIN especies e ON o.especie_id = e.especie_id
                    JOIN municipios m ON LPAD(o.cvegeo::text, 5, '0') = LPAD(m.cvegeo::text, 5, '0')
                    {where_im}
                    GROUP BY 1, 2;
                    """,
                    params_im,
                )
                fig_im_map = px.choropleth(
                    df_coro_im,
                    geojson=geojson_mun_estado,
                    locations="cvegeo",
                    featureidkey="properties.cvegeo",
                    color="registros",
                    hover_name="nombre",
                    color_continuous_scale=["#FBF0E1", "#E8A87C", "#C86D51", "#7F3B27"],
                    title=f"Importancia Médica Municipal: {estado_sel}",
                )

            fig_im_map.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")

        fig_im_map.update_layout(**PLOTLY_LAYOUT, height=520)
        st.plotly_chart(fig_im_map, use_container_width=True)

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
            color_continuous_scale=["#E8A87C", "#C86D51"],
            title="Top Géneros de Importancia Médica",
            labels={"registros": "Registros", "genero": ""},
        )
        fig_gen.update_layout(**PLOTLY_LAYOUT, height=240, coloraxis_showscale=False)
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
        df_exp_im["anio_str"] = df_exp_im["anio_llegada"].astype(int).astype(str)
        df_exp_im["municipios_acumulados"] = df_exp_im["municipios_acumulados"].astype(int)

        fig_area = px.area(
            df_exp_im,
            x="anio_str",
            y="municipios_acumulados",
            orientation="v",
            title="Expansión Territorial: Municipios Acumulados",
            labels={"anio_str": "Año", "municipios_acumulados": "Municipios"},
            color_discrete_sequence=["#C86D51"],
        )
        fig_area.update_xaxes(type="category")
        fig_area.update_layout(**PLOTLY_LAYOUT, height=240)
        st.plotly_chart(fig_area, use_container_width=True)

    st.markdown("#### Especies de Importancia Médica más Registradas")
    df_top_im = run_query(
        f"""
        SELECT
            e.especie,
            COALESCE(NULLIF(TRIM(e.nombre_comun), ''), 'Sin nombre común') AS nombre_comun,
            e.genero,
            COUNT(*) AS registros,
            COUNT(DISTINCT o.cvegeo) AS municipios
        FROM observaciones o
        JOIN especies e ON o.especie_id = e.especie_id
        {where_im}
        GROUP BY e.especie, e.nombre_comun, e.genero
        ORDER BY registros DESC
        LIMIT 12;
        """,
        params_im,
    )
    st.dataframe(
        df_top_im.rename(columns={
            "especie": "Especie",
            "nombre_comun": "Nombre común",
            "genero": "Género",
            "registros": "Registros",
            "municipios": "Municipios",
        }),
        use_container_width=True,
        hide_index=True,
    )

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
            COALESCE(NULLIF(TRIM(e.nombre_comun), ''), 'Sin nombre común') AS nombre_comun,
            e.clase,
            COUNT(*) AS avistamientos,
            COUNT(DISTINCT o.cve_ent) AS estados,
            COUNT(DISTINCT o.cvegeo) AS municipios
        FROM observaciones o
        JOIN especies e ON o.especie_id = e.especie_id
        {where_inv}
        GROUP BY e.especie, e.nombre_comun, e.clase
        ORDER BY municipios DESC
        LIMIT 15;
        """,
        params_inv,
    )

    if df_inv_top.empty:
        st.info("No se encontraron registros de especies invasoras con los filtros actuales.")
    else:
        col_t, col_e = st.columns([1.15, 1])
        with col_t:
            st.dataframe(
                df_inv_top.rename(columns={
                    "especie": "Especie",
                    "nombre_comun": "Nombre común",
                    "clase": "Clase",
                    "avistamientos": "Avistamientos",
                    "estados": "Estados",
                    "municipios": "Municipios",
                }),
                use_container_width=True,
                hide_index=True,
            )

        with col_e:
            opciones_sp = {"Todas las especies invasoras": "TODAS"}
            for _, row in df_inv_top.iterrows():
                etiqueta = f"{row['especie']} — {row['nombre_comun']}"
                opciones_sp[etiqueta] = row["especie"]

            etiqueta_sel = st.selectbox("Analizar expansión municipal de:", list(opciones_sp.keys()))
            especie_sel = opciones_sp[etiqueta_sel]

            if especie_sel == "TODAS":
                titulo_exp = "Todas las especies invasoras"
                where_actual, params_actual = where_inv, params_inv
            else:
                nombre_comun_sel = df_inv_top.loc[df_inv_top["especie"] == especie_sel, "nombre_comun"].iloc[0]
                titulo_exp = f"{especie_sel} ({nombre_comun_sel})"
                where_actual, params_actual = build_where(["e.es_invasora = TRUE", "e.especie = %s"])
                params_actual = params_actual + (especie_sel,)

            df_exp_sp = run_query(
                f"""
                WITH primer AS (
                    SELECT o.cvegeo, MIN(o.anio) AS anio_llegada
                    FROM observaciones o
                    JOIN especies e ON o.especie_id = e.especie_id
                    {where_actual}
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
                params_actual,
            )
            df_exp_sp["anio_str"] = df_exp_sp["anio_llegada"].astype(int).astype(str)
            df_exp_sp["acumulados"] = df_exp_sp["acumulados"].astype(int)

            fig_inv = px.area(
                df_exp_sp,
                x="anio_str",
                y="acumulados",
                orientation="v",
                title=f"Municipios Acumulados: {titulo_exp}",
                labels={"anio_str": "Año", "acumulados": "Municipios"},
                color_discrete_sequence=["#D9822B"],
            )
            fig_inv.update_xaxes(type="category")
            fig_inv.update_layout(**PLOTLY_LAYOUT)
            st.plotly_chart(fig_inv, use_container_width=True)

        st.markdown("---")
        opciones_mapa_inv = ["Avance por Año (Puntos)", "Mapa de Calor"]
        if estado_sel != "Todos":
            opciones_mapa_inv.append("Densidad Municipal")

        tipo_mapa_inv = st.radio(
            f"Mapa de distribución para {titulo_exp}:",
            opciones_mapa_inv,
            horizontal=True,
            key="mapa_inv_tipo",
        )

        if tipo_mapa_inv == "Densidad Municipal" and estado_sel != "Todos":
            cve_sel = str(df_cat_estados.loc[df_cat_estados["nombre"] == estado_sel, "cve_ent"].values[0]).zfill(2)
            geojson_mun_estado = {
                "type": "FeatureCollection",
                "features": [
                    {
                        **f,
                        "properties": {
                            **f["properties"],
                            "cve_ent": str(f["properties"]["cve_ent"]).zfill(2),
                            "cvegeo": str(f["properties"]["cvegeo"]).zfill(5),
                        },
                    }
                    for f in geojson_municipios["features"]
                    if str(f["properties"]["cve_ent"]).zfill(2) == cve_sel
                ],
            }
            df_mapa_mun_inv = run_query(
                f"""
                SELECT LPAD(o.cvegeo::text, 5, '0') AS cvegeo, m.nombre, COUNT(*) AS registros
                FROM observaciones o
                JOIN especies e ON o.especie_id = e.especie_id
                JOIN municipios m ON LPAD(o.cvegeo::text, 5, '0') = LPAD(m.cvegeo::text, 5, '0')
                {where_actual}
                GROUP BY 1, 2;
                """,
                params_actual,
            )
            fig_inv_map = px.choropleth(
                df_mapa_mun_inv,
                geojson=geojson_mun_estado,
                locations="cvegeo",
                featureidkey="properties.cvegeo",
                color="registros",
                hover_name="nombre",
                color_continuous_scale=["#FBF0E1", "#E8A87C", "#D9822B", "#8C5319"],
                title=f"Densidad Municipal ({estado_sel}): {titulo_exp}",
            )
            fig_inv_map.update_geos(fitbounds="locations", visible=False, bgcolor="rgba(0,0,0,0)")
        else:
            df_mapa_inv = run_query(
                f"""
                SELECT
                    ROUND(o.latitud::numeric, 2) AS lat,
                    ROUND(o.longitud::numeric, 2) AS lon,
                    MIN(o.anio) AS primer_anio,
                    COUNT(*) AS registros
                FROM observaciones o
                JOIN especies e ON o.especie_id = e.especie_id
                {where_actual}
                GROUP BY 1, 2;
                """,
                params_actual,
            )
            center_inv = (
                dict(lat=float(df_mapa_inv["lat"].mean()), lon=float(df_mapa_inv["lon"].mean()))
                if estado_sel != "Todos" and not df_mapa_inv.empty
                else dict(lat=23.6, lon=-102.5)
            )
            zoom_inv = 7 if estado_sel != "Todos" and not df_mapa_inv.empty else 4

            if tipo_mapa_inv == "Avance por Año (Puntos)":
                fig_inv_map = px.scatter_map(
                    df_mapa_inv,
                    lat="lat",
                    lon="lon",
                    color="primer_anio",
                    size="registros",
                    size_max=16,
                    center=center_inv,
                    zoom=zoom_inv,
                    map_style="carto-positron",
                    color_continuous_scale="Viridis",
                    labels={"primer_anio": "Año 1er registro"},
                    title=f"Distribución Histórica: {titulo_exp}",
                )
            else:
                fig_inv_map = px.density_map(
                    df_mapa_inv,
                    lat="lat",
                    lon="lon",
                    z="registros",
                    radius=12,
                    center=center_inv,
                    zoom=zoom_inv,
                    map_style="carto-positron",
                    color_continuous_scale="YlOrRd",
                    title=f"Densidad de Avistamientos: {titulo_exp}",
                )

        fig_inv_map.update_layout(**PLOTLY_LAYOUT, height=480)
        st.plotly_chart(fig_inv_map, use_container_width=True)