from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import pandas as pd
import uvicorn # Usado solo para contexto

# -------------------------------------------------------------------
# CONFIGURACIÓN INICIAL Y SIMULACIÓN DE DB
# -------------------------------------------------------------------

app = FastAPI()

# --- SIMULACIÓN DE BASES DE DATOS EN MEMORIA ---
# Los usuarios registrados por la app
db_usuarios: List[Dict[str, Any]] = [] 
usuario_id_counter: int = 0 
# Los gastos registrados por la app
gastos_app: List[Dict[str, Any]] = []
gasto_id_counter: int = 0
# Presupuestos semanales O(1)
db_presupuestos: Dict[int, float] = {}

# Carga del DataSet de 1500 estudiantes (IMPORTANTE para tu O(N))
try:
    # Ajusta el nombre del archivo si es diferente, ej: 'dataset.xlsx'
    df = pd.read_excel('data.xlsx') 
    data_list: List[Dict[str, Any]] = df.to_dict(orient='records')
    print(f"INFO: DataSet de {len(data_list)} estudiantes cargado.")
except FileNotFoundError:
    data_list = []
    print("ADVERTENCIA: Archivo 'data.xlsx' no encontrado.")

# -------------------------------------------------------------------
# MODELOS DE DATOS (Pydantic Schemas)
# -------------------------------------------------------------------

class UsuarioBase(BaseModel):
    # Modelo para recibir datos del formulario de registro
    nombre: str
    # Usamos una expresión regular para una validación básica de email
    email: str = Field(pattern=r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
    contrasena: str 
    universidad: str 

class LoginRequest(BaseModel):
    # Modelo para recibir datos del formulario de login
    email: str
    contrasena: str

class Gasto(BaseModel):
    # Modelo para registrar nuevos gastos (O(1))
    usuario_id: int 
    categoria: str 
    monto: float   
    descripcion: Optional[str] = None 
    
class Presupuesto(BaseModel):
    # Modelo para el endpoint de Presupuesto (O(1))
    usuario_id: int
    monto_semanal: float
    
# -------------------------------------------------------------------
# ENDPOINTS PRINCIPALES Y LÓGICA DE NEGOCIO
# -------------------------------------------------------------------

# 1. Endpoint de Registro de Usuario (Complejidad: O(N))
@app.post("/usuarios/", status_code=201)
def registrar_usuario(nuevo_usuario: UsuarioBase):
    """
    Registra un nuevo usuario. La búsqueda de unicidad de email es O(N).
    """
    global usuario_id_counter
    
    # Búsqueda de email para unicidad (O(N) - la parte lenta si no usamos DB)
    for usuario in db_usuarios:
        if usuario['email'] == nuevo_usuario.email:
            raise HTTPException(status_code=400, detail="El email ya está registrado.")
    
    usuario_id_counter += 1
    usuario_data = nuevo_usuario.model_dump()
    usuario_data['id'] = usuario_id_counter
    
    # Guardado (O(1) - adición al final de la lista)
    db_usuarios.append(usuario_data)
    
    # Devolvemos la información pública
    usuario_registrado = {
        'id': usuario_data['id'],
        'nombre': usuario_data['nombre'],
        'email': usuario_data['email'],
        'universidad': usuario_data['universidad']
    }
    
    return {"mensaje": "Registro exitoso. Bienvenido a AhorraU", "usuario": usuario_registrado}


# 2. Endpoint de Visualización de Todos los Usuarios (PARA DEPURACIÓN)
@app.get("/usuarios/")
def get_all_usuarios():
    """
    Devuelve la lista completa de usuarios registrados (sin contraseñas).
    Usado para depurar si el registro fue exitoso.
    """
    # Usamos list comprehension para excluir la contraseña antes de enviar
    usuarios_sin_contrasena = [
        {k: v for k, v in user.items() if k != 'contrasena'}
        for user in db_usuarios
    ]
    return usuarios_sin_contrasena


# 3. Endpoint para obtener un Usuario por ID (Usado en Dashboard - Complejidad: O(N))
@app.get("/usuarios/{usuario_id}")
def get_usuario_por_id(usuario_id: int):
    """
    Busca un usuario por ID para el saludo en el Dashboard (O(N)).
    """
    for user in db_usuarios:
        if user['id'] == usuario_id:
            # Devuelve los datos sin la contraseña
            return {
                "nombre": user['nombre'], 
                "universidad": user['universidad']
            }
            
    raise HTTPException(status_code=404, detail="Usuario no encontrado")


# 4. Endpoint de Login (Complejidad: O(N))
@app.post("/login/")
def login_usuario(credenciales: LoginRequest):
    """
    Simula el inicio de sesión. La búsqueda por email es O(N).
    """
    usuario_encontrado = None
    
    # Búsqueda O(N)
    for user in db_usuarios:
        if user['email'] == credenciales.email:
            usuario_encontrado = user
            break
            
    if not usuario_encontrado:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    # Verificación de contraseña
    if usuario_encontrado['contrasena'] != credenciales.contrasena:
        raise HTTPException(status_code=401, detail="Credenciales inválidas.")

    # Éxito: devolvemos los datos del usuario
    return {
        "mensaje": "Inicio de sesión exitoso", 
        "usuario_id": usuario_encontrado['id'],
        "nombre": usuario_encontrado['nombre'],
        "universidad": usuario_encontrado['universidad']
    } 


# 5. Endpoint de Registro de Gasto (Complejidad: O(1))
@app.post("/gastos/", status_code=201)
def registrar_gasto(gasto: Gasto):
    """
    Simula el registro de un gasto. Es una operación O(1) de adición.
    """
    global gasto_id_counter
    gasto_id_counter += 1
    
    gasto_data = gasto.model_dump()
    gasto_data['gasto_id'] = gasto_id_counter
    gasto_data['timestamp'] = pd.Timestamp.now().isoformat()
    
    gastos_app.append(gasto_data)
    
    return {"mensaje": "Gasto registrado exitosamente", "gasto": gasto_data}

# 6. Endpoint de Presupuesto Semanal (Complejidad: O(1))
@app.post("/presupuesto/", status_code=201)
def set_presupuesto(presupuesto: Presupuesto):
    """
    Guarda el presupuesto semanal del usuario. O(1) por uso de diccionario.
    """
    db_presupuestos[presupuesto.usuario_id] = presupuesto.monto_semanal
    
    return {"mensaje": "Presupuesto semanal guardado", "monto": presupuesto.monto_semanal}


# 7. Endpoint para obtener todos los estudiantes del DataSet (O(1) - Acceso a la lista cargada)
@app.get("/estudiantes/")
def get_estudiantes():
    """
    Devuelve el DataSet de 1500 estudiantes (acceso O(1) a la memoria).
    """
    return data_list