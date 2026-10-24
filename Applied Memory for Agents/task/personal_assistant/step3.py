from openai import OpenAI
import os
import json
import dotenv
from tinydb import TinyDB, Query
from enum import Enum
import re
import ssl
import httpx
import truststore

dotenv.load_dotenv()

# Contexto seguro con los certificados de Windows, solo para este cliente
# (no modifica el módulo ssl del proceso del evaluador)
contexto_ssl = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

CLIENT = OpenAI(
    base_url=os.getenv("OPENAI_BASE_URL"),
    api_key=os.getenv("OPENAI_API_KEY"),
    http_client=httpx.Client(verify=contexto_ssl),
    max_retries=6,
    timeout=60,
)

INSTRUCCIONES = """You are a personal task assistant.
Always use the tools to create, find and update tasks. Never answer about existing tasks from memory: query them with find_task.
Valid statuses are exactly: to-do, in-progress, done.
Map whatever the user writes to a valid status WITHOUT asking for confirmation:
- 'todo', 'to do', 'pending' -> 'to-do'
- 'in_progress', 'in progress', 'inprogress', 'started', 'doing' -> 'in-progress'
- 'completed', 'finished', 'complete' -> 'done'
If no status is given for a new task, use 'to-do'.
When the user says they started or finished a task, update its status.
Answer briefly and always mention task names exactly as stored."""

class ContextManager:
    def __init__(self):
        self.messages: list[dict] = []
        
    def add_user_message(self, message: str):
        self.messages.append({
            "role": "user", "content": message
        })
    
    def update_messages(self, messages: list[dict]):
        self.messages = messages
        
    def get_repr(self):
        """Function for showing context for easier solving of optional tasks"""
        msgs = []
        for elem in self.messages:
            if type(elem) is dict:
                if 'role' in elem:
                    msgs.append(elem['role'] + ': ' + elem['content'][:15] + '...')
                else:
                    msgs.append(elem['type'] + ': ' + elem['output'][:15] + '...')
            else:
                msgs.append(str(elem.type))
        return 'Context:\n\t' + "\n\t".join(msgs) + '\n-------'
    
    def get_context(self) -> list[dict]:
        return self.messages.copy()

    def compact(self):
        """
        OPTIONAL TASK
        
        If you use get_repr() function after each call to LLM, 
        you will see that context is getting bigger and bigger. Not only with messages, but also with function calls and their outputs. 
        
        Your task is to implement compact() function to remove all non-message items from context.
        """
        pass
    
    def reset(self):
        self.messages = []
        
class MatchType(Enum):
    EQ = "eq"
    CONTAINS = "contains"
    
  
class TasksStore:
    VALID_STATUSES = ("to-do", "in-progress", "done")

    def __init__(self):
        self.db = TinyDB('tasks.json')

    def create_task(self, name: str, status: str) -> str:
        status = self._normalizar_estado(status)
        if status not in self.VALID_STATUSES:
            return f"Invalid status '{status}'. Valid statuses: {', '.join(self.VALID_STATUSES)}"
        self.db.insert({"name": name, "status": status})
        return f"Task '{name}' created with status '{status}'"

    def find_task(self, key: str, value: str, match: MatchType = MatchType.EQ) -> str:
        if key == "status":
            value = self._normalizar_estado(value)

        # El LLM manda el texto "eq" / "contains"; el valor por defecto es el Enum.
        # Por eso normalizo a string comparando contra .value
        match_value = match.value if isinstance(match, MatchType) else match

        Task = Query()
        if match_value == MatchType.EQ.value:
            results = self.db.search(Task[key] == value)
        elif match_value == MatchType.CONTAINS.value:
            results = self.db.search(
                Task[key].test(lambda v: re.search(value, str(v), re.IGNORECASE) is not None)
            )
        else:
            return f"Invalid match type '{match_value}'. Use 'eq' or 'contains'"

        if not results:
            return f"No tasks found where {key} {match_value} '{value}'"
        lines = [f"- {t['name']} (status: {t['status']})" for t in results]
        return "Tasks found:\n" + "\n".join(lines)

    def update_task_status(self, name: str, new_status: str) -> str:
        new_status = self._normalizar_estado(new_status)
        if new_status not in self.VALID_STATUSES:
            return f"Invalid status '{new_status}'. Valid statuses: {', '.join(self.VALID_STATUSES)}"
        updated = self.db.update({"status": new_status}, Query().name == name)
        if not updated:
            return f"Task '{name}' not found"
        return f"Task '{name}' status updated to '{new_status}'"

    def _normalizar_estado(self, estado: str) -> str:
        """Convierte variantes como 'in_progress', 'in progress' o 'todo' al formato válido"""
        e = estado.strip().lower().replace("_", "-").replace(" ", "-")
        equivalencias = {"todo": "to-do", "inprogress": "in-progress"}
        return equivalencias.get(e, e)

    def flush(self):
        self.db.truncate()
    
    
