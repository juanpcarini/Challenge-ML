import os, sys
from typing import TypedDict, Annotated, Sequence, Dict
from langgraph.graph import StateGraph, END
from langgraph.graph.message import add_messages
from langchain_core.messages import BaseMessage, HumanMessage, AIMessage
from langchain_google_genai import ChatGoogleGenerativeAI # Importar Gemini
from langchain_core.tools import tool , BaseTool, Tool
from dotenv import load_dotenv
import re, ast
from inspect import signature
import json
import ldap3

import logging 

# Configuración de logging: solo se mostrarán WARNING, ERROR y CRITICAL por defecto.
logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__) 

# Paths de importación
sys.path.append(os.path.abspath(os.path.dirname(__file__)))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools')))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Import tool generation node
from generate_tool_node import generate_tool_node 

# Import herramientas disponibles (estáticas)
from user_tools import (
    get_all_usernames_tool,
    get_user_attributes_tool,
    get_group_names_tool,
    get_current_user_info_tool,
    get_user_groups_tool,
    enumerate_group_members_tool,
    get_user_email_tool
)

# Configuración API + Entorno
load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

# Configuración para Gemini
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logger.critical("GOOGLE_API_KEY no está configurada en el archivo .env.")
    sys.exit(1)

model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", google_api_key=GOOGLE_API_KEY, temperature=0) # Usar gemini-2.0-flash-lite

# --- FUNCIÓN PARA INICIALIZAR HERRAMIENTAS ESTÁTICAS --- 
def initialize_static_tools() -> Dict[str, BaseTool]: 
    """Inicializa y devuelve el diccionario de herramientas estáticas.""" 
    return { 
        "get_all_usernames_tool": get_all_usernames_tool, 
        "get_user_attributes_tool": get_user_attributes_tool, 
        "get_group_names_tool": get_group_names_tool, 
        "get_current_user_info_tool": get_current_user_info_tool, 
        "get_user_groups_tool": get_user_groups_tool, 
        "enumerate_group_members_tool": enumerate_group_members_tool, 
        "get_user_email_tool": get_user_email_tool 
    } 

# Diccionario de herramientas (inicialmente solo estáticas)
tools_dict: Dict[str, BaseTool] = initialize_static_tools()

# --- LÓGICA DE CARGA DE HERRAMIENTAS DINÁMICAS ---
DYNAMIC_TOOLS_FILE = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'tools', 'dynamic_tools.py'))

import importlib.util
import importlib.machinery

def load_dynamic_tools():
    global tools_dict 
    
    if not os.path.exists(DYNAMIC_TOOLS_FILE):
        with open(DYNAMIC_TOOLS_FILE, 'w', encoding='utf-8') as f:
            f.write("""
# open_ldap_files/tools/dynamic_tools.py

import os
from dotenv import load_dotenv
from ldap3 import Server, Connection, ALL_ATTRIBUTES, SUBTREE
from langchain_core.tools import tool # Importante para que el @tool funcione
import ldap3.core.exceptions
import re # Necesario para parsing en herramientas generadas

load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env')))

LDAP_HOST = os.getenv("LDAP_HOST")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD")
LDAP_USERS_BASE_DN = os.getenv("LDAP_USERS_BASE_DN")
LDAP_GROUPS_BASE_DN = os.getenv("LDAP_GROUPS_BASE_DN")

# Aquí es donde se añadirán las herramientas generadas dinámicamente.
""")
        return

    try:
        spec = importlib.util.spec_from_file_location("dynamic_tools", DYNAMIC_TOOLS_FILE)
        
        if spec is None:
            logger.error(f"❌ No se pudo obtener la especificación del módulo para {DYNAMIC_TOOLS_FILE}")
            return
            
        dynamic_module = importlib.util.module_from_spec(spec)
        sys.modules["dynamic_tools"] = dynamic_module
        spec.loader.exec_module(dynamic_module)

        found_dynamic_tools = False
        for name in dir(dynamic_module):
            obj = getattr(dynamic_module, name)
            
            if callable(obj) and hasattr(obj, 'name') and hasattr(obj, 'description'):
                actual_tool_instance = obj if isinstance(obj, Tool) else Tool(name=obj.name, description=obj.description, func=obj)
                
                if actual_tool_instance.name not in tools_dict:
                    tools_dict[actual_tool_instance.name] = actual_tool_instance
                    found_dynamic_tools = True
        
    except Exception as e:
        logger.error(f"❌ Error CRÍTICO al cargar herramientas dinámicas desde {DYNAMIC_TOOLS_FILE}: {e}", exc_info=True)

