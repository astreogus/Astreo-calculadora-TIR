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
    Genera un DataFrame con el flujo de caja realista de un préstamo, simulando
    la amortización y el efecto de los abonos extraordinarios en la duración.

    Args:
        (Todos los argumentos de la función original)

    Returns:
        pd.DataFrame: DataFrame con las columnas 'Periodo' y 'Flujo', o None si la tasa
                      base no puede ser calculada.
    """
    # 1. Calcular la tasa periódica implícita del crédito SIN abonos.
    flujo_base = [monto_prestamo]
    total_periodos_original = int(round(duracion_anos * pagos_por_ano))
    for p in range(1, total_periodos_original + 1):
        ano_actual = (p - 1) / pagos_por_ano + 1
        if ano_actual > anos_gracia_ipc and incremento_ipc_anual > 0:
            anos_con_ajuste = int(ano_actual - anos_gracia_ipc)
            cuota_ajustada = cuota_mensual * ((1 + incremento_ipc_anual) ** anos_con_ajuste)
        else:
            cuota_ajustada = cuota_mensual
        flujo_base.append(-cuota_ajustada)

    tasa_periodica = npf.irr(flujo_base)

    if pd.isna(tasa_periodica) or tasa_periodica < 0:
        return None # Señal de error si la tasa no es válida

    # 2. Simular la amortización real, período por período, con abonos.
    flujos = [monto_prestamo]
    saldo_capital = monto_prestamo
    abonos_dict = dict(abonos_extraordinarios)

    for periodo in range(1, total_periodos_original + 2): # +1 para el pago final
        if saldo_capital < 0.01:
            break

        interes_periodo = saldo_capital * tasa_periodica

        ano_actual = (periodo - 1) / pagos_por_ano + 1
        cuota_programada = cuota_mensual
        if ano_actual > anos_gracia_ipc and incremento_ipc_anual > 0:
            anos_con_ajuste = int(ano_actual - anos_gracia_ipc)
            cuota_programada = cuota_mensual * ((1 + incremento_ipc_anual) ** anos_con_ajuste)

        abono_extra = abonos_dict.get(periodo, 0)
        pago_total_del_periodo = cuota_programada + abono_extra

        if (saldo_capital + interes_periodo) < pago_total_del_periodo:
            pago_total_del_periodo = saldo_capital + interes_periodo

        flujos.append(-pago_total_del_periodo)
        abono_a_capital = pago_total_del_periodo - interes_periodo
        saldo_capital -= abono_a_capital

    df_flujo = pd.DataFrame({
        "Periodo": range(len(flujos)),
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

        if df_flujo is None:
            st.error("No se pudo calcular la tasa de interés implícita del préstamo. Verifique que las cuotas sean suficientes para pagar el crédito o que los parámetros sean consistentes.")
            st.stop()

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Resultados")
            # Calcular el total de intereses pagados
            total_pagado = -df_flujo.loc[df_flujo['Periodo'] > 0, 'Flujo'].sum()
            total_intereses = total_pagado - monto_prestamo

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
                    st.metric(
                        label="Total Intereses Pagados",
                        value=f"${total_intereses:,.2f}",
                        help="Suma de todas las cuotas y abonos menos el monto del préstamo inicial. Un abono extraordinario debería reducir este valor."
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
