from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import pandas as pd
import itertools 
import random    
from datetime import datetime

app = FastAPI(
    title="AhorraU Backend",
    description="API para gestión financiera de estudiantes con Algoritmos de Complejidad.",
    version="2.2.0"
)

# -------------------------------------------------------------------
# SIMULACIÓN DE BASES DE DATOS
# -------------------------------------------------------------------
db_usuarios: List[Dict[str, Any]] = [] 
usuario_id_counter: int = 0 
gastos_app: List[Dict[str, Any]] = []
gasto_id_counter: int = 0
db_presupuestos: Dict[int, float] = {}

# Lista global de categorías permitidas
categorias_globales: List[str] = ["alquiler", "servicios", "ocio", "alimentos", "transporte", "otros", "educacion"]

# Carga del DataSet
try:
    df = pd.read_excel('data.xlsx') 
    data_list: List[Dict[str, Any]] = df.to_dict(orient='records')
    print(f"INFO: DataSet de {len(data_list)} estudiantes cargado.")
except FileNotFoundError:
    data_list = []
    print("ADVERTENCIA: Archivo 'data.xlsx' no encontrado (Usando modo simulación).")

# -------------------------------------------------------------------
# MODELOS DE DATOS (Schemas)
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

# --- Modelos para Vistas y Algoritmos ---
class UpdateGastosPayload(BaseModel):
    gastos: Dict[str, float]

class NuevaCategoriaRequest(BaseModel):
    categoria: str

class FuerzaBrutaSimpleRequest(BaseModel):
    gasto_actual: float
    meta: float

class RecuperarPassRequest(BaseModel):
    email: str

class EditarPerfilRequest(BaseModel):
    usuario_id: int
    nuevo_nombre: Optional[str] = None
    nueva_universidad: Optional[str] = None

class EscenarioRequest(BaseModel):
    usuario_id: int
    meta_ahorro_semanal: float 

class OrdenarGastosRequest(BaseModel):
    usuario_id: int

# --- Modelos para Gráficos (Nuevo) ---
class ChartData(BaseModel):
    labels: List[str]
    data: List[float]

class GastosTotalesResponse(BaseModel):
    mensual: ChartData
    semanal: ChartData
    total_gastos: float
    promedio_diario: float

# -------------------------------------------------------------------
# LÓGICA DE ALGORITMOS (CLASES Y FUNCIONES)
# -------------------------------------------------------------------

class NodoGasto:
    def __init__(self, id_gasto, categoria, monto, tipo):
        self.id = id_gasto
        self.categoria = categoria
        self.monto = monto
        self.tipo = tipo

class GrafoFinanciero:
    def __init__(self, usuario_id):
        self.usuario_id = usuario_id
        self.nodos_gastos: List[NodoGasto] = []
        
    def agregar_gasto(self, gasto: Dict):
        cat = gasto['categoria'].lower()
        if any(x in cat for x in ['alquiler', 'servicio', 'luz', 'agua', 'internet', 'educacion', 'educación']):
            tipo = "Fijo"
        else:
            tipo = "Variable"
        nuevo_nodo = NodoGasto(gasto.get('gasto_id'), gasto['categoria'], gasto['monto'], tipo)
        self.nodos_gastos.append(nuevo_nodo)

    def obtener_gastos_variables(self):
        return [nodo for nodo in self.nodos_gastos if nodo.tipo == "Variable"]
    
    def exportar_grafo(self):
        nodos = [{"id": "U", "label": "Yo", "color": "#007AFF"}]
        aristas = []
        for g in self.nodos_gastos:
            color = "#FF3B30" if g.tipo == "Fijo" else "#FFCC00"
            nodo_id = f"G{g.id}"
            nodos.append({"id": nodo_id, "label": f"{g.categoria}\nS/{g.monto}", "color": color})
            aristas.append({"from": "U", "to": nodo_id})
        return {"nodos": nodos, "aristas": aristas}

