<img src="https://github.com/user-attachments/assets/0923a764-c4da-4a30-853f-e2f7cbe06779" alt="Tiger Social" width="200">

# tiger-social
A Discord social bot for answering questions with relevance and attribution

## Inspiration
RAG technology sparked an idea: a Discord bot that could not only answer questions but also attribute knowledge to its original authors. This concept aims to recognize community contributions while efficiently addressing repeated queries.

## What it does
Tiger Social enhances Discord communities by:

- Efficiently answering repeated questions
- Utilizing the community's collective knowledge
- Providing proper attribution for sourced information

## How we built it
Our development process involved:

1. Creating a Discord Python Bot
2. Integrating OpenAI's LLM
3. Implementing Jina AI for embeddings
4. Utilizing TiDB for vector database storage
5. Using raw SQL for data and vector storage

## Challenges we ran into
- Adapting to Jina AI embeddings when prototyping with Claude
- Navigating TiDB's beta vector database capabilities
- Resolving issues with the Llama-Index TiDB plugin

## Accomplishments that we're proud of
- Successfully integrating TiDB and OpenAI function calling
- Implementing vector embeddings for the first time
- Completing the project despite technical hurdles

## What we learned
- Gained experience with vector embeddings
- Explored TiDB's features, including HTAP capabilities
- Enhanced problem-solving skills through troubleshooting

## What's next for Tiger Social
Future plans include:

- Implementing support for replies and threads
- Developing a dashboard for question analytics
- Expanding attribution features to include analytics
- This revised version maintains the essence of your project while presenting the information in a more balanced and professional tone. It highlights your achievements and learning experiences without overstating them, and presents challenges as opportunities for growth.




## Python Prerequisites
```
$ pip install pymysql python-dotenv openai requests discord.py
```
## Cloud Prerequisites
- TiDB Cloud account - Create a serverless DB
- Open AI account - get Open AI API Key
- Go to Jina.ai - get API Key (no login required)

## Create relevant Tables
Create relevant tables. Add `use yourDB;` in the SQL playground of TiDB
```
CREATE TABLE messages (
    id INT AUTO_INCREMENT PRIMARY KEY,
    author_name VARCHAR(255) NOT NULL,
    author_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    link VARCHAR(512) NOT NULL,
    embedding VECTOR(768) NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE interactions (
    id INT AUTO_INCREMENT PRIMARY KEY,
    author_name VARCHAR(255) NOT NULL,
    author_id VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

## Set these variables into .env file before running 
```
DISCORD_TOKEN = ""

OPENAI_API_KEY = ""

JINA_API_KEY = ""

TIDB_HOST = ""
TIDB_PORT = ""
TIDB_USER = ""
TIDB_PASSWORD = ""
TIDB_DATABASE = ""
```