class PersonalAssistant:
    def __init__(self):
        """
        TODO: fill tools list with correct tool descriptions. Match tool names to function names. And tool parameters to function parameters.
        
        As a hint, check how tool_result is obtained during tool call phase.
        """
        self.tools = [
            {
                "type": "function",
                "name": "find_task",
                "description": "Search tasks by a field. Use key='status' to list tasks by status "
                               "(to-do, in-progress, done) or key='name' to look up a task by its name. "
                               "Use match='contains' for partial/pattern matches.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "key": {"type": "string", "enum": ["name", "status"],
                                "description": "Field to search by"},
                        "value": {"type": "string", "description": "Value or pattern to look for"},
                        "match": {"type": "string", "enum": ["eq", "contains"],
                                  "description": "'eq' for exact match, 'contains' for pattern match"},
                    },
                    "required": ["key", "value"],
                },
            },
            {
                "type": "function",
                "name": "create_task",
                "description": "Create a new task with a name and an initial status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Name of the task"},
                        "status": {"type": "string", "enum": ["to-do", "in-progress", "done"],
                                   "description": "Initial status. Use 'to-do' for new tasks unless told otherwise"},
                    },
                    "required": ["name", "status"],
                },
            },
            {
                "type": "function",
                "name": "update_task_status",
                "description": "Change the status of an existing task, identified by its exact name.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Exact name of the task to update"},
                        "new_status": {"type": "string", "enum": ["to-do", "in-progress", "done"],
                                       "description": "New status of the task"},
                    },
                    "required": ["name", "new_status"],
                },
            },
        ]
        # to store data
        self.tasks_store = TasksStore()
        
        self.tool_map = {
            "find_task": self.tasks_store.find_task,
            "create_task": self.tasks_store.create_task,
            "update_task_status": self.tasks_store.update_task_status
        }
        # to manage context
        self.context_manager = ContextManager()
        
    def send_message(self, message: str) -> str:
        self.context_manager.add_user_message(message)
        context = self.context_manager.get_context()
        context = self._call_llm(context)
        self.context_manager.update_messages(context)
        return context[-1].content[0].text

    def _call_llm(self, messages: list[dict]) -> list[dict]:
        response = CLIENT.responses.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            instructions=INSTRUCCIONES,
            input=messages,
            tools=self.tools
        )
        messages += response.output

        function_calls = [item for item in response.output if item.type == "function_call"]

        # THOUGHT terminó sin pedir herramientas: respuesta final
        if not function_calls:
            return messages

        # ACT + OBSERVE
        for item in function_calls:
            tool_result = self.tool_map[item.name](**json.loads(item.arguments))
            messages.append({
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": str(tool_result),
            })

        # Volvemos a THOUGHT: el LLM tiene que ver los resultados y redactar la respuesta
        return self._call_llm(messages)
    
    def flush(self):
        self.tasks_store.flush()
        self.context_manager.reset()
        

def main():
    """Main conversation loop"""
    assistant = PersonalAssistant()
    while True:
        try:
            user_input = input("User: ").strip()
            if not user_input:
                continue
            
            # Process special commands
            if user_input == "/q":
                break
            elif user_input == "/flush":
                assistant.flush()
                print("[INFO] Flushed")
                continue
            
            # Process normal message
            response = assistant.send_message(user_input)
            print(f"Assistant: {response}")
        except KeyboardInterrupt:
            print("\nGoodbye!")
            break


if __name__ == "__main__":
    main()
