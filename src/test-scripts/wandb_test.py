import os
import weave
from ollama import ChatResponse, Client


weave.init(os.getenv("PROJECT_NAME", ""))


@weave.op
def create_completion(message: str) -> ChatResponse:
    client = Client(host=os.getenv("OLLAMA_HOST"))
    response = client.chat(
        model="deepseek-r1:8b",
        messages=[
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": message},
        ],
    )
    return response


message = "Tell me a joke."
create_completion(message)
