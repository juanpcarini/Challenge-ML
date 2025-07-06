import os,sys
import re
from langchain_core.tools import tool 
from dotenv import load_dotenv
from typing import TypedDict
from inspect import signature
import ldap3
from langchain_google_genai import ChatGoogleGenerativeAI 

import logging


logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    logger.critical("GOOGLE_API_KEY no está configurada en el archivo .env en generate_tool_node.py")
    sys.exit(1)


model = ChatGoogleGenerativeAI(model="gemini-2.0-flash-lite", google_api_key=GOOGLE_API_KEY, temperature=0)


class AgentState(TypedDict, total=False):
    user_input: str
    tool_name: str
    tool_arg: str
    tool_generated: bool
    result: str
    new_generated_tool: tool
    generated_tool_code: str

def generate_tool_node(state: AgentState) -> AgentState:
    user_input = state.get("user_input", "")
    tool_name = state.get("tool_name", "")
    tool_arg = state.get("tool_arg", "")

    prompt = f"""
    Generá una función en Python decorada con @tool de langchain_core.tools
    para consultar un servidor LDAP y responder la siguiente necesidad del usuario:

    Consulta: "{user_input}"

    Condiciones:
    - La función debe incluir `import os`, `from dotenv import load_dotenv`, y `load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env')))` al principio para cargar las variables de entorno correctamente desde la raíz del proyecto.
    - Debe usar ldap3 (ej: ldap3.Server, ldap3.Connection) para conectarse a un servidor LDAP.
    - Debe obtener credenciales y bases DN desde variables de entorno específicas:
        - `LDAP_HOST` para el host del servidor.
        - `LDAP_BIND_DN` para el usuario de enlace (bind user).
        - `LDAP_BIND_PASSWORD` para la contraseña del usuario de enlace.
        - `LDAP_USERS_BASE_DN` para la base DN de usuarios (si busca usuarios).
        - `LDAP_GROUPS_BASE_DN` para la base DN de grupos (si busca grupos).
    - No uses `LDAP_SERVER`, `LDAP_USER`, `LDAP_PASSWORD`, `LDAP_BASE_DN`. Usa los nombres que te he especificado.
    - La función debe llamarse: {tool_name}
    - Si la herramienta necesita un argumento (por ejemplo, un uid para buscar), la función debe aceptarlo como su **único parámetro** con un nombre apropiado (ej: `uid: str`). Si no necesita argumentos, la función no debe tener parámetros.
    - No incluir explicaciones, texto adicional, o comentarios externos al código de la función.
    - Incluir un docstring.
    - Si la función interactúa con LDAP, por favor, gestiona las excepciones comunes de ldap3, como `ldap3.core.exceptions.LDAPException`.
    - La función debe importar `ldap3` al inicio de su definición si lo utiliza (ej. `import ldap3`).
    - La función debe retornar directamente el resultado (str, dict, list).

    Solo devolvé el código de la función, incluyendo cualquier importación necesaria **dentro de la función** si aplica (ej. `from dotenv import load_dotenv`).
    """

    code = "" 
    try:
        response = model.invoke(prompt)
        code_with_markdown = response.content.strip()

        code_match = re.search(r"```python\s*\n(.*?)```", code_with_markdown, re.DOTALL)

        if code_match:
            code = code_match.group(1).strip()
        else:
            code = code_with_markdown 
        


        exec_globals = {
            "os": os,
            "tool": tool, 
            "ldap3": ldap3,
            "Server": ldap3.Server,
            "Connection": ldap3.Connection,
            "ALL_ATTRIBUTES": ldap3.ALL_ATTRIBUTES, 
            "SUBTREE": ldap3.SUBTREE,
            "load_dotenv": load_dotenv,
            "ldap3_exceptions": ldap3.core.exceptions, 
            "__file__": os.path.join(os.path.dirname(__file__), 'temp_tool.py') 
        }
        local_vars = {}
        exec(code, exec_globals, local_vars)

        tool_fn = None
        for val in local_vars.values():
            if callable(val) and hasattr(val, 'name') and hasattr(val, 'description'):
                tool_fn = val
                break
        
        if tool_fn is None:
            state["result"] = "❌ Error: no se pudo detectar una función válida en el código generado."
            logger.error(f"Código generado que no produjo una herramienta válida:\n{code}")
            state["tool_generated"] = False 
            state["new_generated_tool"] = None
            state["generated_tool_code"] = code 
            return state

        sig = signature(tool_fn.func) 
        params = list(sig.parameters.keys())

        execution_result = None
        test_input_args = {}

        if params: 
            for param_name in params:
                test_input_args[param_name] = "testuser" 
            
            
            execution_result = tool_fn.invoke(test_input_args)
        else: 
            
            execution_result = tool_fn.invoke({})

        state["result"] = execution_result
        state["tool_generated"] = True
        state["new_generated_tool"] = tool_fn 
        state["generated_tool_code"] = code 
        

    except Exception as e:
        state["result"] = f"❌ Error generando o ejecutando herramienta: {str(e)}"
        logger.error(f"Error completo en generate_tool_node para '{tool_name}': {e}", exc_info=True)
        state["tool_generated"] = False 
        state["new_generated_tool"] = None
        state["generated_tool_code"] = code 
    return state
