import os
import shutil 


DYNAMIC_TOOLS_FILE = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    'tools', 
    'dynamic_tools.py'
))


DYNAMIC_TOOLS_CACHE_DIR = os.path.abspath(os.path.join(
    os.path.dirname(__file__),
    'tools',
    '__pycache__'
))

def reset_dynamic_tools_file():
    """
    Reinicia el archivo 'dynamic_tools.py', borrando su contenido
    y escribiendo el encabezado inicial necesario. También elimina
    la carpeta '__pycache__' asociada para asegurar una recarga limpia.
    """
    tools_dir = os.path.dirname(DYNAMIC_TOOLS_FILE)
    if not os.path.exists(tools_dir):
        os.makedirs(tools_dir)
        print(f"Directorio de herramientas creado: '{tools_dir}'")

    
    try:
        with open(DYNAMIC_TOOLS_FILE, 'w', encoding='utf-8') as f: 
            f.write("""
import os
from dotenv import load_dotenv
from ldap3 import Server, Connection, ALL_ATTRIBUTES, SUBTREE
from langchain_core.tools import tool, Tool 
import ldap3.core.exceptions 
import re 

# Cargar variables de entorno
load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '.env')))

LDAP_HOST = os.getenv("LDAP_HOST")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD")
LDAP_USERS_BASE_DN = os.getenv("LDAP_USERS_BASE_DN")
LDAP_GROUPS_BASE_DN = os.getenv("LDAP_GROUPS_BASE_DN")

# Aca se agregan las herramientas generadas dinamicamente.
""")
        print(f"✨ Archivo 'dynamic_tools.py' reseteado a su estado inicial.")
    except Exception as e:
        print(f"❌ Error al resetear 'dynamic_tools.py': {e}")

  
    if os.path.exists(DYNAMIC_TOOLS_CACHE_DIR):
        try:
            shutil.rmtree(DYNAMIC_TOOLS_CACHE_DIR)
            print(f"🗑️ Caché de herramientas dinámicas eliminada.")
        except OSError as e:
            print(f"⚠️ No se pudo eliminar la caché de herramientas dinámicas: {e}")

if __name__ == "__main__":
    print("\n--- Iniciando Reseteo de Herramientas Dinámicas ---")
    reset_dynamic_tools_file()
    print("--- Reseteo de Herramientas Dinámicas Completado ---")
    print("\nPara que los cambios surtan efecto en tu agente, asegúrate de reiniciar 'agent_graph.py'.")

