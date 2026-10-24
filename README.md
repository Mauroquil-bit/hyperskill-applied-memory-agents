# Asistente personal de tareas con memoria

Proyecto final del curso **Applied Memory for Agents** de Hyperskill.

Es un asistente que se maneja escribiéndole en lenguaje natural. Le pedís que anote una tarea, que la marque como empezada o terminada, o que te diga qué tenés pendiente, y él se encarga. Las tareas quedan guardadas en un archivo, así que no se pierden al cerrar el programa.

## Ejemplo de uso

```
User: hey, create task "do laundry"
Assistant: The task "do laundry" has been created and is marked as to-do.

User: I just started to do laundry
Assistant: The task "do laundry" is now marked as in-progress.

User: what are tasks in progress?
Assistant: The task in progress is "do laundry."
```

El asistente responde en inglés porque las pruebas del curso están en inglés.

## Cómo funciona

### La idea principal

El modelo de lenguaje **no toca la base de datos directamente**. Tiene a su disposición tres herramientas y decide solo cuándo usar cada una, según lo que le pidas:

| Herramienta | Para qué sirve |
|---|---|
| `create_task` | Crear una tarea nueva con un nombre y un estado. |
| `find_task` | Buscar tareas por nombre o por estado. |
| `update_task_status` | Cambiar el estado de una tarea que ya existe. |

Cada tarea tiene uno de estos tres estados: `to-do` (pendiente), `in-progress` (en curso) o `done` (terminada).

### El bucle Pensar → Actuar → Observar

Cada vez que le escribís algo, el asistente repite este ciclo hasta tener una respuesta:

1. **Pensar:** el modelo lee toda la conversación y decide si alcanza con contestar o si necesita usar una herramienta.
2. **Actuar:** si pide una herramienta, el programa la ejecuta. El modelo nunca ejecuta nada: solo indica qué función usar y con qué datos.
3. **Observar:** el resultado se agrega a la conversación y se vuelve al paso 1, para que el modelo vea qué pasó.

Cuando el modelo contesta con texto en lugar de pedir una herramienta, el ciclo termina y se muestra la respuesta.

### Las piezas del programa

- **`TasksStore`:** guarda las tareas en `tasks.json` usando TinyDB, una base de datos muy simple que trabaja sobre un archivo de texto.
- **`ContextManager`:** lleva el historial de la conversación, que es la "memoria de corto plazo" del asistente.
- **`PersonalAssistant`:** une todo. Tiene la lista de herramientas, las instrucciones para el modelo y el bucle descripto arriba.

Además, el programa acepta variantes al escribir los estados (`todo`, `in_progress`, `in progress`) y las convierte al formato correcto.

## Qué necesitás

- Python 3.11 o más nuevo.
- Una clave de API de [Groq](https://console.groq.com) (tiene plan gratuito) o de OpenAI.

## Cómo instalarlo

1. Cloná el repositorio y entrá a la carpeta:

   ```bash
   git clone https://github.com/Mauroquil-bit/hyperskill-applied-memory-agents.git
   cd hyperskill-applied-memory-agents
   ```

2. Creá un entorno virtual e instalá las dependencias:

   ```bash
   python -m venv venv
   venv\Scripts\activate        # en Windows
   source venv/bin/activate     # en Linux o Mac
   pip install -r requirements.txt
   ```

3. Creá un archivo llamado `.env` dentro de `Applied Memory for Agents/task/personal_assistant/` con este contenido, poniendo tu clave:

   ```
   OPENAI_API_KEY=tu_clave_aca
   OPENAI_BASE_URL=https://api.groq.com/openai/v1
   OPENAI_MODEL=openai/gpt-oss-20b
   ```

   El `.env` **nunca se sube a GitHub**: está excluido en el `.gitignore` porque contiene tu clave.

   Si preferís usar OpenAI en lugar de Groq, borrá la línea de `OPENAI_BASE_URL` y poné `OPENAI_MODEL=gpt-4o-mini`.

## Cómo usarlo

```bash
cd "Applied Memory for Agents/task/personal_assistant"
python step3.py
```

Además de hablarle normalmente, hay dos comandos especiales:

| Comando | Qué hace |
|---|---|
| `/flush` | Borra todas las tareas y la conversación. |
| `/q` | Sale del programa. |

## Problemas que aparecieron y cómo se resolvieron

Algunas cosas que no estaban en el enunciado, pero que hubo que resolver para que funcionara:

- **Certificados en redes corporativas.** En redes que inspeccionan el tráfico seguro, Python rechaza la conexión porque no reconoce el certificado de la empresa. Se resolvió con la librería `truststore`, que hace que Python use los certificados de Windows, aplicada solo al cliente del modelo.
- **El evaluador corre todo en el mismo proceso.** Las pruebas de Hyperskill ejecutan el programa muchas veces sin reiniciar Python. Por eso no conviene modificar módulos globales: cualquier cambio se acumula de una prueba a la otra.
- **Modelos chicos y formatos de estado.** El modelo a veces frenaba a pedir confirmación cuando el usuario escribía `in_progress` en vez de `in-progress`. Se resolvió con instrucciones claras para el modelo y normalizando el estado en el código.

## Enlaces

- Proyecto en Hyperskill: https://hyperskill.org/projects/554
- Mi perfil en Hyperskill: https://hyperskill.org/profile/415935286
