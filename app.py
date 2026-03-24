import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.express as px

# --- Funciones de Cálculo ---

def generar_flujo_caja(
    monto_prestamo,
    duracion_anos,
    cuota_mensual,
    incremento_ipc_anual,
    anos_gracia_ipc,
    pagos_por_ano,
    abonos_extraordinarios,
):
    """
    Genera un DataFrame con el flujo de caja periódico de una inversión o préstamo.

    Args:
        monto_prestamo (float): Monto inicial del préstamo (flujo positivo para el prestatario).
        duracion_anos (float): Duración total del préstamo en años.
        cuota_mensual (float): Valor de la cuota mensual base (sin ajustes).
        incremento_ipc_anual (float): Porcentaje de incremento anual por IPC (ej: 0.05 para 5%).
        anos_gracia_ipc (int): Número de años sin ajuste por IPC.
        pagos_por_ano (int): Frecuencia de los pagos/cuotas en un año.
        abonos_extraordinarios (list): Lista de tuplas (periodo, monto) para abonos a capital.

    Returns:
        pd.DataFrame: DataFrame con las columnas 'Periodo' y 'Flujo'.
    """
    total_periodos = int(round(duracion_anos * pagos_por_ano))
    flujos = [0] * (total_periodos + 1)
    
    # Periodo 0: Desembolso del préstamo (flujo de entrada positivo)
    flujos[0] = monto_prestamo

    cuota_actual = cuota_mensual

    for periodo in range(1, total_periodos + 1):
        # Determinar el año actual basado en el período y la frecuencia de pagos
        ano_actual = (periodo - 1) / pagos_por_ano + 1

        # Aplicar incremento IPC si ha pasado el período de gracia
        if ano_actual > anos_gracia_ipc and incremento_ipc_anual > 0:
            # El ajuste se calcula basado en los años completos transcurridos desde el fin del período de gracia
            anos_con_ajuste = int(ano_actual - anos_gracia_ipc)
            
            # Recalcular la cuota ajustada desde la base
            cuota_ajustada = cuota_mensual * ((1 + incremento_ipc_anual) ** anos_con_ajuste)
        else:
            cuota_ajustada = cuota_mensual

        # El pago de la cuota es un flujo de salida (negativo)
        flujos[periodo] = -cuota_ajustada

    # Añadir abonos extraordinarios (flujos de salida negativos)
    for periodo_abono, monto_abono in abonos_extraordinarios:
        if 0 < periodo_abono <= total_periodos:
            flujos[periodo_abono] -= monto_abono

    df_flujo = pd.DataFrame({
        "Periodo": range(total_periodos + 1),
        "Flujo": flujos,
    })
    return df_flujo

# --- Interfaz de Usuario con Streamlit ---

st.set_page_config(layout="wide")
st.title("📊 ASTREO - Calculadora de TIR para Préstamos e Inversiones")
st.markdown("Esta herramienta calcula la Tasa Interna de Retorno (TIR) efectiva anual de un flujo de caja, considerando ajustes por IPC y abonos extraordinarios.")

# --- Barra Lateral de Entradas ---

st.sidebar.header("Parámetros de Entrada")

# Valores por defecto para facilitar la prueba
monto_prestamo_default = 100000.0
duracion_anos_default = 10.0
cuota_mensual_default = 1200.0
ipc_anual_default = 5.0  # en porcentaje
anos_gracia_default = 2
pagos_ano_default = 12
abonos_extra_default = """36, 5000
60, 8000"""

# Widgets para la entrada de datos
monto_prestamo = st.sidebar.number_input(
    "Monto del Préstamo/Inversión ($)", 
    min_value=0.0, 
    value=monto_prestamo_default, 
    step=1000.0,
    help="Monto inicial recibido como préstamo o aportado en una inversión."
)

duracion_anos = st.sidebar.number_input(
    "Duración Total (años)", 
    min_value=0.1, 
    value=duracion_anos_default, 
    step=0.5,
    help="Duración total del horizonte de inversión o del crédito."
)

cuota_mensual = st.sidebar.number_input(
    "Valor de la Cuota Fija Mensual ($)", 
    min_value=0.0, 
    value=cuota_mensual_default, 
    step=50.0,
    help="Importe de la cuota base antes de ajustes por IPC."
)

pagos_por_ano = st.sidebar.number_input(
    "Frecuencia de Pagos por Año",
    min_value=1,
    max_value=12,
    value=pagos_ano_default,
    step=1,
    help="Ej: 12 para pagos mensuales, 4 para trimestrales, 1 para anual."
)

