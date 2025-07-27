from docling.chunking import HybridChunker
from docling.document_converter import DocumentConverter
from dotenv import load_dotenv
from openai import OpenAI
from utils.tokenizer import OpenAITokenizerWrapper
import json
import psycopg
from psycopg.rows import dict_row
import os
import re

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

def process_file(file_path: str, converter: DocumentConverter, chunker: HybridChunker):
    """Process a single file and return the chunks with metadata"""
    print(f"Processing file: {file_path}")
    
    try:
        result = converter.convert(file_path)
    except Exception as e:
        print(f"Error converting file {file_path}: {e}")
        return []
    
    # Apply chunking
    chunk_iter = chunker.chunk(dl_doc=result.document)
    chunks = list(chunk_iter)
    
    # Extract book name from file path as fallback
    book_name = os.path.splitext(os.path.basename(file_path))[0]
    
    # Try to get title from document metadata, fallback to filename
    try:
        document_title = result.document.meta.title if hasattr(result.document, 'meta') and hasattr(result.document.meta, 'title') else book_name
    except AttributeError:
        document_title = book_name
    
    return chunks, document_title

converter = DocumentConverter()

# --------------------------------------------------------------
# Apply hybrid chunking
# --------------------------------------------------------------

chunker = HybridChunker(
    tokenizer=tokenizer,
    max_tokens=500, # significantly smaller to encourage splitting
    merge_peers=False, # disable merging if you want strict paragraph separation
    #split_regex="\n\n+", # explicitly instructs chunker to split at paragraph breaks - IT IS NOT WORKING AT ALL!!
)

# Get all files from the converted_notes_folder
converted_notes_folder = config["converted_notes_folder"]
if not os.path.exists(converted_notes_folder):
    print(f"Error: Folder {converted_notes_folder} does not exist")
    exit(1)

# Get all files in the folder (you can filter by extension if needed)
file_list = []
for filename in os.listdir(converted_notes_folder):
    file_path = os.path.join(converted_notes_folder, filename)
    if os.path.isfile(file_path):
        # Optional: filter by file extensions
        if filename.lower().endswith(('.docx', '.pdf', '.txt', '.md')):
            file_list.append(file_path)

if not file_list:
    print(f"No supported files found in {converted_notes_folder}")
    exit(1)

print(f"Found {len(file_list)} files to process")

# Process each file
with psycopg.connect(config["postgres_dsn"], row_factory=dict_row) as conn:
    with conn.cursor() as cur:
        for file_path in file_list:
            chunks, document_title = process_file(file_path, converter, chunker)
            
            if not chunks:
                print(f"No chunks generated for {file_path}")
                continue
            
            current_headers = []  # Reset headers for each file
            chunks_processed = 0
            
            for chunk in chunks:
                # Check if chunk.text contains header pattern (starts and ends with **)
                header_match = re.match(r'^\*\*(.*)\*\*$', chunk.text.strip())
                
                if header_match:
                    # Extract header text (without **)
                    header_text = header_match.group(1)
                    
                    # Add to current_headers list
                    current_headers.append(header_text)
                    continue  # Skip to next chunk
                
                # If it's regular text and we have current_headers, save to DB
                if current_headers:
                    try:
                        # Get embedding
                        vector = embed_text(chunk.text)

                        # Convert headers list to JSON string
                        headings_json = json.dumps(current_headers)

                        # Insert into DB with current_headers as JSON
                        cur.execute(
                            """
                            INSERT INTO book_chunks (book_name, chunk_text, embedding, sent_as_letter, headings)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (
                                document_title,
                                chunk.text,
                                vector,
                                False,
                                headings_json  # Now properly formatted as JSON
                            )
                        )
                        chunks_processed += 1

                        # Clear the current_headers after saving
                        current_headers = []
                    except Exception as e:
                        print(f"Error processing chunk from {file_path}: {e}")
                else:
                    # If no current_headers, needs to handle this case
                    print(f"Skipping chunk without header from {file_path}: {chunk.text[:50]}...")
            
            print(f"Processed {chunks_processed} chunks from {document_title}")
            
        conn.commit()
        print("All files processed and committed to database")