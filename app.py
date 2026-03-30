import streamlit as st
import pandas as pd
import numpy_financial as npf
import plotly.express as px

# --- Funciones de Cálculo ---

def calcular_escenarios_flujo(
    monto_prestamo,
    duracion_anos,
    cuota_mensual,
    incremento_ipc_anual,
    anos_gracia_ipc,
    pagos_por_ano,
    abonos_extraordinarios,
    cuotas_diferentes,
    cuotas_porcentaje,
):
    """
    Genera dos DataFrames de flujo de caja:
    1. Un flujo "ingenuo" para el cálculo de la TIR, que asume la duración completa.
    2. Un flujo "realista" que simula la amortización para calcular intereses reales.

    Args:
        (Todos los argumentos de la función original)

    Returns:
        tuple: (pd.DataFrame, pd.DataFrame, float) para el flujo de TIR, 
               la tabla de amortización realista, y la tasa de interés periódica del préstamo.
               El segundo y tercer elemento pueden ser None si la tasa base no es válida.
    """
    total_periodos_original = int(round(duracion_anos * pagos_por_ano))

    # --- Escenario 1: Flujo "Ingenuo" para cálculo de TIR ---
    # Asume duración completa y simplemente suma los abonos.
    # Esto es para que la TIR refleje el "costo" de hacer pagos anticipados.
    flujos_para_tir = [0.0] * (total_periodos_original + 1)
    flujos_para_tir[0] = monto_prestamo
    cuotas_base_sin_abono = []

    for periodo in range(1, total_periodos_original + 1):
        # Calcula la cuota estándar con ajuste IPC para este período
        ano_actual = (periodo - 1) / pagos_por_ano + 1
        if ano_actual > anos_gracia_ipc and incremento_ipc_anual > 0:
            anos_con_ajuste = int(ano_actual - anos_gracia_ipc)
            cuota_estandar_periodo = cuota_mensual * ((1 + incremento_ipc_anual) ** anos_con_ajuste)
        else:
            cuota_estandar_periodo = cuota_mensual

        # Esta lista se usa para calcular la tasa de interés implícita, no debe incluir modificaciones
        cuotas_base_sin_abono.append(-cuota_estandar_periodo)

        # Determina la cuota final para el flujo de la TIR, aplicando modificaciones
        if periodo in cuotas_diferentes:
            cuota_final_periodo = cuotas_diferentes[periodo]
        elif periodo in cuotas_porcentaje:
            porcentaje = cuotas_porcentaje[periodo]
            cuota_final_periodo = cuota_mensual * (porcentaje / 100.0)
        else:
            cuota_final_periodo = cuota_estandar_periodo
        flujos_para_tir[periodo] = -cuota_final_periodo

    for periodo_abono, monto_abono in abonos_extraordinarios:
        if 0 < periodo_abono <= total_periodos_original:
            flujos_para_tir[periodo_abono] -= monto_abono

    df_flujo_para_tir = pd.DataFrame({
        "Periodo": range(total_periodos_original + 1),
        "Flujo": flujos_para_tir,
    })

    # --- Escenario 2: Flujo "Realista" para cálculo de Intereses y visualización ---
    flujo_base = [monto_prestamo] + cuotas_base_sin_abono
    tasa_periodica = npf.irr(flujo_base)

    if pd.isna(tasa_periodica) or tasa_periodica < 0:
        return df_flujo_para_tir, None, None

    tabla_amortizacion = []
    saldo_capital = monto_prestamo
    abonos_dict = dict(abonos_extraordinarios)
    cuota_dinamica = cuota_mensual  # Esta cuota se recalculará con los abonos y se ajustará por IPC

    for periodo in range(1, total_periodos_original + 1):
        # Aplicar ajuste por IPC a la cuota dinámica al inicio de cada año (después del período de gracia)
        if (periodo - 1) > 0 and (periodo - 1) % pagos_por_ano == 0:
            ano_actual = ((periodo - 1) / pagos_por_ano) + 1
            if ano_actual > anos_gracia_ipc:
                cuota_dinamica *= (1 + incremento_ipc_anual)

        saldo_inicial_periodo = saldo_capital

        # Si el préstamo ya está pagado, rellenar los períodos restantes con ceros
        # para que la tabla siempre muestre el plazo original completo.
        if saldo_inicial_periodo < 0.01:
            tabla_amortizacion.append({
                "Periodo": periodo,
                "Flujo": 0,
                "Saldo Inicial": 0,
                "Pago Cuota": 0,
                "Abono Extraordinario": 0,
                "Pago Total": 0,
                "Interés Pagado": 0,
                "Abono a Capital": 0,
                "Saldo Final": 0
            })
            saldo_capital = 0  # Asegurarse de que se mantenga en cero
            continue

        interes_periodo = saldo_inicial_periodo * tasa_periodica

        # Determinar la cuota base para este período
        if periodo in cuotas_diferentes:
            pago_base_periodo = cuotas_diferentes[periodo]
        elif periodo in cuotas_porcentaje:
            porcentaje = cuotas_porcentaje[periodo]
            pago_base_periodo = cuota_mensual * (porcentaje / 100.0)
        else:
            pago_base_periodo = cuota_dinamica

        abono_extra_original = abonos_dict.get(periodo, 0)
        pago_total_del_periodo = pago_base_periodo + abono_extra_original

        # Guardar los valores para la tabla, que pueden ser ajustados si hay sobrepago
        pago_cuota_tabla = pago_base_periodo
        abono_extra_tabla = abono_extra_original

        # El pago total no puede ser mayor que el saldo más intereses
        # Y en el último período, debe ser exactamente el saldo más intereses para liquidar.
        if pago_total_del_periodo >= (saldo_inicial_periodo + interes_periodo) or periodo == total_periodos_original:
            pago_total_del_periodo = saldo_capital + interes_periodo
            # Ajustar componentes para la tabla para que la suma sea correcta
            pago_cuota_tabla = min(pago_base_periodo, pago_total_del_periodo)
            abono_extra_tabla = pago_total_del_periodo - pago_cuota_tabla

        abono_a_capital = pago_total_del_periodo - interes_periodo
        saldo_capital -= abono_a_capital

        tabla_amortizacion.append({
            "Periodo": periodo,
            "Flujo": -pago_total_del_periodo,
            "Saldo Inicial": saldo_inicial_periodo,
            "Pago Cuota": pago_cuota_tabla,
            "Abono Extraordinario": abono_extra_tabla,
            "Pago Total": pago_total_del_periodo,
            "Interés Pagado": interes_periodo,
            "Abono a Capital": abono_a_capital,
            "Saldo Final": saldo_capital if saldo_capital > 0.01 else 0.0
        })

        # Si se hizo un abono extra, recalcular la cuota dinámica para los períodos restantes
        if abono_extra_original > 0:
            periodos_restantes = total_periodos_original - periodo
            if periodos_restantes > 0 and saldo_capital > 0.01:
                try:
                    if tasa_periodica > 0:
                        # Fórmula de anualidad para recalcular el pago
                        factor = (1 + tasa_periodica) ** periodos_restantes
                        nueva_cuota = saldo_capital * (tasa_periodica * factor) / (factor - 1)
                        cuota_dinamica = nueva_cuota
                    else: # Caso sin interés
                        cuota_dinamica = saldo_capital / periodos_restantes
                except (OverflowError, ZeroDivisionError):
                    # Fallback en caso de problemas numéricos
                    cuota_dinamica = saldo_capital / periodos_restantes if periodos_restantes > 0 else 0
            else:
                # Si no quedan períodos o no hay saldo, la cuota futura es cero
                cuota_dinamica = 0

    df_flujo_realista = pd.DataFrame(tabla_amortizacion)
    df_periodo_cero = pd.DataFrame([{"Periodo": 0, "Flujo": monto_prestamo, "Saldo Inicial": 0, 
        "Pago Cuota": 0, "Abono Extraordinario": 0, "Pago Total": 0, 
        "Interés Pagado": 0, "Abono a Capital": 0, "Saldo Final": monto_prestamo
    }])
    df_flujo_realista = pd.concat([df_periodo_cero, df_flujo_realista], ignore_index=True)
    return df_flujo_para_tir, df_flujo_realista, tasa_periodica

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