def quicksort_gastos(lista_gastos: List[Dict]):
    if len(lista_gastos) <= 1:
        return lista_gastos
    pivot = lista_gastos[len(lista_gastos) // 2]
    monto_pivot = pivot['monto']
    left = [x for x in lista_gastos if x['monto'] > monto_pivot]
    middle = [x for x in lista_gastos if x['monto'] == monto_pivot]
    right = [x for x in lista_gastos if x['monto'] < monto_pivot]
    return quicksort_gastos(left) + middle + quicksort_gastos(right)

def algoritmo_fuerza_bruta(gastos_variables: List[NodoGasto], meta_ahorro: float):
    if meta_ahorro <= 0:
        return {"exito": True, "mensaje": "Presupuesto cumplido.", "ahorro_total": 0, "estrategia": []}

    niveles_reduccion = [0.0, 0.10, 0.25, 0.50]
    mejor_escenario = None
    menor_impacto = float('inf')
    limit_vars = gastos_variables[:8] 
    combinaciones = list(itertools.product(niveles_reduccion, repeat=len(limit_vars)))

    for combinacion in combinaciones:
        ahorro_acumulado = 0
        impacto_acumulado = 0
        detalles = []
        for i, reduccion in enumerate(combinacion):
            gasto = limit_vars[i]
            ahorro = gasto.monto * reduccion
            ahorro_acumulado += ahorro
            impacto_acumulado += reduccion
            if reduccion > 0:
                detalles.append({
                    "categoria": gasto.categoria,
                    "accion": f"Reducir {int(reduccion*100)}%",
                    "ahorro_item": round(ahorro, 2),
                    "nuevo_monto": round(gasto.monto - ahorro, 2)
                })

        if ahorro_acumulado >= meta_ahorro:
            if impacto_acumulado < menor_impacto:
                menor_impacto = impacto_acumulado
                mejor_escenario = {
                    "exito": True,
                    "ahorro_total": round(ahorro_acumulado, 2),
                    "estrategia": detalles
                }

    if mejor_escenario:
        return mejor_escenario
    else:
        return {"exito": False, "mensaje": "Imposible llegar a la meta reduciendo solo variables."}

# -------------------------------------------------------------------
# SECCIÓN 1: AUTENTICACIÓN
# -------------------------------------------------------------------
@app.post("/login/", tags=["Autenticación"])
def login_usuario(credenciales: LoginRequest):
    for user in db_usuarios:
        if user['email'] == credenciales.email and user['contrasena'] == credenciales.contrasena:
            return {"mensaje": "Login exitoso", "usuario_id": user['id'], "nombre": user['nombre']}
    raise HTTPException(status_code=401, detail="Credenciales inválidas.")

@app.post("/recuperar-contrasena", tags=["Autenticación"])
def recuperar_contrasena(request: RecuperarPassRequest):
    for user in db_usuarios:
        if user['email'] == request.email:
            return {"mensaje": f"Correo enviado a {request.email}."}
    raise HTTPException(status_code=404, detail="El correo no está registrado.")

# -------------------------------------------------------------------
# SECCIÓN 2: GESTIÓN DE USUARIOS
# -------------------------------------------------------------------
@app.post("/usuarios/", status_code=201, tags=["Gestión de Usuarios"])
def registrar_usuario(nuevo_usuario: UsuarioBase):
    global usuario_id_counter
    for u in db_usuarios:
        if u['email'] == nuevo_usuario.email:
            raise HTTPException(status_code=400, detail="El email ya existe.")
    usuario_id_counter += 1
    usuario_data = nuevo_usuario.model_dump()
    usuario_data['id'] = usuario_id_counter
    db_usuarios.append(usuario_data)
    return {"mensaje": "Registro exitoso", "usuario": {"id": usuario_data['id']}}

@app.get("/usuarios/", tags=["Gestión de Usuarios"])
def listar_todos_usuarios():
    return [{k:v for k,v in u.items() if k!='contrasena'} for u in db_usuarios]

@app.get("/usuarios/{usuario_id}", tags=["Gestión de Usuarios"])
def obtener_perfil_usuario(usuario_id: int):
    for user in db_usuarios:
        if user['id'] == usuario_id:
            return {"nombre": user['nombre'], "universidad": user['universidad'], "email": user['email']}     
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

@app.put("/perfil/editar", tags=["Gestión de Usuarios"])
def editar_perfil(request: EditarPerfilRequest):
    for user in db_usuarios:
        if user['id'] == request.usuario_id:
            if request.nuevo_nombre: user['nombre'] = request.nuevo_nombre
            if request.nueva_universidad: user['universidad'] = request.nueva_universidad
            return {"mensaje": "Perfil actualizado", "usuario": user}
    raise HTTPException(status_code=404, detail="Usuario no encontrado")

# -------------------------------------------------------------------
# SECCIÓN 3: GESTIÓN DE GASTOS (VISTAS DETALLE Y TOTALES)
# -------------------------------------------------------------------

@app.get("/gastos/totales", tags=["Gestión de Gastos"])
def obtener_gastos_totales(usuario_id: int):
    """
    **Endpoint solicitado (Gastos Totales):** Devuelve datos para gráficas mensuales/semanales y promedios.
    """
    mis_gastos = [g for g in gastos_app if g['usuario_id'] == usuario_id]
    
    total = sum(g['monto'] for g in mis_gastos)
    promedio = round(total / 7, 2) if total > 0 else 0

    return {
        "mensual": {
            "labels": ["Ene", "Feb", "Mar", "Abr"],
            "data": [250, 320, 280, total] # Abril refleja el total actual
        },
        "semanal": {
            "labels": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"],
            "data": [random.randint(10, 50) for _ in range(7)] # Simulado para la demo
        },
        "total_gastos": total,
        "promedio_diario": promedio
    }

@app.post("/gastos/actualizar", tags=["Gestión de Gastos"])
def actualizar_gastos(payload: UpdateGastosPayload, usuario_id: int):
    """Actualiza los gastos desde la vista 'Detalle'."""
    global gasto_id_counter, gastos_app
    gastos_app = [g for g in gastos_app if g['usuario_id'] != usuario_id]
    nuevos_gastos = []
    
    for categoria, monto in payload.gastos.items():
        if categoria.lower() == "total" or monto <= 0: continue
        gasto_id_counter += 1
        gasto = {
            "gasto_id": gasto_id_counter, "usuario_id": usuario_id,
            "categoria": categoria, "monto": float(monto),
            "descripcion": "Carga manual", "timestamp": pd.Timestamp.now().isoformat()
        }
        gastos_app.append(gasto)
        nuevos_gastos.append(gasto)
        if categoria not in categorias_globales: categorias_globales.append(categoria)
            
    return {"mensaje": "Gastos actualizados", "cantidad": len(nuevos_gastos)}

@app.post("/categorias/nueva", tags=["Gestión de Gastos"])
def crear_nueva_categoria(request: NuevaCategoriaRequest):
    cat = request.categoria.lower().strip()
    if cat not in categorias_globales: categorias_globales.append(cat)
    return {"mensaje": "Categoría creada", "lista": categorias_globales}

@app.post("/gastos/", status_code=201, tags=["Gestión de Gastos"])
def registrar_gasto_individual(gasto: Gasto):
    global gasto_id_counter
    gasto_id_counter += 1
    d = gasto.model_dump()
    d['gasto_id'] = gasto_id_counter
    gastos_app.append(d)
    return {"mensaje": "Gasto registrado", "gasto": d}

# -------------------------------------------------------------------
# SECCIÓN 4: ALGORITMOS AVANZADOS
# -------------------------------------------------------------------

@app.post("/algoritmo/fuerza_bruta", tags=["Algoritmos Avanzados"])
def calcular_fuerza_bruta_simple(request: FuerzaBrutaSimpleRequest, usuario_id: int):
    """Calcula ahorro necesario basado en Gasto Actual vs Meta."""
    ahorro_necesario = request.gasto_actual - request.meta
    
    mis_gastos = [g for g in gastos_app if g['usuario_id'] == usuario_id]
    if not mis_gastos: return {"exito": False, "mensaje": "Sin gastos registrados."}

    grafo = GrafoFinanciero(usuario_id)
    for g in mis_gastos: grafo.agregar_gasto(g)
    
    variables = grafo.obtener_gastos_variables()
    if not variables: return {"exito": False, "mensaje": "Solo tienes gastos fijos."}

    res = algoritmo_fuerza_bruta(variables, ahorro_necesario)
    res["contexto"] = {"gasto_actual": request.gasto_actual, "meta": request.meta}
    return res

@app.post("/calcular-escenario", tags=["Algoritmos Avanzados"])
def calcular_escenario_legacy(request: EscenarioRequest):
    """Versión Legacy (mantiene compatibilidad)."""
    return calcular_fuerza_bruta_simple(
        FuerzaBrutaSimpleRequest(gasto_actual=9999, meta=9999-request.meta_ahorro_semanal), 
        request.usuario_id
    )

@app.post("/ordenar-gastos", tags=["Algoritmos Avanzados"])
def ordenar_gastos(request: OrdenarGastosRequest):
    """Quicksort."""
    mis_gastos = [g for g in gastos_app if g['usuario_id'] == request.usuario_id]
    return quicksort_gastos(mis_gastos) if mis_gastos else []

@app.get("/grafos/usuario/{usuario_id}", tags=["Algoritmos Avanzados"])
def obtener_grafo_usuario(usuario_id: int):
    """Grafo visual."""
    mis_gastos = [g for g in gastos_app if g['usuario_id'] == usuario_id]
    grafo = GrafoFinanciero(usuario_id)
    for g in mis_gastos: grafo.agregar_gasto(g)
    return grafo.exportar_grafo()