import os
import random
import docx
import json
import re
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI

# Load configuration
with open("config.json") as f:
    config = json.load(f)

client = OpenAI(api_key=config["openai_api_key"])

# Pick a random note
def pick_random_note(notes_folder):
    notes = [f for f in os.listdir(notes_folder) if f.endswith('.docx')]
    if not notes:
        raise Exception("No notes available!")
    return random.choice(notes)

# Read note content
def get_note_content(filepath, char_limit=4000):
    doc = docx.Document(filepath)
    full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip() != ""])
    return full_text[:char_limit]

# Extract book name for subject line
def extract_book_name(filename):
    base = os.path.splitext(filename)[0]
    base = re.sub(r'\[.*?\]', '', base)
    base = base.replace('_', ' ').strip()
    return base

# Rich letter generators
def generate_parenting_letter(note_excerpt, config):
    family = config["family_details"]
    prompt = f"""
    You are a compassionate parenting coach. Using the provided excerpts, write an inspiring, personalized letter.

    Family context:
    "{family}".

    Letter:
    1. Warm greeting: 'Dear Mykhailo,'.
    2. Encouraging parenting advice.
    3. Stress management tips.
    4. Positive parenting techniques.
    5. Recommendation of a parenting book or movie.

    Excerpts:
    "{note_excerpt}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.9
    )
    return response.choices[0].message.content.strip()

def generate_investing_letter(note_excerpt, config):
    portfolio = pd.read_csv(os.path.expanduser(config["portfolio_csv"]))
    with open(os.path.expanduser(config["investment_strategy_txt"])) as file:
        strategy = file.read()

    prompt = f"""
    You are a wise financial advisor. Using the provided excerpts, write an thoughtful, personalized letter

    Investment Strategy:
    "{strategy}"

    Portfolio:
    "{portfolio.to_string(index=False)}"

    Letter:
    1. Greeting: 'Dear Mykhailo,'.
    2. How the portfolio aligns with the strategy.
    3. Recommendations for adjustment to portfolio and strategy.
    4. Inspirational investor quotes.

    Excerpts:
    "{note_excerpt}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.8
    )
    return response.choices[0].message.content.strip()

def generate_diet_letter(note_excerpt, config):
    health = config["health_info"]
    prompt = f"""
    You are a supportive nutrition coach. Using the provided excerpts and health details, write an inspiring, personalized letter.

    Personal health details:
    "{health}".

    Letter:
    1. Greeting: 'Dear Mykhailo,'.
    2. Nutritional insights and ideas for improving your health.
    3. Practical diet suggestions.
    4. Recommendation of a relevant book or movie.

    Excerpts:
    "{note_excerpt}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.8
    )
    return response.choices[0].message.content.strip()

def generate_general_letter(note_excerpt, config):
    personal = config["personal_details"]
    prompt = f"""
    You are a thoughtful personal coach. Using the provided excerpts and personal details, write an inspiring, personalized letter.

    Personal details:
    "{personal}".

    Letter:
    1. Warm greeting: 'Dear Mykhailo,'.
    2. Insightful inspirational thoughts.
    3. Practical habit suggestions.
    4. Recommendation of a book or movie.

    Excerpts:
    "{note_excerpt}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.9
    )
    return response.choices[0].message.content.strip()

# Send email
def send_email(letter, subject, recipient_email):
    msg = MIMEText(letter)
    msg['Subject'] = subject
    msg['From'] = config["email"]["from"]
    msg['To'] = recipient_email

    with smtplib.SMTP(config["email"]["smtp_server"], config["email"]["smtp_port"]) as server:
        server.starttls()
        server.login(config["email"]["from"], config["email"]["password"])
        server.sendmail(msg['From'], [recipient_email], msg.as_string())

if __name__ == "__main__":
    notes_folder = config["notes_folder"]
    recipient_email = config["recipient_email"]

    note = pick_random_note(notes_folder)
    content = get_note_content(os.path.join(notes_folder, note))
    book_name = extract_book_name(note)

    # Define GPT tools
    tools = [
        {"type": "function", "function": {"name": "generate_parenting_letter", "description": "Generate a parenting coaching letter.", "parameters": {"type": "object", "properties": {"note_excerpt": {"type": "string"}}, "required": ["note_excerpt"]}}},
        {"type": "function", "function": {"name": "generate_investing_letter", "description": "Generate an investing coaching letter.", "parameters": {"type": "object", "properties": {"note_excerpt": {"type": "string"}}, "required": ["note_excerpt"]}}},
        {"type": "function", "function": {"name": "generate_diet_letter", "description": "Generate a diet coaching letter.", "parameters": {"type": "object", "properties": {"note_excerpt": {"type": "string"}}, "required": ["note_excerpt"]}}},
        {"type": "function", "function": {"name": "generate_general_letter", "description": "Generate a general self-improvement letter.", "parameters": {"type": "object", "properties": {"note_excerpt": {"type": "string"}}, "required": ["note_excerpt"]}}},
    ]

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful coach. Choose the appropriate coaching letter type based on the note excerpt."},
            {"role": "user", "content": content}
        ],
        tools=tools,
        tool_choice="auto",
        temperature=0.0
    )

    tool_call = response.choices[0].message.tool_calls[0]
    tool_name = tool_call.function.name
    args = json.loads(tool_call.function.arguments)

    # Map tools to Python functions
    tool_map = {
        "generate_parenting_letter": generate_parenting_letter,
        "generate_investing_letter": generate_investing_letter,
        "generate_diet_letter": generate_diet_letter,
        "generate_general_letter": generate_general_letter
    }

    letter = tool_map[tool_name](args["note_excerpt"], config)

    send_email(letter, book_name, recipient_email)