# Cargar herramientas dinámicas al inicio del script
load_dynamic_tools()
# --- FIN LÓGICA DE CARGA DE HERRAMIENTAS DINÁMICAS ---


# Estado del agente
class AgentState(TypedDict, total=False):
    messages: Annotated[Sequence[BaseMessage], add_messages]
    user_input: str
    tool_name: str
    tool_arg: str
    tool_generated: bool
    result: str 
    new_generated_tool: BaseTool
    generated_tool_code: str

# --- NUEVA FUNCIÓN PARA GENERAR DESCRIPCIÓN DE TOOLS DINÁMICAMENTE ---
def get_available_tools_description() -> str:
    """Genera una descripción formateada de las herramientas disponibles en tools_dict."""
    description = ""
    tool_number = 1
    for tool_name, tool_obj in tools_dict.items():
        tool_desc = getattr(tool_obj, 'description', 'No hay descripción disponible.')
        
        params = []
        func_to_inspect = getattr(tool_obj, 'func', tool_obj) 
        if callable(func_to_inspect): 
            sig = signature(func_to_inspect)
            params = list(sig.parameters.keys())
        
        arg_req = ""
        if params:
            arg_req = f"- Requiere argumento: {', '.join(params)}"
        else:
            arg_req = "- No requiere argumentos."

        description += f"{tool_number}. {tool_name}:\n"
        description += f"- Uso: {tool_desc}\n"
        description += f"{arg_req}\n\n"
        tool_number += 1
    return description
# --- FIN NUEVA FUNCIÓN ---


