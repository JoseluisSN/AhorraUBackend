from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List, Union
import pandas as pd
import itertools 
import random    
from datetime import datetime

app = FastAPI(
    title="AhorraU Backend",
    description="API v3.11.0: Respuesta de registro unificada y estándar.",
    version="3.11.0"
)

# ===================================================================
# 🛡️ INTERCEPTORES DE ERRORES (Anti [object Object])
# ===================================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    errores = []
    for error in exc.errors():
        loc = error.get("loc", ["campo"])
        campo = loc[-1]
        msg = error.get("msg", "Error")
        errores.append(f"{campo}: {msg}")
    
    mensaje_texto = "Datos inválidos: " + "; ".join(errores)
    print(f"⚠️ Validación falló: {mensaje_texto}")
    return JSONResponse(status_code=422, content={"detail": mensaje_texto})

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    mensaje_texto = str(exc.detail)
    print(f"⚠️ Error HTTP ({exc.status_code}): {mensaje_texto}")
    return JSONResponse(status_code=exc.status_code, content={"detail": mensaje_texto})

@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    mensaje_texto = f"Error interno del servidor: {str(exc)}"
    print(f"❌ CRASH INTERNO: {mensaje_texto}")
    return JSONResponse(status_code=500, content={"detail": mensaje_texto})


# ===================================================================
# 💾 SIMULACIÓN DE BD
# ===================================================================
db_usuarios: List[Dict[str, Any]] = [
    {
        "id": 1,
        "nombre": "Usuario Prueba",
        "email": "test@upc.edu.pe",
        "password": "123456",
        "universidad": "UPC"
    }
]
usuario_id_counter: int = 1 
gastos_app: List[Dict[str, Any]] = []
gasto_id_counter: int = 0
categorias_base: List[str] = ["alquiler", "servicios", "ocio", "alimentos", "transporte", "otros", "educacion"]
categorias_globales = categorias_base.copy()

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
    universidad: str
    password: Optional[str] = None
    contrasena: Optional[str] = None 
    contraseña: Optional[str] = None 

class LoginRequest(BaseModel):
    email: str
    password: Optional[str] = None
    contrasena: Optional[str] = None
    contraseña: Optional[str] = None

class Gasto(BaseModel):
    usuario_id: int 
    categoria: str 
    monto: float   
    descripcion: Optional[str] = None 

class UpdateGastosPayload(BaseModel):
    usuario_id: Optional[Union[int, str]] = None 
    gastos: Dict[str, float]

class DetalleGastosResponse(BaseModel):
    usuario_id: int
    gastos: Dict[str, float]

class NuevaCategoriaRequest(BaseModel):
    categoria: str

class FuerzaBrutaRequest(BaseModel):
    usuario_id: Optional[Union[int, str]] = None
    gasto_actual: Optional[float] = None
    meta: Optional[float] = None
    gastoSemanal: Optional[float] = None
    metaGasto: Optional[float] = None

class RecuperarPassRequest(BaseModel):
    email: str

class EditarPerfilRequest(BaseModel):
    usuario_id: int
    nuevo_nombre: Optional[str] = None
    nueva_universidad: Optional[str] = None

class EscenarioRequest(BaseModel):
    usuario_id: Optional[Union[int, str]] = None
    meta_ahorro_semanal: Optional[float] = None
    gasto_actual: Optional[float] = None
    meta: Optional[float] = None
    gastoSemanal: Optional[float] = None
    metaGasto: Optional[float] = None

class OrdenarGastosRequest(BaseModel):
    usuario_id: int

# -------------------------------------------------------------------
# LÓGICA DE ALGORITMOS
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

    niveles_reduccion = [0.0, 0.10, 0.20, 0.30, 0.40, 0.50]
    
    mejor_escenario_absoluto = None
    maximo_ahorro_posible = 0.0
    
    mejor_escenario_cumplido = None
    menor_impacto = float('inf')
    
    limit_vars = gastos_variables[:6]
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
                porcentaje_real = int(reduccion * 100)
                detalles.append({
                    "categoria": gasto.categoria,
                    "accion": f"Reducir {porcentaje_real}%", 
                    "ahorro_item": round(ahorro, 2),
                    "nuevo_monto": round(gasto.monto - ahorro, 2)
                })

        escenario_actual = {
            "exito": True,
            "ahorro_total": round(ahorro_acumulado, 2),
            "estrategia": detalles
        }

        if ahorro_acumulado > maximo_ahorro_posible:
            maximo_ahorro_posible = ahorro_acumulado
            mejor_escenario_absoluto = escenario_actual

        if ahorro_acumulado >= meta_ahorro:
            if impacto_acumulado < menor_impacto:
                menor_impacto = impacto_acumulado
                mejor_escenario_cumplido = escenario_actual

    if mejor_escenario_cumplido:
        return mejor_escenario_cumplido
    elif mejor_escenario_absoluto:
        mejor_escenario_absoluto["mensaje"] = f"Meta muy alta. Máximo ahorro posible: S/{maximo_ahorro_posible}"
        return mejor_escenario_absoluto
    else:
        return {"exito": False, "mensaje": "No se encontraron gastos variables para reducir."}

