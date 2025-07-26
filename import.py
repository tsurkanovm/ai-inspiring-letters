from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from dotenv import load_dotenv
from openai import OpenAI
from utils.tokenizer import OpenAITokenizerWrapper
import json
import psycopg
from psycopg.rows import dict_row


load_dotenv()

with open('config.json') as f:
    config = json.load(f)

client = OpenAI(api_key=config["openai_api_key"])


tokenizer = OpenAITokenizerWrapper()  # Load our custom tokenizer for OpenAI
MAX_TOKENS = 8191  # text-embedding-3-large's maximum context length


# --------------------------------------------------------------
# Extract the data
# --------------------------------------------------------------

def embed_text(text: str) -> list[float]:
    resp = client.embeddings.create(
        input=text,
        model="text-embedding-3-large"
    )
    return resp.data[0].embedding


converter = DocumentConverter()
file_path = config["notes_folder"] + '/Essentialism.docx'
print(file_path)
result = converter.convert(file_path)


# --------------------------------------------------------------
# Apply hybrid chunking
# --------------------------------------------------------------

chunker = HybridChunker(
    tokenizer=tokenizer,
    max_tokens=MAX_TOKENS,
    merge_peers=True,
)
#print(chunker.model_dump())
chunk_iter = chunker.chunk(dl_doc=result.document)
chunks = list(chunk_iter)
#print(chunks)
#len(chunks)
for chunk in chunks:
    print(f"Text - {chunk.text[:100]}…")
    print(f"Headings - {chunk.meta.headings}")

    # Get embedding
    vector = embed_text(chunk.text)

    # Insert into DB
    cur.execute(
        """
        INSERT INTO book_chunks (book_name, chunk_text, embedding, sent_as_letter, headings)
        VALUES (%s, %s, %s, %s, %s)
        """,
        (
            result.meta.title,  # or extract from file name
            chunk.text,
            vector,
            False,
            json.dumps(chunk.meta.headings)
        )
    )
conn.commit()
cur.close()
conn.close()