# Nodo de selección
def select_tool_node(state: AgentState) -> AgentState:
    user_input = state["user_input"]
    
    current_messages = state.get("messages", [])
    current_messages.append(HumanMessage(content=user_input)) 
    
    prompt = f"""
    Eres un agente especializado en seguridad ofensiva LDAP. Tu objetivo principal es ayudarte a recopilar información y realizar tareas de reconocimiento en un servidor LDAP. 

    Las herramientas disponibles son: 
    
    {get_available_tools_description()} 

    Instrucciones clave para la selección de herramientas: 
    1.  **Si la consulta es sobre un atributo ESPECÍFICO de un usuario** (ej. 'dame el teléfono de Alice', 'cuál es el título de Bob', 'dime el departamento de un usuario'): 
        * **Prioridad 1: Busca una herramienta DEDICADA existente** para ese atributo (ej. `get_user_email_tool`). Si la encuentras, úsala. 
        * **Prioridad 2: Si NO existe una herramienta DEDICADA**, entonces **ES OBLIGATORIO generar una nueva herramienta**. 
            * **ATENCIÓN CRÍTICA: Bajo NINGUNA circunstancia uses `get_user_attributes_tool` para obtener UN atributo específico.** Esa herramienta es *solo* para obtener *todos* los atributos del usuario. 
            * La nueva herramienta debe tener un nombre descriptivo en `snake_case` (ej. `get_user_phone_number_tool`, `get_user_title_tool`). 
            * Debe aceptar un parámetro `query: str` y devolver **SOLO el valor del atributo solicitado**. 
    2.  **Si la consulta pide TODOS los atributos de un usuario** (ej. 'dame toda la info de un usuario', 'muéstrame todos los detalles de un usuario'): 
        * **DEBES usar** `get_user_attributes_tool`. 
    3.  **Si la consulta es sobre LDAP y no hay una herramienta existente que la cubra perfectamente (pero no es un atributo específico de usuario)**: 
        * **DEBES generar una nueva herramienta.** Inventa un nombre de herramienta en `snake_case` que sea muy descriptivo para la tarea. 
        * Ejemplos: `get_password_policy_tool`, `find_weak_password_users_tool`, `list_computers_tool`. 
        * La herramienta generada debe tener un único parámetro `query: str` si necesita una entrada, o ningún parámetro si es una consulta general del dominio. Debe devolver **SOLO el valor del atributo solicitado o la lista de resultados directamente**. 
    4.  **Si la consulta NO está relacionada con LDAP** (ej. un saludo, una pregunta general, etc.): 
        * Tu respuesta JSON debe ser: ` {{"tool": "ninguno", "arg": "ninguno"}} ` 

    **IMPORTANTE: Cuando selecciones una herramienta, DEBES usar su `nombre_de_tool` EXACTO, no su número de la lista.**
    **CRÍTICO: Si la herramienta requiere un argumento, el valor de 'arg' DEBE ser el valor exacto que la herramienta necesita.**

    **INSTRUCCIONES CLAVE PARA LA EXTRACCIÓN DE ARGUMENTOS (¡LEE ESTO CUIDADOSAMENTE!):**
    * Para herramientas que requieren un `uid` (como `get_user_email_tool`, `get_user_attributes_tool`, `get_user_groups_tool`), el `arg` SIEMPRE será el nombre de usuario (ej. "test.user", "alice.brown") que se encuentra en la consulta del usuario.
    * Para herramientas que requieren un `group_name` (como `enumerate_group_members_tool`), el `arg` SIEMPRE será el nombre del grupo (ej. "it", "managers", "admins") que se encuentra en la consulta del usuario.
    * Para herramientas que requieren un `field` (como `get_current_user_info_tool`), el `arg` SIEMPRE será el nombre del atributo solicitado (ej. "title", "mail", "phone") que se encuentra en la consulta del usuario.
    * **El valor de 'arg' DEBE ser solo el dato puro, sin comillas adicionales, texto explicativo, o prefijos como 'de' o 'del equipo'.**

    **EJEMPLOS DE EXTRACCIÓN DE ARGUMENTOS (¡PRECISOS Y CRÍTICOS PARA EL ÉXITO!):**
    * **Consulta:** "dame el email de test.user"
        **JSON:** ` {{"tool": "get_user_email_tool", "arg": "test.user"}} `
        *(Aquí, "test.user" es el UID exacto)*
    * **Consulta:** "cuáles son los grupos de alice.brown"
        **JSON:** ` {{"tool": "get_user_groups_tool", "arg": "alice.brown"}} `
        *(Aquí, "alice.brown" es el UID exacto)*
    * **Consulta:** "dame todos los atributos de john.doe"
        **JSON:** ` {{"tool": "get_user_attributes_tool", "arg": "john.doe"}} `
        *(Aquí, "john.doe" es el UID exacto)*
    * **Consulta:** "enumera los miembros del grupo admins"
        **JSON:** ` {{"tool": "enumerate_group_members_tool", "arg": "admins"}} `
        *(Aquí, "admins" es el nombre del grupo exacto)*
    * **Consulta:** "dame todos los usuarios del equipo it"
        **JSON:** ` {{"tool": "enumerate_group_members_tool", "arg": "it"}} `
        *(Aquí, "it" es el nombre del grupo exacto)*
    * **Consulta:** "dame el título del usuario actual"
        **JSON:** ` {{"tool": "get_current_user_info_tool", "arg": "title"}} `
        *(Aquí, "title" es el nombre del campo exacto)*
    * **Consulta:** "dame todos los usuarios"
        **JSON:** ` {{"tool": "get_all_usernames_tool", "arg": "ninguno"}} `
        *(No requiere argumento)*

    Consulta del usuario: "{user_input}" 

    Responde estrictamente en JSON: 
    {{ 
    "tool": "<nombre_de_tool>", 
    "arg": "<argumento_o_ninguno>" 
    }} 
    """ 
    response = model.invoke(prompt) 
    response_text = response.content 

    try: 
        match = re.search(r"\{(.+?)\}", response_text, re.DOTALL) 
        if match: 
            tool_info = ast.literal_eval("{" + match.group(1) + "}") 
            tool_name = tool_info.get("tool", "").strip() 
            tool_arg = tool_info.get("arg", "").strip() 

            state["tool_name"] = tool_name 
            state["tool_arg"] = tool_arg 
        else: 
            state["tool_name"] = "" 
            state["tool_arg"] = "" 
            logger.warning(f"No se pudo parsear la respuesta del LLM a JSON: {response_text}") 

        state["messages"] = current_messages 
        
    except Exception as e: 
        state["tool_name"] = "" 
        state["tool_arg"] = "" 
        logger.error(f"Error parseando la respuesta del LLM en select_tool_node: {e}", exc_info=True) 
        state["messages"] = current_messages 
        
    return state 

