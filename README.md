# **Agente Conversacional para Operaciones LDAP**

Este proyecto implementa un **agente conversacional avanzado** diseñado para asistir en la gestión y análisis de información en servidores LDAP. Utiliza un modelo de lenguaje grande (LLM) para interpretar las consultas del usuario, seleccionar o generar dinámicamente herramientas de consulta LDAP, ejecutarlas y presentar los resultados de manera amigable.

## **Características Principales**

* **Interacción Conversacional:** Comuníquese con el agente en lenguaje natural para realizar consultas LDAP complejas.  
* **Selección Inteligente de Herramientas:** El agente es capaz de identificar la herramienta LDAP más adecuada para su consulta entre un conjunto predefinido.  
* **Generación Dinámica de Herramientas:** Si una herramienta específica no existe para una necesidad particular (por ejemplo, para obtener un atributo muy específico de un usuario), el agente puede generar una nueva herramienta Python sobre la marcha, añadirla a su repertorio y usarla.  
* **Recopilación y Gestión de Información LDAP:**  
  * Listado de todos los usuarios y grupos.  
  * Obtención de todos los atributos de un usuario específico.  
  * Enumeración de miembros de grupos.  
  * **Funcionalidad de Correo Electrónico:** Permite obtener la dirección de correo electrónico de un usuario específico directamente desde LDAP.  
  * Recuperación de información del usuario actual (la cuenta de enlace LDAP).  
* **Persistencia de Herramientas:** Las herramientas generadas dinámicamente se guardan y están disponibles para futuras interacciones.

## **Flujo Operativo del Agente**

El presente agente opera mediante una arquitectura estructurada basada en un **grafo de estados**. Este diseño permite un procesamiento sistemático de las consultas, asegurando una gestión eficiente y precisa de las operaciones LDAP. Cada interacción sigue un flujo de decisiones lógicas claramente definido.

A continuación, se detalla el proceso operativo del agente:

1. Recepción y Análisis de la Consulta:  
   El proceso se inicia con la recepción de la consulta del usuario (user\_input), la cual se integra al historial conversacional. Un Modelo de Lenguaje Grande (LLM) se encarga de analizar el texto para determinar la intención subyacente. Este análisis no se limita a la identificación de palabras clave, sino que abarca la comprensión contextual y la extracción de datos específicos relevantes, como un identificador de usuario (uid), el nombre de un grupo (group\_name), o un atributo particular.  
2. Evaluación de Herramientas: Existente o Requerimiento de Generación:  
   Basándose en el análisis inicial de la consulta, el LLM evalúa las herramientas LDAP disponibles en su repertorio.  
   * **Si la consulta se alinea con una herramienta existente** (por ejemplo, una solicitud de correo electrónico para un usuario específico que puede ser manejada por get\_user\_email\_tool), dicha herramienta es seleccionada para su ejecución.  
   * **Si la consulta es altamente específica** y no existe una herramienta dedicada para su resolución (por ejemplo, la solicitud de un atributo poco común), el agente determina la necesidad de **generar una nueva herramienta**. Esta capacidad es un pilar fundamental del diseño, ya que elimina la dependencia de un conjunto estático de funcionalidades predefinidas.  
   * **En caso de que la consulta no esté relacionada con operaciones LDAP**, el agente lo identifica y responde adecuadamente, informando al usuario sobre su ámbito de especialización.  
3. Generación de Nuevas Herramientas (según demanda):  
   Cuando se requiere una nueva herramienta, el LLM recibe un conjunto de especificaciones detalladas: el nombre de la función, su propósito y las condiciones para su desarrollo (incluyendo la interacción con el servidor LDAP, el uso de variables de entorno específicas, el manejo de argumentos y el tipo de retorno esperado). El LLM procede a generar el código Python de la herramienta. Tras su creación, se realiza una validación interna para asegurar su correcto funcionamiento, y la herramienta es integrada permanentemente al conjunto de capacidades del agente, quedando disponible para interacciones futuras.  
