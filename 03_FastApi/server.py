from fastapi import FastAPI, HTTPException
from openai import AsyncOpenAI
from pydantic import BaseModel

app = FastAPI()

client = AsyncOpenAI(
    base_url="http://127.0.0.1:1337/v1",
    api_key="no-key",
)


class Prompt(BaseModel):
    text: str
    temperature: float = 0.7


@app.get("/")
async def root():
    return {"message": "BANKAI!"}


@app.get("/users/{user_id}")
async def get_user(user_id: int):
    if user_id == 0:
        raise HTTPException(status_code=404, detail="user not found")
    return {"user_id": user_id}


@app.get("/items")
async def list_items(skip: int = 0, limit: int = 10):
    return {"skip": skip, "limit": limit}


@app.post("/ask")
async def ask(p: Prompt):
    return {"received": p.text, "temperature": p.temperature}


@app.post("/chat")
async def chat(p: Prompt):
    res = await client.chat.completions.create(
        model="gemma-4-12B-it-MLX-6bit",
        temperature=p.temperature,
        messages=[{"role": "user", "content": p.text}],
    )
    return {"answer": res.choices[0].message.content}
