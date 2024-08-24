import os
import discord
import openai
from dotenv import load_dotenv
import requests
import pymysql
import json
import ssl

# Load environment variables from .env file
load_dotenv()

# Load required Tokens
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
JINA_API_KEY = os.getenv('JINA_API_KEY')
TIDB_HOST = os.getenv('TIDB_HOST')
TIDB_PORT = int(os.getenv('TIDB_PORT'))
TIDB_USER = os.getenv('TIDB_USER')
TIDB_PASSWORD = os.getenv('TIDB_PASSWORD')
TIDB_DATABASE = os.getenv('TIDB_DATABASE')

# Create a new bot instance with default intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Function to get database connection
def get_db_connection():
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
    
    return pymysql.connect(
        host=TIDB_HOST,
        port=TIDB_PORT,
        user=TIDB_USER,
        password=TIDB_PASSWORD,
        database=TIDB_DATABASE,
        cursorclass=pymysql.cursors.DictCursor,
        ssl=ssl_context,
        ssl_verify_cert=True
    )

# Function to generate embedding
def generate_embedding(message_content):
    url = 'https://api.jina.ai/v1/embeddings'
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {JINA_API_KEY}'
    }
    data = {
        "model": "jina-embeddings-v2-base-en",
        "input": [message_content]
    }
    response = requests.post(url, headers=headers, data=json.dumps(data))
    if response.status_code == 200:
        print("Done generating Embeddings")
        embedding_data = response.json()
        return embedding_data['data'][0]['embedding']
    else:
        print(f"Error generating embedding: {response.text}")
        return None

# Function to save message data to TiDB Knowledge Base
def save_to_kb(message, embedding):
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = """
            INSERT INTO messages (author_name, author_id, content, link, embedding)
            VALUES (%s, %s, %s, %s, %s)
            """
            message_link = f"https://discord.com/channels/{message.guild.id}/{message.channel.id}/{message.id}"
            values = (
                str(message.author.name),
                str(message.author.id),
                message.content,
                message_link,
                json.dumps(embedding)
            )
            cursor.execute(query, values)
        connection.commit()
        print("Message saved to database successfully")
    except pymysql.Error as error:
        print(f"Error saving to database: {error}")
    finally:
        if connection:
            connection.close()

# Function to save interaction data
def save_interaction(message):
    connection = None
    try:
        connection = get_db_connection()
        with connection.cursor() as cursor:
            query = """
            INSERT INTO interactions (author_name, author_id, content)
            VALUES (%s, %s, %s)
            """
            values = (
                str(message.author.name),
                str(message.author.id),
                message.content
            )
            cursor.execute(query, values)
        connection.commit()
        print("Interaction saved to database successfully")
    except pymysql.Error as error:
        print(f"Error saving interaction to database: {error}")
    finally:
        if connection:
            connection.close()

# Updated function to query the knowledge base using TiDB's vector search
def query_kb(query):
    connection = None
    try:
        connection = get_db_connection()
        query_embedding = generate_embedding(query)
        
        if not query_embedding:
            return "Failed to generate embedding for the query."

        with connection.cursor() as cursor:
            vector_query = """
            SELECT *, vec_cosine_distance(embedding, %s) AS distance
            FROM messages
            ORDER BY distance
            LIMIT 5
            """
            cursor.execute(vector_query, (json.dumps(query_embedding),))
            results = cursor.fetchall()

        response = "Top 5 most relevant messages:\n\n"
        for i, message in enumerate(results, 1):
            author_mention = f"<@{message['author_id']}>"
            response += f"{i}. (Similarity: {1 - message['distance']:.2f}) Author: {author_mention}\nContent: {message['content']}\nLink: {message['link']}\n\n"

        return response

    except pymysql.Error as error:
        return f"Error querying database: {error}"
    finally:
        if connection:
            connection.close()

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    print(f"Author: {message.author} (ID: {message.author.id})")
    print(f"Content: {message.content}")
    print("--------------------")

    if client.user.mentioned_in(message):
        save_interaction(message)
        
        content = message.content.replace(f'<@!{client.user.id}>', '').strip()

        try:
            response = openai.chat.completions.create(
                model="gpt-4",
                messages=[
                    {"role": "system", "content": "You are a Discord Bot called Tiger Social. You're a helpful assistant which chats with users in the discord app. Always use the query_kb function to retrieve relevant information before answering questions. After answering, provide the link to the most relevant message from the knowledge base and mention the original author."},
                    {"role": "user", "content": content}
                ],
                tools=[
                    {
                        "type": "function",
                        "function": {
                            "name": "query_kb",
                            "description": "Query the knowledge base for relevant information",
                            "parameters": {
                                "type": "object",
                                "properties": {
                                    "query": {
                                        "type": "string",
                                        "description": "The query to search for in the knowledge base"
                                    }
                                },
                                "required": ["query"]
                            }
                        }
                    }
                ],
                tool_choice="auto"
            )

            if response.choices[0].message.tool_calls:
                function_call = response.choices[0].message.tool_calls[0].function
                kb_results = query_kb(json.loads(function_call.arguments)['query'])

                final_response = openai.chat.completions.create(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a Discord Bot called Tiger Social. You're a helpful assistant which chats with users in the discord app. Use the information from the knowledge base to answer the user's question. After your answer, on a new line, provide the link to the most relevant message from the knowledge base and mention the original author."},
                        {"role": "user", "content": content},
                        {"role": "function", "name": "query_kb", "content": kb_results},
                        {"role": "assistant", "content": "Based on the information from the knowledge base, I'll now answer the user's question and provide a link to the most relevant message, mentioning the original author."}
                    ]
                )

                ai_response = final_response.choices[0].message.content
            else:
                ai_response = response.choices[0].message.content

            await message.channel.send(ai_response)

        except Exception as e:
            print(f"Error in OpenAI API call: {e}")
            await message.channel.send("I'm sorry, I couldn't process that request")
    else:
        embedding = generate_embedding(message.content)
        if embedding:
            save_to_kb(message, embedding)
        else:
            print("Failed to generate embedding. Message not saved to database")

# Run the bot
client.run(DISCORD_TOKEN)
