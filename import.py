from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from dotenv import load_dotenv
from openai import OpenAI
from utils.tokenizer import OpenAITokenizerWrapper
import json
import psycopg
from psycopg.rows import dict_row
import os


load_dotenv()

with open('config.json') as f:
    config = json.load(f)

client = OpenAI(api_key=config["openai_api_key"])


tokenizer = OpenAITokenizerWrapper()  # Load our custom tokenizer for OpenAI
MAX_TOKENS = 8191  # text-embedding-3-large's maximum context length - do not using now cause it leads to big arbitrary chunks


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
    max_tokens=500, # significantly smaller to encourage splitting
    merge_peers=False, # disable merging if you want strict paragraph separation
    split_regex="\n\n+", # explicitly instructs chunker to split at paragraph breaks - IT IS NOT WORKING AT ALL!!
)

chunk_iter = chunker.chunk(dl_doc=result.document)
chunks = list(chunk_iter)


# Extract book name from file path as fallback
book_name = os.path.splitext(os.path.basename(file_path))[0]

# Try to get title from document metadata, fallback to filename
try:
    document_title = result.document.meta.title if hasattr(result.document, 'meta') and hasattr(result.document.meta, 'title') else book_name
except AttributeError:
    document_title = book_name

with psycopg.connect(config["postgres_dsn"], row_factory=dict_row) as conn:
    with conn.cursor() as cur:
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
                    document_title,  # Use the extracted title or filename
                    chunk.text,
                    vector,
                    False,
                    json.dumps(chunk.meta.headings)
                )
            )
        conn.commit()