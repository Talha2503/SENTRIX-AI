import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from pydantic import BaseModel  # noqa: E402

from app.core.config import settings  # noqa: E402
from app.core.llm import call_json  # noqa: E402


class Ping(BaseModel):
    ok: bool
    message: str


print(f"Model: {settings.GROQ_MODEL}")
result = call_json("You are a test assistant.", "Return ok=true and message='SENTRIX online'.", Ping)
print(result)