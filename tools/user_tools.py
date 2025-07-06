import os,re
from dotenv import load_dotenv
from ldap3 import Server, Connection, ALL, SUBTREE,ALL_ATTRIBUTES
from langchain_core.tools import tool
import ldap3.core.exceptions
import json
import logging


logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)


load_dotenv(dotenv_path=os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '.env')))

LDAP_HOST = os.getenv("LDAP_HOST")
LDAP_BIND_DN = os.getenv("LDAP_BIND_DN")
LDAP_BIND_PASSWORD = os.getenv("LDAP_BIND_PASSWORD")
LDAP_USERS_BASE_DN = os.getenv("LDAP_USERS_BASE_DN")
LDAP_GROUPS_BASE_DN = os.getenv("LDAP_GROUPS_BASE_DN")


@tool
def get_all_usernames_tool() -> list[str] | dict:
    """Devuelve los uid (nombres de usuario) de todos los usuarios del dominio."""
    server = None
    conn = None
    try:
        server = Server(LDAP_HOST, use_ssl=True, get_info=ALL_ATTRIBUTES)
        conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PASSWORD, auto_bind=True)

        if not conn.bound:
            logger.error(f"Error: No se pudo realizar el bind para get_all_usernames_tool. DN: {LDAP_BIND_DN}.")
            return {"error": f"No se pudo realizar el bind para get_all_usernames_tool."}

        conn.search(
            search_base=LDAP_USERS_BASE_DN,
            search_filter='(objectClass=inetOrgPerson)',
            search_scope=SUBTREE,
            attributes=['uid']
        )
        
        usernames = []
        for entry in conn.entries:
            if 'uid' in entry and entry.uid.value:
                value = entry.uid.value
                if isinstance(value, bytes):
                    try:
                        usernames.append(value.decode('utf-8'))
                    except UnicodeDecodeError:
                        usernames.append(str(value))
                else:
                    usernames.append(value)

        if usernames:
            return usernames
        else:
            return {"error": "No se encontraron nombres de usuario."}
            
    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        return {"error": f"Error de conexión LDAP para get_all_usernames_tool: {e}"}
    except ldap3.core.exceptions.LDAPBindError as e:
        return {"error": f"Error de autenticación LDAP para get_all_usernames_tool: {e}"}
    except Exception as e:
        logger.error(f"Error inesperado en get_all_usernames_tool: {e}", exc_info=True)
        return {"error": f"Ocurrió un error inesperado al obtener nombres de usuario: {e}"}
    finally:
        if conn and conn.bound:
            conn.unbind()


@tool
def get_user_attributes_tool(uid: str) -> dict:
    """Dado un uid, devuelve todos los atributos disponibles de ese usuario."""
    if not all([LDAP_HOST, LDAP_BIND_DN, LDAP_BIND_PASSWORD, LDAP_USERS_BASE_DN]):
        logger.error("Error: Variables de entorno LDAP no completamente configuradas para get_user_attributes_tool.")
        return {"error": "Variables de entorno LDAP no completamente configuradas."}

    server = None
    conn = None
    try:
        server = Server(LDAP_HOST, use_ssl=True, get_info=ALL_ATTRIBUTES) 
        conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PASSWORD, auto_bind=True)

        if not conn.bound:
            logger.error(f"Error: No se pudo realizar el bind para el usuario '{LDAP_BIND_DN}' con las credenciales proporcionadas.")
            return {"error": f"No se pudo realizar el bind para el usuario '{LDAP_BIND_DN}'."}

        conn.search(
            search_base=LDAP_USERS_BASE_DN,
            search_filter=f'(uid={uid})',
            search_scope=SUBTREE,
            attributes=['*']
        )

        if conn.entries:
            user_attributes = {}
            for entry in conn.entries:
                if hasattr(entry, 'entry_attributes'):
                    for attr in entry.entry_attributes:
                        value = entry[attr].value
                        if isinstance(value, bytes):
                            try:
                                user_attributes[attr] = value.decode('utf-8')
                            except UnicodeDecodeError:
                                user_attributes[attr] = str(value)
                        elif isinstance(value, list):
                            processed_list = []
                            for item in value:
                                if isinstance(item, bytes):
                                    try:
                                        processed_list.append(item.decode('utf-8'))
                                    except UnicodeDecodeError:
                                        processed_list.append(str(item))
                                else:
                                    processed_list.append(item)
                            user_attributes[attr] = processed_list
                        else:
                            user_attributes[attr] = value
                else:
                    logger.warning(f"La entrada LDAP para '{uid}' no tiene la propiedad 'entry_attributes'.")
                    return {"error": f"La entrada LDAP para '{uid}' no tiene la propiedad 'entry_attributes'. Revisa la estructura del objeto LDAP."}
                break 
            
            return user_attributes
        else:
            return {"error": f"No user found with uid: {uid}"}
            
    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        error_msg = f"Error de conexión LDAP para get_user_attributes_tool: {e}"
        logger.error(error_msg)
        return {"error": error_msg}
    except ldap3.core.exceptions.LDAPBindError as e:
        error_msg = f"Error de autenticación LDAP para get_user_attributes_tool: {e}"
        logger.error(error_msg)
        return {"error": error_msg}
    except Exception as e:
        logger.error(f"Ocurrió un error inesperado en get_user_attributes_tool para {uid}: {e}", exc_info=True)
        return {"error": f"Ocurrió un error inesperado al obtener atributos del usuario {uid}: {e}"}
    finally:
        if conn and conn.bound:
            conn.unbind()
            


