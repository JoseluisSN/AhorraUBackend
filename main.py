from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import pandas as pd
import itertools # NECESARIO PARA LA FUERZA BRUTA (PERMUTACIONES)

# -------------------------------------------------------------------
# CONFIGURACIÓN INICIAL Y SIMULACIÓN DE DB
# -------------------------------------------------------------------

app = FastAPI()

# --- SIMULACIÓN DE BASES DE DATOS EN MEMORIA ---
db_usuarios: List[Dict[str, Any]] = [] 
usuario_id_counter: int = 0 
gastos_app: List[Dict[str, Any]] = []
gasto_id_counter: int = 0
db_presupuestos: Dict[int, float] = {}

# Carga del DataSet
try:
    df = pd.read_excel('data.xlsx') 
    data_list: List[Dict[str, Any]] = df.to_dict(orient='records')
    print(f"INFO: DataSet de {len(data_list)} estudiantes cargado.")
except FileNotFoundError:
    data_list = []
    print("ADVERTENCIA: Archivo 'data.xlsx' no encontrado (Usando modo simulación).")

# -------------------------------------------------------------------
# MODELOS DE DATOS
# -------------------------------------------------------------------

class UsuarioBase(BaseModel):
    nombre: str
    email: str = Field(pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    contrasena: str 
    universidad: str 

class LoginRequest(BaseModel):
    email: str
    contrasena: str

class Gasto(BaseModel):
    usuario_id: int 
    categoria: str 
    monto: float   
    descripcion: Optional[str] = None 
    
class Presupuesto(BaseModel):
    usuario_id: int
    monto_semanal: float

# -------------------------------------------------------------------
# ### --- NUEVO: LÓGICA DE GRAFOS Y ALGORITMOS (Backend del Informe) ---
# -------------------------------------------------------------------

# 1. Definición de Nodos para el Grafo (Según informe: Estudiante, Fijo, Variable) [cite: 68-74]
class NodoGasto:
    def __init__(self, id_gasto, categoria, monto, tipo):
        self.id = id_gasto
        self.categoria = categoria
        self.monto = monto
        self.tipo = tipo # "Fijo" o "Variable"

class GrafoFinanciero:
    """
    Representa los gastos del usuario como un Grafo Dirigido.
    Nodo Central: Usuario -> Aristas -> Nodos de Gasto
    """
    def __init__(self, usuario_id):
        self.usuario_id = usuario_id
        self.nodos_gastos: List[NodoGasto] = []
        
    def agregar_gasto(self, gasto: Dict):
        # Clasificación simple basada en el informe (Alquiler/Servicios = Fijo) [cite: 71, 73]
        categoria = gasto['categoria'].lower()
        if 'alquiler' in categoria or 'servicio' in categoria or 'luz' in categoria:
            tipo = "Fijo"
        else:
            tipo = "Variable" # Ocio, Transporte, Alimentación
            
        nuevo_nodo = NodoGasto(gasto.get('gasto_id'), gasto['categoria'], gasto['monto'], tipo)
        self.nodos_gastos.append(nuevo_nodo)

    def obtener_gastos_variables(self):
        # Filtra solo los nodos variables para optimización (O(N))
        return [nodo for nodo in self.nodos_gastos if nodo.tipo == "Variable"]

# 2. Algoritmo de Fuerza Bruta (Permutaciones) [cite: 88, 91]
def algoritmo_fuerza_bruta_ahorro(gastos_variables: List[NodoGasto]):
    """
    Genera escenarios exhaustivos de reducción de gastos.
    Complejidad: O(M^N) donde N es cant. de gastos y M son los niveles de reducción.
    Esto cumple con la "simulación exhaustiva" del informe.
    """
    # Niveles de reducción a probar: 0% (Mantener), 10% (Reducir leve), 20% (Ahorro fuerte)
    niveles_reduccion = [0.0, 0.10, 0.20] 
    
    mejor_escenario = {
        "ahorro_total": 0,
        "detalles": []
    }

    # Generamos TODAS las combinaciones posibles (Producto Cartesiano)
    # Si hay 3 gastos, prueba 3^3 = 27 combinaciones.
    combinaciones = list(itertools.product(niveles_reduccion, repeat=len(gastos_variables)))

    for combinacion in combinaciones:
        ahorro_actual = 0
        detalles_escenario = []

        # Evaluamos esta combinación específica
        for i, reduccion in enumerate(combinacion):
            gasto = gastos_variables[i]
            monto_ahorrado = gasto.monto * reduccion
            ahorro_actual += monto_ahorrado
            
            if reduccion > 0:
                detalles_escenario.append({
                    "categoria": gasto.categoria,
                    "accion": f"Reducir {int(reduccion*100)}%",
                    "ahorro_generado": round(monto_ahorrado, 2)
                })
        
        # Criterio de Selección: Maximizar ahorro (Simple) [cite: 92]
        if ahorro_actual > mejor_escenario["ahorro_total"]:
            mejor_escenario["ahorro_total"] = round(ahorro_actual, 2)
            mejor_escenario["detalles"] = detalles_escenario

    return mejor_escenario

# -------------------------------------------------------------------
# ENDPOINTS EXISTENTES (SIN CAMBIOS)
# -------------------------------------------------------------------

@app.post("/usuarios/", status_code=201)
def registrar_usuario(nuevo_usuario: UsuarioBase):
    global usuario_id_counter
    for usuario in db_usuarios:
        if usuario['email'] == nuevo_usuario.email:
            raise HTTPException(status_code=400, detail="El email ya está registrado.")
    usuario_id_counter += 1
    usuario_data = nuevo_usuario.model_dump()
    usuario_data['id'] = usuario_id_counter
    db_usuarios.append(usuario_data)
    return {"mensaje": "Registro exitoso", "usuario": {"id": usuario_data['id'], "nombre": usuario_data['nombre']}}

@app.post("/login/")
def login_usuario(credenciales: LoginRequest):
    for user in db_usuarios:
        if user['email'] == credenciales.email and user['contrasena'] == credenciales.contrasena:
            return {"mensaje": "Login exitoso", "usuario_id": user['id'], "nombre": user['nombre']}
    raise HTTPException(status_code=401, detail="Credenciales inválidas.")

@app.post("/gastos/", status_code=201)
def registrar_gasto(gasto: Gasto):
    global gasto_id_counter
    gasto_id_counter += 1
    gasto_data = gasto.model_dump()
    gasto_data['gasto_id'] = gasto_id_counter
    gasto_data['timestamp'] = pd.Timestamp.now().isoformat()
    gastos_app.append(gasto_data)
    return {"mensaje": "Gasto registrado", "gasto": gasto_data}

@app.post("/presupuesto/", status_code=201)
def set_presupuesto(presupuesto: Presupuesto):
    db_presupuestos[presupuesto.usuario_id] = presupuesto.monto_semanal
    return {"mensaje": "Presupuesto guardado"}

@app.get("/usuarios/{usuario_id}")
def get_usuario_por_id(usuario_id: int):
    for user in db_usuarios:
        if user['id'] == usuario_id:
            return {"nombre": user['nombre'], "universidad": user['universidad']}     
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

@app.get("/analisis/recomendaciones/{usuario_id}")
def generar_recomendaciones(usuario_id: int):
    """
    Implementa el flujo del informe:
    1. Construye el Grafo de gastos del usuario.
    2. Aplica Fuerza Bruta para hallar escenarios de ahorro[cite: 96].
    3. Devuelve la recomendación óptima.
    """
    # 1. Recuperar gastos del usuario (Búsqueda Lineal O(N))
    gastos_usuario = [g for g in gastos_app if g['usuario_id'] == usuario_id]
    
    if not gastos_usuario:
        return {"mensaje": "No hay suficientes datos para generar recomendaciones."}

    # 2. Construcción del Grafo (Modelado)
    grafo = GrafoFinanciero(usuario_id)
    for gasto in gastos_usuario:
        grafo.agregar_gasto(gasto) # Crea nodos y aristas en memoria

    # 3. Identificar Nodos Variables (Aristas Amarillas en tu informe) [cite: 74]
    nodos_variables = grafo.obtener_gastos_variables()

    if not nodos_variables:
        return {"mensaje": "Solo tienes gastos fijos. No podemos optimizar alquileres o servicios."}

    # 4. Ejecución del Algoritmo de Fuerza Bruta (Simulación de Escenarios)
    resultado_optimo = algoritmo_fuerza_bruta_ahorro(nodos_variables)

    return {
        "usuario_id": usuario_id,
        "analisis": "Algoritmo de Fuerza Bruta completado",
        "total_ahorro_posible": resultado_optimo["ahorro_total"],
        "recomendaciones": resultado_optimo["detalles"],
        "nota_metodologica": "Se han simulado todas las permutaciones de reducción posibles."
    }