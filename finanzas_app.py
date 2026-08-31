from datetime import datetime
import os
import pandas as pd
import streamlit as st

# Configuración de la página
st.set_page_config(
    page_title="Cuentas Compartidas", page_icon="💰", layout="wide"
)

CSV_FILE = "movimientos.csv"


# Función para inicializar o cargar los datos
def cargar_datos():
  if os.path.exists(CSV_FILE):
    df = pd.read_csv(CSV_FILE)
  else:
    # Estructura inicial del archivo de movimientos
    df = pd.DataFrame(columns=[
        "Fecha",
        "Tipo_Operacion",
        "Cuenta",
        "Monto_Local",
        "Monto_Extranjera",
        "Tipo_Cambio",
        "Comentario",
    ])
    df.to_csv(CSV_FILE, index=False)
  return df


df_movs = cargar_datos()

# Título principal
st.title("📊 Control de Cuentas Compartidas")

# --- 1. CÁLCULOS DE BALANCES ---
# Inicializamos contadores
balance_local = 0.0
balance_extranjera = 0.0
buffer_caja_seguridad = 0.0
total_caja_seguridad = 0.0

if not df_movs.empty:
  for _, row in df_movs.iterrows():
    op = row["Tipo_Operacion"]
    monto_l = float(row["Monto_Local"]) if pd.notna(row["Monto_Local"]) else 0.0
    monto_e = (
        float(row["Monto_Extranjera"])
        if pd.notna(row["Monto_Extranjera"])
        else 0.0
    )

    if op == "Ingreso / Gasto":
      if row["Cuenta"] == "Moneda Local":
        balance_local += monto_l
      else:
        balance_extranjera += monto_e
        # Si es un ingreso (positivo) en moneda extranjera, también va al buffer de caja
        if monto_e > 0:
          buffer_caja_seguridad += monto_e
        # Si fuera un egreso (negativo) en moneda extranjera, descuenta del buffer si lo hubiera
        elif monto_e < 0:
          buffer_caja_seguridad += (
              monto_e  # monto_e ya es negativo, por lo que resta
          )

    elif op == "Cambio de Moneda":
      # Resta de local, suma a extranjera y suma al buffer pendiente de caja
      balance_local -= monto_l
      balance_extranjera += monto_e
      buffer_caja_seguridad += monto_e

    elif op == "Traslado a Caja de Seguridad":
      # Reduce el buffer pendiente y aumenta el acumulado de la caja de seguridad
      buffer_caja_seguridad -= monto_e
      total_caja_seguridad += monto_e

# --- 2. DASHBOARD (MÉTRICAS SUPERIORES) ---
st.subheader("Estado Actual")
col1, col2, col3, col4 = st.columns(4)

with col1:
  st.metric(
      label="Balance Moneda Local",
      value=f"$ {balance_local:,.2f}"
      .replace(",", "_")
      .replace(".", ",")
      .replace("_", "."),
  )
with col2:
  st.metric(
      label="Balance Moneda Extranjera",
      value=f"USD {balance_extranjera:,.2f}"
      .replace(",", "_")
      .replace(".", ",")
      .replace("_", "."),
  )
with col3:
  st.metric(
      label="Caja de Seguridad (Total)",
      value=f"USD {total_caja_seguridad:,.2f}"
      .replace(",", "_")
      .replace(".", ",")
      .replace("_", "."),
  )
with col4:
  st.metric(
      label="Pendiente de llevar a Caja",
      value=f"USD {buffer_caja_seguridad:,.2f}"
      .replace(",", "_")
      .replace(".", ",")
      .replace("_", "."),
      help=(
          "Monto en moneda extranjera (por cambios o ingresos) aún no llevado"
          " físicamente a la caja de seguridad."
      ),
  )

st.divider()

# --- 3. SECCIÓN DE REGISTRO (FORMULARIOS) ---
st.subheader("Registrar Nuevo Movimiento")

tab1, tab2, tab3 = st.tabs(
    ["📥 Ingreso / Gasto", "💱 Cambio de Moneda", "🔒 Traslado a Caja de Seguridad"]
)