# -------------------------------------------------------------------
# SECCIÓN 1: AUTENTICACIÓN
# -------------------------------------------------------------------
@app.post("/login/", tags=["Autenticación"])
def login_usuario(credenciales: LoginRequest):
    print(f"👉 LOGIN: {credenciales.email}")
    password_final = credenciales.password or credenciales.contrasena or credenciales.contraseña
    if not password_final:
        raise HTTPException(status_code=422, detail="Falta la contraseña")

    for user in db_usuarios:
        if user['email'] == credenciales.email and user['password'] == password_final:
            print(f"✅ Login OK: {user['nombre']}")
            # Login también usa estructura estándar
            return {
                "usuario": {
                    "id": user['id'],
                    "nombre": user['nombre'],
                    "email": user['email'],
                    "universidad": user['universidad']
                },
                "token": "token-simulado-123"
            }
    
    print("❌ Login Fallido")
    raise HTTPException(status_code=401, detail="Credenciales incorrectas")

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
    print(f"👉 REGISTRO: {nuevo_usuario.email}")
    password_final = nuevo_usuario.password or nuevo_usuario.contrasena or nuevo_usuario.contraseña
    if not password_final:
        raise HTTPException(status_code=422, detail="Falta la contraseña.")

    for u in db_usuarios:
        if u['email'] == nuevo_usuario.email:
            raise HTTPException(status_code=400, detail="El email ya existe.")
    
    usuario_id_counter += 1
    usuario_data = {
        "id": usuario_id_counter,
        "nombre": nuevo_usuario.nombre,
        "email": nuevo_usuario.email,
        "password": password_final,
        "universidad": nuevo_usuario.universidad
    }
    db_usuarios.append(usuario_data)
    print(f"✅ Registro OK: ID {usuario_id_counter}")
    
    # 🔥 RESPUESTA UNIFICADA: Exactamente lo que pediste
    return {
        "usuario": {
            "id": usuario_data['id'],
            "nombre": usuario_data['nombre'],
            "email": usuario_data['email'],
            "universidad": usuario_data['universidad']
        },
        "token": "token-simulado-reg"
    }

@app.get("/usuarios/", tags=["Gestión de Usuarios"])
def listar_todos_usuarios():
    return [{k:v for k,v in u.items() if k!='password'} for u in db_usuarios]

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
# SECCIÓN 3: GESTIÓN DE GASTOS
# -------------------------------------------------------------------

@app.get("/gastos/usuario/{usuario_id}", response_model=DetalleGastosResponse, tags=["Gestión de Gastos"])
def obtener_gastos_usuario(usuario_id: Union[int, str]):
    try:
        uid_final = int(usuario_id)
    except (TypeError, ValueError):
        print(f"⚠️ ID inválido recibido: '{usuario_id}'. Usando ID 1 por defecto.")
        uid_final = 1

    mis_gastos = [g for g in gastos_app if g['usuario_id'] == uid_final]
    
    resumen_gastos = {cat: 0.0 for cat in categorias_base}
    
    for g in mis_gastos:
        cat_nombre = g['categoria'].lower()
        monto = g['monto']
        
        if cat_nombre in resumen_gastos:
            resumen_gastos[cat_nombre] += monto
        else:
            resumen_gastos[cat_nombre] = monto
            
    return {
        "usuario_id": uid_final,
        "gastos": resumen_gastos
    }

