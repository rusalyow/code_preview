from pyrogram import Client, filters
import asyncio
from openai import OpenAI
import httpx
import json
import time

def remake_text(prompt):
    client = OpenAI(
        api_key="*",
        http_client=httpx.Client(
            proxies="http://***:***@***:62980"),
    )
    assistant_id = 'asst_***'
    thread_id = 'thread_***'

    message = client.beta.threads.messages.create(
        thread_id=thread_id,
        role="user",
        content=prompt
    )

    run = client.beta.threads.runs.create(
        thread_id=thread_id,
        assistant_id=assistant_id,
    )

    while run.status in ['queued', 'in_progress', 'cancelling']:
        time.sleep(1) 
        run = client.beta.threads.runs.retrieve(
            thread_id=thread_id,
            run_id=run.id
        )

    if run.status == 'completed':
        messages = client.beta.threads.messages.list(
            thread_id=thread_id
        )
        print(messages.data[0].content[0].text.value)
        return messages.data[0].content[0].text.value

session = '***'
app = Client("my_account", session_string=session)
@app.on_message(filters.chat('rian_ru') | filters.chat('tass_agency'))
def log(client, message):
    try:
        print(message.text)
        new_post = remake_text(message.text)
        app.send_message('@neuro_demo', new_post)
    except:
        print(message.caption)
        new_post = remake_text(message.caption)
        app.send_message('@neuro_demo', new_post)

app.run()