@tool
def get_group_names_tool() -> list[str] | dict:
    """Devuelve los nombres (cn) de todos los grupos del dominio."""
    server = None
    conn = None
    try:
        server = Server(LDAP_HOST, use_ssl=True, get_info=ALL_ATTRIBUTES)
        conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PASSWORD, auto_bind=True)

        if not conn.bound:
            logger.error(f"Error: No se pudo realizar el bind para get_group_names_tool. DN: {LDAP_BIND_DN}.")
            return {"error": f"No se pudo realizar el bind para get_group_names_tool."}

        conn.search(
            search_base=LDAP_GROUPS_BASE_DN,
            search_filter='(objectClass=groupOfNames)',
            search_scope=SUBTREE,
            attributes=['cn']
        )
        
        group_names = [entry.cn.value for entry in conn.entries if 'cn' in entry]
        if group_names:
            return group_names
        else:
            return {"error": "No se encontraron nombres de grupo."}

    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        return {"error": f"Error de conexión LDAP para get_group_names_tool: {e}"}
    except ldap3.core.exceptions.LDAPBindError as e:
        return {"error": f"Error de autenticación LDAP para get_group_names_tool: {e}"}
    except Exception as e:
        logger.error(f"Error inesperado en get_group_names_tool: {e}", exc_info=True)
        return {"error": f"Ocurrió un error inesperado al obtener nombres de grupo: {e}"}
    finally:
        if conn and conn.bound:
            conn.unbind()


@tool
def get_current_user_info_tool(field: str | None = None) -> dict | str | list | int:
    """
    Recupera los atributos para el usuario actual (la cuenta utilizada para vincularse a LDAP).
    Si se proporciona 'field', devuelve solo el valor de ese atributo específico (ej., 'mail', 'gidNumber').
    De lo contrario, devuelve todos los atributos como un diccionario.
    """
    if not all([LDAP_HOST, LDAP_BIND_DN]): 
        error_msg = "Error: Las variables de entorno LDAP_HOST o LDAP_BIND_DN no están configuradas para get_current_user_info_tool."
        logger.error(error_msg)
        return {"error": error_msg}

    try:
        
        parts = LDAP_BIND_DN.split(',')
        if not parts or '=' not in parts[0]:
            error_msg = f"Error: LDAP_BIND_DN '{LDAP_BIND_DN}' no tiene un formato parseable (ej. 'attr=value,...')."
            logger.error(error_msg)
            return {"error": error_msg}
            
        _ , simple_username = parts[0].split('=', 1)


        user_info = get_user_attributes_tool(simple_username) 
        
        if "error" in user_info:
            logger.error(f"get_user_attributes_tool no pudo obtener la información completa para el usuario '{simple_username}': {user_info['error']}")
            return user_info

        
        if field:
            if field in user_info:
                
                return user_info[field]
            else:
                error_msg = f"Atributo '{field}' no encontrado para el usuario actual."
                logger.warning(error_msg)
                return {"error": error_msg}
        else:
            
            return user_info

    except Exception as e:
        error_msg = f"Ocurrió un error inesperado en get_current_user_info_tool al procesar el usuario actual: {e}"
        logger.error(error_msg, exc_info=True)
        return {"error": error_msg}
    
