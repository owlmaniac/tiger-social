import os
import discord
import openai
from dotenv import load_dotenv
import requests
import json
import ssl
from tidb_vector.integrations import TiDBVectorClient
from llama_index import VectorStoreIndex, SimpleDirectoryReader, Document
from llama_index.vector_stores import TiDBVectorStore
from llama_index.embeddings import JinaEmbeddings
import urllib.parse

# Load environment variables from .env file
load_dotenv()

# Load required Tokens
DISCORD_TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
JINA_API_KEY = os.getenv('JINA_API_KEY')

# TiDB connection details
TIDB_HOST = os.getenv('TIDB_HOST')
TIDB_PORT = int(os.getenv('TIDB_PORT'))
TIDB_USER = os.getenv('TIDB_USER')
TIDB_PASSWORD = os.getenv('TIDB_PASSWORD')
TIDB_DATABASE = os.getenv('TIDB_DATABASE')

# Construct the connection string
TIDB_CONNECTION_STRING = f"mysql+pymysql://{urllib.parse.quote_plus(TIDB_USER)}:{urllib.parse.quote_plus(TIDB_PASSWORD)}@{TIDB_HOST}:{TIDB_PORT}/{TIDB_DATABASE}"

# Add SSL parameters
ssl_params = {
    "ssl": {
        "ssl_verify_cert": True,
        "ssl_verify_identity": True
    }
}
TIDB_CONNECTION_STRING += "?" + "&".join(f"{k}={v}" for k, v in ssl_params["ssl"].items())

# Set up OpenAI API key
openai.api_key = OPENAI_API_KEY

# Create a new bot instance with default intents
intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

# Initialize TiDBVectorClient
vector_store = TiDBVectorClient(
    table_name='embedded_messages',
    connection_string=TIDB_CONNECTION_STRING,
    vector_dimension=768,  # Jina.ai generates vectors with 768 dimensions
    drop_existing_table=False,  # Set to True if you want to recreate the table
)

# Initialize JinaEmbeddings
embed_model = JinaEmbeddings(api_key=JINA_API_KEY)

# Initialize TiDBVectorStore for LlamaIndex
tidb_vector_store = TiDBVectorStore(vector_store)

# Initialize VectorStoreIndex
index = VectorStoreIndex.from_vector_store(tidb_vector_store)

def save_to_kb(message):
    try:
        # Generate embedding using Jina.ai
        embedding = embed_model.embed_query(message.content)
        
        # Save to TiDB Vector Store
        vector_store.insert(
            ids=[str(message.id)],
            texts=[message.content],
            embeddings=[embedding],
            metadatas=[{
                'guild_id': str(message.guild.id),
                'channel_id': str(message.channel.id),
                'author_id': str(message.author.id),
                'author_name': str(message.author.name),
            }]
        )
        print("Message saved to TiDB Vector Store successfully")
    except Exception as error:
        print(f"Error saving to TiDB Vector Store: {error}")

def query_kb(query):
    try:
        # Use LlamaIndex to query the vector store
        query_engine = index.as_query_engine()
        response = query_engine.query(query)
        
        # Process the response
        results = response.source_nodes
        formatted_response = "Top relevant messages:\n\n"
        for i, node in enumerate(results[:5], 1):
            metadata = node.metadata
            message_link = f"https://discord.com/channels/{metadata['guild_id']}/{metadata['channel_id']}/{node.id}"
            author_mention = f"<@{metadata['author_id']}>"
            formatted_response += f"{i}. Author: {author_mention}\nContent: {node.text}\nLink: {message_link}\n\n"
        
        return formatted_response
    except Exception as error:
        return f"Error querying knowledge base: {error}"

@client.event
async def on_ready():
    print(f'{client.user} has connected to Discord!')

@client.event
async def on_message(message):
    if message.author == client.user:
        return
    
    print(f"Guild ID: {message.guild.id}")
    print(f"Channel ID: {message.channel.id}")
    print(f"Message ID: {message.id}")
    print(f"Channel: {message.channel}")
    print(f"Author: {message.author} (ID: {message.author.id})")
    print(f"Content: {message.content}")
    print("--------------------")

    if client.user.mentioned_in(message):
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
        save_to_kb(message)

# Run the bot
client.run(DISCORD_TOKEN)