# Decisión condicional:
def decide_if_tool_exists(state: AgentState) -> str: 
    tool_name = state.get("tool_name", "") 
    
    if tool_name == "ninguno": 
        return "respond_to_user" 
    elif tool_name in tools_dict: 
        return "execute_tool" 
    else: 
        logger.warning(f"⚠️ La herramienta '{tool_name}' NO existe en tools_dict. Se procederá a generación.") 
        return "generate_tool" 

# Ejecución de herramienta 
def execute_tool_node(state: AgentState) -> AgentState: 
    tool_name = state.get("tool_name", "") 
    tool_arg = state.get("tool_arg", None) 
    tool_fn = tools_dict.get(tool_name) 

    current_messages = state.get("messages", [])
    user_input = state.get("user_input", "") 

    if not tool_fn:
        error_msg = f"❌ La herramienta '{tool_name}' no está registrada en el diccionario global."
        logger.error(error_msg)
        state["result"] = error_msg
        current_messages.append(AIMessage(content=error_msg)) 
        state["messages"] = current_messages
        return state

    try:
        execution_result = None
        
        sig = signature(tool_fn.func)
        params = list(sig.parameters.keys()) 

        if tool_arg and str(tool_arg).lower() != "ninguno" and tool_arg != "":
            if params: 
                
                param_name = params[0] 
                invoke_args = {param_name: tool_arg}
                execution_result = tool_fn.invoke(invoke_args)
            else: 
                logger.warning(f"La herramienta '{tool_name}' recibió el argumento '{tool_arg}' pero no espera parámetros. Invocando sin argumentos.")
                execution_result = tool_fn.invoke({}) 
        else: 
            execution_result = tool_fn.invoke({})

        state["result"] = execution_result
        
        
        format_prompt = f"""
        El usuario preguntó: "{user_input}"
        La herramienta ejecutada obtuvo el siguiente resultado:
        {execution_result}

        Por favor, formatea este resultado de una manera amigable y conversacional para el usuario.
        Si el resultado es una lista de elementos, preséntalos de forma clara y legible.
        Si es un solo valor, intégralo en una frase natural.
        Si el resultado indica que no se encontró información, informa al usuario de manera cortés.
        Sé conciso, pero informativo.
        """
        formatted_response_from_llm = model.invoke(format_prompt)
        formatted_result = formatted_response_from_llm.content

        state["messages"].append(AIMessage(content=formatted_result))

    except Exception as e: 
        error_msg = f"❌ Error ejecutando la herramienta '{tool_name}': {str(e)}" 
        state["result"] = error_msg 
        logger.error(error_msg, exc_info=True) 
        current_messages.append(AIMessage(content=error_msg)) 
        state["messages"] = current_messages 

    return state 