4. Ejecución Precisa de la Herramienta Seleccionada:  
   Una vez identificada o generada la herramienta, el agente procede a su invocación. Un aspecto crítico en esta fase es la gestión precisa de los argumentos. El agente inspecciona la firma de la función de la herramienta para determinar los parámetros exactos que requiere (ej., uid, group\_name). Posteriormente, extrae el dato relevante de la consulta original del usuario y lo pasa a la herramienta con la clave de parámetro correcta. Este mecanismo asegura que la herramienta reciba los insumos exactos para su ejecución, minimizando errores de validación.  
5. Transformación y Presentación de Resultados:  
   Una vez que la herramienta ha completado su operación y ha obtenido el resultado (que puede presentarse en formatos técnicos como JSON o listas de Nombres Distinguidos), el agente no lo expone directamente. En su lugar, el LLM es nuevamente utilizado para formatear esta información. El objetivo es transformar los datos técnicos en una respuesta conversacional, clara y de fácil comprensión para el usuario. Esto implica presentar listas de elementos de manera legible o integrar valores individuales en frases naturales, garantizando que la información sea digerible y útil.

Este ciclo continuo de análisis, decisión, ejecución y comunicación es lo que confiere a este Agente Conversacional para Operaciones LDAP su robustez y adaptabilidad, convirtiéndolo en un recurso valioso para la gestión y análisis en entornos LDAP.

## **Requisitos**

* Python 3.9+  
* Poetry (para gestión de dependencias)  
* Acceso a un servidor LDAP (se incluye una configuración básica con Docker Compose para pruebas).  
* Una clave API de Google Gemini (para el modelo gemini-2.0-flash-lite).

## **Configuración y Ejecución**

1. **Clona este repositorio:**  
   git clone https://github.com/juanpcarini/Challenge-ML.git

   cd Challenge-ML/open\_ldap\_files

2. Configura las variables de entorno:  
   Crea un archivo .env en la raíz del proyecto (open\_ldap\_files/) con tus credenciales LDAP y la clave API de Google.  
   \# .env  
   LDAP\_HOST="your\_ldap\_host"  
   LDAP\_BIND\_DN="cn=admin,dc=example,dc=org"  
   LDAP\_BIND\_PASSWORD="admin\_password"  
   LDAP\_USERS\_BASE\_DN="ou=users,dc=example,dc=org"  
   LDAP\_GROUPS\_BASE\_DN="ou=groups,dc=example,dc=org"  
   GOOGLE\_API\_KEY="your\_google\_api\_key"

   *(Asegúrate de reemplazar los valores con tu configuración LDAP real y tu clave API de Google).*  
3. **Instala las dependencias con Poetry:**  
   poetry install

4. Inicia el servidor LDAP (opcional, para pruebas):  
   Si deseas un entorno LDAP local para pruebas, puedes usar Docker Compose:  
   docker-compose \-f docker-compose-meli-challenge.yml up \-d

   Luego, puedes poblarlo con los datos de ejemplo:  
   ./setup-ldap.sh

5. **Ejecuta el agente:**  
   poetry run python agent/agent\_graph.py

## **Ejemplos de Uso**

Una vez que el agente esté corriendo, puedes interactuar con él:

* dame los grupos  
* dame los usuarios  
* quien soy  
* dame el email de test.user  
* dame los atributos de alice.brown  
* dame todos los usuarios del equipo it  
* dame el número de teléfono de john.doe (Esto debería generar una nueva herramienta si no existe).


### **Reflexiones y Agradecimiento**

Extiendo un sincero agradecimiento por la oportunidad de participar en este desafiante proyecto. La flexibilidad para abordarlo a mi propio ritmo fue un factor crucial que me permitió sumergirme por completo en cada etapa del desarrollo. Esta libertad me brindó el espacio para experimentar, investigar y, en última instancia, tomar decisiones de diseño y arquitectura que considero fundamentales para la robustez y escalabilidad del agente.

Particularmente, la implementación de la **generación dinámica de herramientas** y la **gestión inteligente de argumentos** fueron áreas donde pude explorar soluciones creativas y aprender significativamente. Cada obstáculo se convirtió en una oportunidad para profundizar en la lógica de los LLM y la interacción con sistemas externos como LDAP.

Realmente disfruté cada momento de este proceso, desde la conceptualización hasta la depuración final. Ha sido una experiencia enriquecedora que ha consolidado mi comprensión de los agentes conversacionales y las **operaciones LDAP**. ¡Gracias por esta valiosa oportunidad\!