@tool
def get_user_groups_tool(uid: str) -> list[str] | dict:
    """
    Dado un uid (nombre de usuario), devuelve los nombres de los grupos a los que pertenece ese usuario.
    """
    server = None
    conn = None
    try:
        server = Server(LDAP_HOST, use_ssl=True, get_info=ALL_ATTRIBUTES)
        conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PASSWORD, auto_bind=True)

        if not conn.bound:
            logger.error(f"Error: No se pudo realizar el bind para get_user_groups_tool. DN: {LDAP_BIND_DN}.")
            return {"error": f"No se pudo realizar el bind para get_user_groups_tool."}

        
        conn.search(
            search_base=LDAP_USERS_BASE_DN,
            search_filter=f'(uid={uid})',
            search_scope=SUBTREE,
            attributes=[] 
        )
        
        if not conn.entries:
            return {"error": f"User with uid '{uid}' not found."}
        
        user_dn = conn.entries[0].entry_dn 

        
        conn.search(
            search_base=LDAP_GROUPS_BASE_DN,
            search_filter=f'(member={user_dn})',
            search_scope=SUBTREE,
            attributes=['cn']
        )
        
        if conn.entries:
            return [entry.cn.value for entry in conn.entries if 'cn' in entry]
        else:
            return []
    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        return {"error": f"Error de conexión LDAP para get_user_groups_tool: {e}"}
    except ldap3.core.exceptions.LDAPBindError as e:
        return {"error": f"Error de autenticación LDAP para get_user_groups_tool: {e}"}
    except Exception as e:
        logger.error(f"Error inesperado en get_user_groups_tool: {e}", exc_info=True)
        return {"error": f"Ocurrió un error inesperado al obtener grupos del usuario {uid}: {e}"}
    finally:
        if conn and conn.bound:
            conn.unbind()


@tool
def enumerate_group_members_tool(group_name: str) -> list[str] | dict:
    """
    Dado el nombre común (cn) de un grupo, devuelve una lista de los DNs de sus miembros.
    Útil para identificar usuarios dentro de grupos específicos, especialmente grupos privilegiados.
    """
    server = None
    conn = None
    try:
        server = Server(LDAP_HOST, use_ssl=True, get_info=ALL_ATTRIBUTES)
        conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PASSWORD, auto_bind=True)

        if not conn.bound:
            logger.error(f"Error: No se pudo realizar el bind para enumerate_group_members_tool. DN: {LDAP_BIND_DN}.")
            return {"error": f"No se pudo realizar el bind para enumerate_group_members_tool."}

        conn.search(
            search_base=LDAP_GROUPS_BASE_DN,
            search_filter=f'(&(objectClass=groupOfNames)(cn={group_name}))',
            search_scope=SUBTREE,
            attributes=['member']
        )

        if conn.entries and 'member' in conn.entries[0]:
            members = conn.entries[0].member.values
            return [str(member) for member in members]
        else:
            return {"error": f"Group '{group_name}' not found or has no members."}
    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        return {"error": f"Error de conexión LDAP para enumerate_group_members_tool: {e}"}
    except ldap3.core.exceptions.LDAPBindError as e:
        return {"error": f"Error de autenticación LDAP para enumerate_group_members_tool: {e}"}
    except Exception as e:
        logger.error(f"Error inesperado en enumerate_group_members_tool: {e}", exc_info=True)
        return {"error": f"Ocurrió un error inesperado al enumerar miembros del grupo {group_name}: {e}"}
    finally:
        if conn and conn.bound:
            conn.unbind()


@tool
def get_user_email_tool(uid: str) -> str | dict:
    """
    Dado un uid (nombre de usuario), devuelve la dirección de correo electrónico del usuario.
    """
    server = None
    conn = None
    try:
        server = Server(LDAP_HOST, use_ssl=True, get_info=ALL_ATTRIBUTES)
        conn = Connection(server, user=LDAP_BIND_DN, password=LDAP_BIND_PASSWORD, auto_bind=True)

        if not conn.bound:
            logger.error(f"Error: No se pudo realizar el bind para get_user_email_tool. DN: {LDAP_BIND_DN}.")
            return {"error": f"No se pudo realizar el bind para get_user_email_tool."}

        conn.search(
            search_base=LDAP_USERS_BASE_DN,
            search_filter=f'(uid={uid})',
            search_scope=SUBTREE,
            attributes=['mail']
        )

        if conn.entries and 'mail' in conn.entries[0]:
            return conn.entries[0].mail.value
        else:
            return {"error": f"User '{uid}' not found or has no email address."}
    except ldap3.core.exceptions.LDAPSocketOpenError as e:
        return {"error": f"Error de conexión LDAP para get_user_email_tool: {e}"}
    except ldap3.core.exceptions.LDAPBindError as e:
        return {"error": f"Error de autenticación LDAP para get_user_email_tool: {e}"}
    except Exception as e:
        logger.error(f"Error inesperado en get_user_email_tool: {e}", exc_info=True)
        return {"error": f"Ocurrió un error inesperado al obtener el correo del usuario {uid}: {e}"}
    finally:
        if conn and conn.bound:
            conn.unbind()