# Nodo de respuesta directa al usuario (cuando no se necesita herramienta) 
def respond_to_user_node(state: AgentState) -> AgentState: 
    user_input = state.get("user_input", "") 
    current_messages = state.get("messages", []) 

    prompt_for_response = f""" 
    Eres un asistente LDAP. El usuario preguntó: "{user_input}". 
    No se identificó ninguna herramienta adecuada para esta consulta. 
    Por favor, responde amablemente al usuario indicando que tu propósito es ayudar con consultas LDAP y si puede reformular su pregunta. 
    Sé conciso y directo. 
    """ 
    response_from_llm = model.invoke(prompt_for_response) 
    
    final_response = response_from_llm.content 
    state["result"] = final_response 
    current_messages.append(AIMessage(content=final_response)) 
    state["messages"] = current_messages 
    return state 

# Nuevo nodo para manejar la herramienta generada y añadirla al tools_dict global 
def handle_generated_tool(state: AgentState) -> AgentState: 
    global tools_dict 
    
    new_tool_name = state.get("tool_name") 
    tool_code = state.get("generated_tool_code", "") 
    new_generated_tool_instance = state.get("new_generated_tool") 

    if tool_code and new_generated_tool_instance: 
        try: 
            
            current_file_content = ""
            if os.path.exists(DYNAMIC_TOOLS_FILE):
                with open(DYNAMIC_TOOLS_FILE, 'r', encoding='utf-8') as f_read:
                    current_file_content = f_read.read()

            
            with open(DYNAMIC_TOOLS_FILE, 'w', encoding='utf-8') as f_write:
                if not re.search(rf"(?:^|\n)\s*@tool(?:\s*\(.*?\))?\s*\ndef\s+{re.escape(new_tool_name)}\(", current_file_content, re.MULTILINE): 
                    f_write.write(current_file_content)
                    f_write.write("\n\n") 
                    f_write.write(tool_code) 
                else: 
                    f_write.write(current_file_content)
                    logger.info(f"Tool '{new_tool_name}' already exists in dynamic_tools.py. Skipping write.") 

            
            if "dynamic_tools" in sys.modules: 
                dynamic_module = sys.modules["dynamic_tools"] 
                importlib.reload(dynamic_module) 
                logger.info(f"✅ Módulo 'dynamic_tools.py' recargado.") 
            else: 
                
                spec = importlib.util.spec_from_file_location("dynamic_tools", DYNAMIC_TOOLS_FILE) 
                if spec and spec.loader: 
                    dynamic_module = importlib.util.module_from_spec(spec) 
                    sys.modules["dynamic_tools"] = dynamic_module 
                    spec.loader.exec_module(dynamic_module) 
                    logger.info(f"✅ Módulo 'dynamic_tools.py' cargado por primera vez.") 
                else: 
                    logger.error(f"❌ No se pudo cargar el módulo 'dynamic_tools.py' después de la generación.") 
                    return state 

            
            found_reloaded_tool = False 
            for name in dir(dynamic_module): 
                obj = getattr(dynamic_module, name) 
                if callable(obj) and hasattr(obj, 'name') and hasattr(obj, 'description'): 
                    actual_tool_instance = obj if isinstance(obj, Tool) else Tool(name=obj.name, description=obj.description, func=obj) 
                    if actual_tool_instance.name == new_tool_name: 
                        tools_dict[actual_tool_instance.name] = actual_tool_instance 
                        logger.info(f"✅ Herramienta dinámica '{actual_tool_instance.name}' añadida al diccionario global después de recarga.") 
                        found_reloaded_tool = True 
                        break 

            if not found_reloaded_tool: 
                logger.error(f"❌ La herramienta '{new_tool_name}' no se encontró en el módulo recargado.") 

        except Exception as e: 
            logger.error(f"❌ Error al persistir o recargar el código de la herramienta en {DYNAMIC_TOOLS_FILE}: {e}", exc_info=True) 
    
    return state 

# Grafo 
graph = StateGraph(AgentState) 