with tab1:
  with st.form("form_ingreso_gasto"):
    st.info(
        "💡 Nota: Los ingresos en Moneda Extranjera suman al balance y también"
        " se acumulan en el pendiente para llevar a la caja de seguridad."
    )
    col_a, col_b = st.columns(2)
    with col_a:
      cuenta_ie = st.selectbox(
          "Cuenta", ["Moneda Local", "Moneda Extranjera"]
      )
      tipo_ie = st.selectbox("Acción", ["Ingreso (+)", "Egreso (-)"])
    with col_b:
      if cuenta_ie == "Moneda Local":
        monto_val = st.number_input(
            "Monto ($ Local)", min_value=0.0, step=100.0
        )
      else:
        monto_val = st.number_input(
            "Monto (USD Extranjera)", min_value=0.0, step=10.0
        )

    comentario_ie = st.text_input(
        "Comentario / Motivo",
        placeholder="Ej: Pago de expensas, cobro de alquiler...",
    )
    submitted_ie = st.form_submit_button("Guardar Movimiento")

    if submitted_ie:
      if monto_val > 0:
        # Ajustar signo si es egreso
        monto_final = -monto_val if "Egreso" in tipo_ie else monto_val
        ml = monto_final if cuenta_ie == "Moneda Local" else 0.0
        me = monto_final if cuenta_ie == "Moneda Extranjera" else 0.0

        nuevo_reg = pd.DataFrame([{
            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Tipo_Operacion": "Ingreso / Gasto",
            "Cuenta": cuenta_ie,
            "Monto_Local": ml,
            "Monto_Extranjera": me,
            "Tipo_Cambio": "",
            "Comentario": comentario_ie,
        }])
        df_movs = pd.concat([df_movs, nuevo_reg], ignore_index=True)
        df_movs.to_csv(CSV_FILE, index=False)
        st.success("¡Movimiento guardado con éxito!")
        st.rerun()
      else:
        st.warning("El monto debe ser mayor a 0.")

with tab2:
  with st.form("form_cambio"):
    st.info(
        "Registra la salida de moneda local y la entrada de moneda extranjera"
        " generada."
    )
    c1, c2 = st.columns(2)
    with c1:
      entrega_local = st.number_input(
          "Monto Entregado (Moneda Local)", min_value=0.0, step=100.0
      )
    with c2:
      recibe_extranjera = st.number_input(
          "Monto Recibido (Moneda Extranjera)", min_value=0.0, step=10.0
      )

    nota_tc = st.text_input(
        "Nota / Tipo de Cambio utilizado",
        placeholder="Ej: TC a 1250 o cueva Josefina",
    )
    comentario_cambio = st.text_input("Comentario adicional", placeholder="")

    submitted_cambio = st.form_submit_button("Registrar Cambio de Moneda")

    if submitted_cambio:
      if entrega_local > 0 and recibe_extranjera > 0:
        nuevo_reg = pd.DataFrame([{
            "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "Tipo_Operacion": "Cambio de Moneda",
            "Cuenta": "Ambas",
            "Monto_Local": entrega_local,
            "Monto_Extranjera": recibe_extranjera,
            "Tipo_Cambio": nota_tc,
            "Comentario": comentario_cambio,
        }])
        df_movs = pd.concat([df_movs, nuevo_reg], ignore_index=True)
        df_movs.to_csv(CSV_FILE, index=False)
        st.success("¡Cambio registrado y sumado al pendiente de caja!")
        st.rerun()
      else:
        st.warning("Por favor completa ambos montos.")

with tab3:
  with st.form("form_caja"):
    st.info(
        f"Pendiente actual por llevar a caja de seguridad: USD"
        f" {buffer_caja_seguridad:,.2f}"
    )
    monto_llevar = st.number_input(
        "Monto físico que se lleva a la caja de seguridad (USD)",
        min_value=0.0,
        step=10.0,
    )
    comentario_caja = st.text_input(
        "Comentario (opcional)", placeholder="Ej: Depósito físico realizado"
    )
    submitted_caja = st.form_submit_button("Confirmar Traslado")

    if submitted_caja:
      if monto_llevar > 0:
        if monto_llevar <= buffer_caja_seguridad:
          nuevo_reg = pd.DataFrame([{
              "Fecha": datetime.now().strftime("%Y-%m-%d %H:%M"),
              "Tipo_Operacion": "Traslado a Caja de Seguridad",
              "Cuenta": "Moneda Extranjera",
              "Monto_Local": 0.0,
              "Monto_Extranjera": monto_llevar,
              "Tipo_Cambio": "",
              "Comentario": comentario_caja,
          }])
          df_movs = pd.concat([df_movs, nuevo_reg], ignore_index=True)
          df_movs.to_csv(CSV_FILE, index=False)
          st.success("¡Traslado registrado correctamente!")
          st.rerun()
        else:
          st.error(
              "Estás intentando llevar más de lo que tienes pendiente en el"
              " buffer."
          )
      else:
        st.warning("Ingresa un monto válido.")

st.divider()

# --- 4. HISTORIAL Y RESPALDO ---
st.subheader("Historial de Movimientos")
if not df_movs.empty:
  st.dataframe(df_movs, use_container_width=True)

  # Botón de respaldo
  csv_export = df_movs.to_csv(index=False).encode("utf-8")
  st.download_button(
      label="📥 Descargar Respaldo de Movimientos (CSV)",
      data=csv_export,
      file_name=f"respaldo_cuentas_{datetime.now().strftime('%Y-%m-%d')}.csv",
      mime="text/csv",
  )
else:
  st.info("Aún no hay movimientos registrados.")