st.sidebar.subheader("Modificaciones de Cuota (Opcional)")

cuotas_diferentes_str = st.sidebar.text_area(
    "Valor de Cuota Específico",
    height=100,
    help="Para meses específicos, reemplace la cuota por un valor absoluto. Formato: 'periodo, monto'. Ejemplo: 24, 1500"
)

cuotas_porcentaje_str = st.sidebar.text_area(
    "Cuota como Porcentaje de la Base (%)",
    height=100,
    help="Para meses específicos, calcule la cuota como un % de la cuota base. Formato: 'periodo, porcentaje'. Ejemplo: 48, 120 (para el 120%)"
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

        # Parseo de cuotas con valor diferente
        cuotas_diferentes = {}
        if cuotas_diferentes_str.strip():
            try:
                lineas = cuotas_diferentes_str.strip().splitlines()
                for linea in lineas:
                    partes = linea.split(',')
                    periodo = int(partes[0].strip())
                    monto = float(partes[1].strip())
                    cuotas_diferentes[periodo] = monto
            except (ValueError, IndexError):
                st.error("El formato de 'Valor de Cuota Específico' no es válido. Use 'periodo, monto'.")
                st.stop()

        # Parseo de cuotas por porcentaje
        cuotas_porcentaje = {}
        if cuotas_porcentaje_str.strip():
            try:
                lineas = cuotas_porcentaje_str.strip().splitlines()
                for linea in lineas:
                    partes = linea.split(',')
                    periodo = int(partes[0].strip())
                    porcentaje = float(partes[1].strip())
                    cuotas_porcentaje[periodo] = porcentaje
            except (ValueError, IndexError):
                st.error("El formato de 'Cuota como Porcentaje' no es válido. Use 'periodo, porcentaje'.")
                st.stop()
        
        # Generar los dos escenarios de flujo de caja
        df_flujo_tir, df_flujo_realista, tasa_interes_prestamo = calcular_escenarios_flujo(
            monto_prestamo,
            duracion_anos,
            cuota_mensual,
            incremento_ipc_anual,
            anos_gracia_ipc,
            pagos_por_ano,
            abonos_extraordinarios,
            cuotas_diferentes,
            cuotas_porcentaje
        )

        if df_flujo_realista is None:
            st.error("No se pudo calcular la tasa de interés implícita del préstamo. Verifique que las cuotas sean suficientes para pagar el crédito o que los parámetros sean consistentes.")
            st.stop()

        total_periodos_original = int(round(duracion_anos * pagos_por_ano))
        # Obtenemos el número real de períodos en los que hubo un pago.
        periodos_reales = 0
        if not df_flujo_realista.empty:
            # Encuentra el último período donde se realizó un pago real.
            df_con_pagos = df_flujo_realista[df_flujo_realista['Pago Total'] > 0.01]
            if not df_con_pagos.empty:
                periodos_reales = int(df_con_pagos['Periodo'].max())

        col1, col2 = st.columns([1, 2])

        with col1:
            st.subheader("Análisis del Plazo")

            # Solo mostramos este análisis si hay datos realistas para comparar
            if periodos_reales > 0:
                saldo_final_real = df_flujo_realista.iloc[-1]["Saldo Final"]
                if periodos_reales < total_periodos_original:
                    st.success(f"¡Pago anticipado! El crédito se liquida en {periodos_reales} períodos en vez de {total_periodos_original}, gracias a los pagos adicionales.")
                elif periodos_reales == total_periodos_original and saldo_final_real > 0.01:
                    st.warning(f"¡Atención! Al final de los {total_periodos_original} períodos, aún queda un saldo de ${saldo_final_real:,.2f}. La cuota base podría ser insuficiente.")
                else:
                    st.info(f"El crédito se liquida correctamente en el plazo planeado de {total_periodos_original} períodos.")

            st.subheader("Resultados")
            # Calcular el total de intereses pagados desde el flujo realista
            total_pagado = -df_flujo_realista.loc[df_flujo_realista['Periodo'] > 0, 'Flujo'].sum()
            total_intereses = total_pagado - monto_prestamo

            try:
                # Calcular TIR desde el flujo "ingenuo" para que refleje el costo del abono
                tir_periodica = npf.irr(df_flujo_tir["Flujo"].values)
                if pd.isna(tir_periodica) or abs(tir_periodica) == float('inf'):
                     st.warning("No se pudo calcular la TIR. Revise si el flujo de caja tiene cambios de signo.")
                else:
                    # Fórmula de anualización de la tasa periódica
                    tir_anual = (1 + tir_periodica) ** pagos_por_ano - 1
                    
                    st.metric(
                        label=f"Tasa Interés Periódica (Préstamo)",
                        value=f"{tasa_interes_prestamo:.4%}",
                        help="Esta es la tasa de interés implícita por período (ej. mensual) calculada a partir del monto, cuota y plazo originales, antes de cualquier abono."
                    )

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

            st.subheader("Tabla de Amortización Detallada")
            columnas_mostrar = [
                "Periodo", 
                "Saldo Inicial", 
                "Pago Cuota",
                "Abono Extraordinario",
                "Pago Total", 
                "Interés Pagado", 
                "Abono a Capital", 
                "Saldo Final"
            ]
            st.dataframe(
                df_flujo_realista[columnas_mostrar].style.format({
                    "Saldo Inicial": "${:,.2f}",
                    "Pago Cuota": "${:,.2f}",
                    "Abono Extraordinario": "${:,.2f}",
                    "Pago Total": "${:,.2f}",
                    "Interés Pagado": "${:,.2f}",
                    "Abono a Capital": "${:,.2f}",
                    "Saldo Final": "${:,.2f}",
                }),
                height=400
            )

        with col2:
            st.subheader("Gráfico del Flujo de Caja")
            # Crear gráfico de barras con Plotly
            fig = px.bar(
                df_flujo_realista,
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