graph.add_node("select_tool", select_tool_node) 
graph.add_conditional_edges( 
    "select_tool", 
    decide_if_tool_exists, 
    { 
        "execute_tool": "execute_tool", 
        "generate_tool": "generate_tool", 
        "respond_to_user": "respond_to_user_node" 
    } 
) 

graph.add_node("execute_tool", execute_tool_node) 
graph.add_node("generate_tool", generate_tool_node) 
graph.add_node("handle_generated_tool", handle_generated_tool) 
graph.add_node("respond_to_user_node", respond_to_user_node) 

graph.add_edge("execute_tool", END) 
graph.add_edge("respond_to_user_node", END) 

graph.add_edge("generate_tool", "handle_generated_tool") 
graph.add_edge("handle_generated_tool", "select_tool") 

graph.set_entry_point("select_tool") 


app = graph.compile() 

if __name__ == "__main__": 
    logging.getLogger().setLevel(logging.CRITICAL) 

    print("Bienvenido al Agente de Seguridad Ofensiva LDAP.") 
    print("Escribe 'salir' para terminar.") 
    while True: 
        print("\n--- Menú Principal ---") 
        print("1. Realizar consulta LDAP") 
        print("2. Ver herramientas disponibles") 
        print("3. Resetear herramientas dinámicas")
        print("4. Salir") 
        
        choice = input("Elige una opción: ") 
        
        if choice == '1': 
            user_input = input("🧠 ¿Consulta LDAP?: ") 
            if user_input.lower() == 'salir': 
                print("👋 ¡Hasta luego!") 
                break 
            
            initial_messages = [HumanMessage(content=user_input)] 
            
            inputs = { 
                "user_input": user_input, 
                "tool_generated": False, 
                "result": "", 
                "messages": initial_messages, 
                "available_tools": tools_dict 
            } 
            
            final_state = app.invoke(inputs) 

            display_content = None
            for message in reversed(final_state.get("messages", [])):
                if isinstance(message, AIMessage):
                    display_content = message.content
                    break
            
            if display_content:
                print(f"Agente: {display_content}")
            else:
                result = final_state.get("result")
                if isinstance(result, str):
                    print(f"Agente: {result}")
                elif isinstance(result, list) or isinstance(result, dict):
                    print(json.dumps(result, indent=2, ensure_ascii=False))
                else:
                    print(f"Agente: No se pudo obtener una respuesta final clara. Estado de resultado: {final_state.get('result', 'N/A')}")

        elif choice == '2': 
            print("\n--- Herramientas Disponibles ---") 
            
            logging.getLogger().setLevel(logging.WARNING) 
            print(get_available_tools_description()) 
            logging.getLogger().setLevel(logging.CRITICAL)
            print("---------------------------------") 
        
        elif choice == '3': 
            print("\n--- Reseteando Herramientas Dinámicas ---") 
            
            try:
                from reset_dynamic_tools import reset_dynamic_tools_file
            except ImportError:
                
                sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
                from reset_dynamic_tools import reset_dynamic_tools_file
                
            reset_dynamic_tools_file() 

            tools_dict = {
                "get_all_usernames_tool": get_all_usernames_tool,
                "get_user_attributes_tool": get_user_attributes_tool,
                "get_group_names_tool": get_group_names_tool,
                "get_current_user_info_tool": get_current_user_info_tool,
                "get_user_groups_tool": get_user_groups_tool,
                "enumerate_group_members_tool": enumerate_group_members_tool,
                "get_user_email_tool": get_user_email_tool
            }
            load_dynamic_tools()
            print("✅ Reseteo completado. Las herramientas dinámicas han sido reiniciadas.") 
            print("\n--- ¡Importante: Reinicia tu agente para un reseteo completo! ---") 
            print("Para que los cambios surtan efecto y tu agente cargue solo las herramientas iniciales:") 

            print("------------------------------------------------------------------") 

        elif choice == '4': 
            print("👋 ¡Hasta luego!") 
            break 
        
        else: 
            print("Opción no válida. Por favor, elige un número del 1 al 4.")