st.sidebar.markdown("---")

incremento_ipc_anual_pct = st.sidebar.number_input(
    "Incremento IPC Anual (%)",
    min_value=0.0,
    value=ipc_anual_default,
    step=0.5,
    help="Tasa de inflación anual que ajustará las cuotas. Ingrese 0 si no hay ajuste."
)

anos_gracia_ipc = st.sidebar.number_input(
    "Años de Gracia para Ajuste IPC",
    min_value=0,
    value=anos_gracia_default,
    step=1,
    help="Número de años desde el inicio durante los cuales la cuota no se ajusta por IPC."
)

st.sidebar.markdown("---")

abonos_extraordinarios_str = st.sidebar.text_area(
    "Abonos Extraordinarios (opcional)",
    value=abonos_extra_default,
    height=100,
    help="Lista de abonos a capital. Formato: un abono por línea, 'periodo, monto'. Ejemplo: 36, 5000"
)

# Botón para ejecutar el cálculo
calcular = st.sidebar.button("Calcular TIR", type="primary")

# --- Lógica Principal y Visualización de Resultados ---

if calcular:
    # Conversión de porcentaje a decimal
    incremento_ipc_anual = incremento_ipc_anual_pct / 100.0
    
    # Validación de entradas
    if duracion_anos <= 0 or monto_prestamo <= 0 or cuota_mensual <=0:
        st.error("Por favor, ingrese valores positivos para monto, duración y cuota.")
    else:
        # Parseo de abonos extraordinarios
        abonos_extraordinarios = []
        if abonos_extraordinarios_str.strip():
            try:
                lineas = abonos_extraordinarios_str.strip().splitlines()
                for linea in lineas:
                    partes = linea.split(',')
                    periodo = int(partes[0].strip())
                    monto = float(partes[1].strip())
                    abonos_extraordinarios.append((periodo, monto))
            except (ValueError, IndexError):
                st.error("El formato de los abonos extraordinarios no es válido. Use 'periodo, monto' por línea.")
                st.stop()
        
        # Generar y mostrar el flujo de caja
        df_flujo = generar_flujo_caja(
            monto_prestamo,
            duracion_anos,
            cuota_mensual,
            incremento_ipc_anual,
            anos_gracia_ipc,
            pagos_por_ano,
            abonos_extraordinarios
        )

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Resultados")
            try:
                # Calcular TIR periódica y anualizarla
                tir_periodica = npf.irr(df_flujo["Flujo"].values)
                if pd.isna(tir_periodica) or abs(tir_periodica) == float('inf'):
                     st.warning("No se pudo calcular la TIR. Revise si el flujo de caja tiene cambios de signo.")
                else:
                    # Fórmula de anualización de la tasa periódica
                    tir_anual = (1 + tir_periodica) ** pagos_por_ano - 1
                    
                    st.metric(
                        label=f"TIR Efectiva Anual ({pagos_por_ano} pagos/año)",
                        value=f"{tir_anual:.2%}"
                    )
                    st.info(f"La TIR periódica (base para el cálculo) es de {tir_periodica:.4%}.")

            except ValueError as e:
                st.warning(f"No se pudo calcular la TIR. Es posible que el flujo de caja no cambie de signo, lo que indica que la inversión nunca genera retornos positivos o siempre es rentable. Error: {e}")

            st.subheader("Flujo de Caja Detallado")
            st.dataframe(df_flujo, height=400)

        with col2:
            st.subheader("Gráfico del Flujo de Caja")
            # Crear gráfico de barras con Plotly
            fig = px.bar(
                df_flujo,
                x="Periodo",
                y="Flujo",
                title="Evolución del Flujo de Caja a lo Largo del Tiempo",
                labels={"Flujo": "Monto ($)", "Periodo": "Periodo"},
                color="Flujo",
                color_continuous_scale=px.colors.sequential.RdBu_r,
                template="plotly_white"
            )
            fig.update_layout(
                xaxis_title="Período",
                yaxis_title="Monto del Flujo ($)",
                coloraxis_colorbar=dict(title="Flujo")
            )
            st.plotly_chart(fig, use_container_width=True)

else:
    st.info("Configure los parámetros en la barra lateral y presione 'Calcular TIR' para ver los resultados.")

st.sidebar.markdown("---")
st.sidebar.markdown("Creado por ASTREO - Gustavo Llano.")
