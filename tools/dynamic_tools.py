
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