@app.post("/gastos/actualizar", tags=["Gestión de Gastos"])
def actualizar_gastos(payload: UpdateGastosPayload):
    try:
        usuario_id = int(payload.usuario_id)
    except (TypeError, ValueError):
        usuario_id = 1 

    global gasto_id_counter, gastos_app
    
    gastos_app = [g for g in gastos_app if g['usuario_id'] != usuario_id]
    
    nuevos_gastos = []
    for categoria, monto in payload.gastos.items():
        if categoria.lower() == "total": 
            continue
            
        if monto >= 0: 
            gasto_id_counter += 1
            gasto = {
                "gasto_id": gasto_id_counter, 
                "usuario_id": usuario_id,
                "categoria": categoria, 
                "monto": float(monto),
                "descripcion": "Edición Manual", 
                "timestamp": pd.Timestamp.now().isoformat()
            }
            gastos_app.append(gasto)
            nuevos_gastos.append(gasto)
            
            if categoria not in categorias_globales: 
                categorias_globales.append(categoria)
                
    return {"exito": True, "mensaje": "Gastos actualizados correctamente"}

@app.get("/gastos/totales", tags=["Gestión de Gastos"])
def obtener_gastos_totales(usuario_id: int):
    mis_gastos = [g for g in gastos_app if g['usuario_id'] == usuario_id]
    total = sum(g['monto'] for g in mis_gastos)
    promedio = round(total / 7, 2) if total > 0 else 0
    return {
        "mensual": {"labels": ["Ene", "Feb", "Mar", "Abr"], "data": [250, 320, 280, total]},
        "semanal": {"labels": ["Lun", "Mar", "Mié", "Jue", "Vie", "Sáb", "Dom"], "data": [random.randint(10, 50) for _ in range(7)]},
        "total_gastos": total, "promedio_diario": promedio
    }

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
def calcular_fuerza_bruta_simple(request: FuerzaBrutaRequest):
    try:
        usuario_id = int(request.usuario_id)
    except (TypeError, ValueError):
        usuario_id = 1

    gasto_final = request.gasto_actual or request.gastoSemanal
    meta_final = request.meta or request.metaGasto
    
    if gasto_final is None or meta_final is None:
        return {
            "exito": True, 
            "mensaje": "Por favor ingresa montos para calcular.", 
            "ahorro_total": 0, 
            "estrategia": []
        }

    ahorro_necesario = gasto_final - meta_final
    
    mis_gastos = [g for g in gastos_app if g['usuario_id'] == usuario_id]
    
    grafo = GrafoFinanciero(usuario_id)
    for g in mis_gastos: grafo.agregar_gasto(g)
    
    variables = grafo.obtener_gastos_variables()
    
    if not variables:
        variables = [
            NodoGasto(0, "Gastos Generales (Simulado)", gasto_final, "Variable")
        ]
    
    res = algoritmo_fuerza_bruta(variables, ahorro_necesario)
    res["contexto"] = {"gasto_actual": gasto_final, "meta": meta_final}
    return res

@app.post("/calcular-escenario", tags=["Algoritmos Avanzados"])
def calcular_escenario_legacy(request: EscenarioRequest):
    try:
        uid = int(request.usuario_id)
    except:
        uid = 1

    gasto = request.gasto_actual or request.gastoSemanal
    meta = request.meta or request.metaGasto
    
    if gasto is not None and meta is not None:
        return calcular_fuerza_bruta_simple(
            FuerzaBrutaRequest(
                usuario_id=uid,
                gasto_actual=gasto,
                meta=meta
            )
        )
    
    if request.meta_ahorro_semanal is not None:
        return calcular_fuerza_bruta_simple(
            FuerzaBrutaRequest(
                usuario_id=uid,
                gasto_actual=9999,
                meta=9999-request.meta_ahorro_semanal
            )
        )
        
    return {"exito": False, "mensaje": "Faltan datos de cálculo."}

@app.post("/ordenar-gastos", tags=["Algoritmos Avanzados"])
def ordenar_gastos(request: OrdenarGastosRequest):
    mis_gastos = [g for g in gastos_app if g['usuario_id'] == request.usuario_id]
    return quicksort_gastos(mis_gastos) if mis_gastos else []

@app.get("/grafos/usuario/{usuario_id}", tags=["Algoritmos Avanzados"])
def obtener_grafo_usuario(usuario_id: int):
    mis_gastos = [g for g in gastos_app if g['usuario_id'] == usuario_id]
    grafo = GrafoFinanciero(usuario_id)
    for g in mis_gastos: grafo.agregar_gasto(g)
    return grafo.exportar_grafo()