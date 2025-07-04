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

def pick_random_note(notes_folder):
    notes = [f for f in os.listdir(notes_folder) if f.endswith('.docx')]
    if not notes:
        raise Exception("No notes available!")
    return random.choice(notes)

def get_note_content(filepath, char_limit=4000):
    doc = docx.Document(filepath)
    full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip() != ""])
    return full_text[:char_limit]

def extract_book_name(filename):
    base = os.path.splitext(filename)[0]
    base = re.sub(r'\[.*?\]', '', base)
    base = base.replace('_', ' ').strip()
    return base

def classify_coach(note_content):
    classification_prompt = f"""
    Classify the following note into one of the categories: "parenting", "investing", "diet", or "general_self_improvement".
    Respond only with the category name.

    Note Content:
    "{note_content[:2000]}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": classification_prompt}],
        max_tokens=3,
        temperature=0.0
    )
    category = response.choices[0].message.content.strip().lower()
    return category

def generate_letter(note_content,config):
    personal = config["personal_details"]
    prompt = f"""
    You are a thoughtful personal coach. Using the provided excerpts, write an inspiring, personalized letter.

    Personal details:
    "{personal}".

    Letter should contain:
    1. Warm greeting addressing me as 'Dear Mykhailo,'.
    2. Insightful inspirational thoughts.
    3. Practical habit suggestions.
    4. Recommend one book or movie.

    Excerpts:
    "{note_content}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.9
    )
    return response.choices[0].message.content.strip()

def generate_parenting_letter(note_content, config):
    family = config["family_details"]
    prompt = f"""
    You are a compassionate parenting coach.

    Family context:
    "{family}".

    Letter:
    1. Warm greeting 'Dear Mykhailo,'.
    2. Encouraging parenting advice.
    3. Stress management tips.
    4. Positive parenting techniques.
    5. Recommend parenting book/movie.

    Excerpts:
    "{note_content}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.9
    )
    return response.choices[0].message.content.strip()

def generate_investing_letter(note_content, config):
    portfolio = pd.read_csv(os.path.expanduser(config["portfolio_csv"]))
    with open(os.path.expanduser(config["investment_strategy_txt"])) as file:
        strategy = file.read()

    prompt = f"""
    You are a wise financial advisor.

    Investment Strategy:
    "{strategy}"

    Portfolio:
    "{portfolio.to_string(index=False)}"

    Letter:
    1. Greeting 'Dear Mykhailo,'.
    2. Portfolio-strategy alignment.
    3. Adjustment recommendations.
    4. Inspirational investor quotes.

    Excerpts:
    "{note_content}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.8
    )
    return response.choices[0].message.content.strip()

def generate_diet_letter(note_content, config):
    health = config["health_info"]
    prompt = f"""
    You are a supportive nutrition coach.

    Personal health details:
    "{health}".

    Letter:
    1. Greeting 'Dear Mykhailo,'.
    2. Nutritional insights.
    3. Practical diet suggestions.
    4. Recommendations for better sleep and GERD management.
    5. Recommend relevant nutrition book/movie.

    Excerpts:
    "{note_content}"
    """
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.8
    )
    return response.choices[0].message.content.strip()

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

    coach_type = classify_coach(content)

    if coach_type == "parenting":
        letter = generate_parenting_letter(content, config)
    elif coach_type == "investing":
        letter = generate_investing_letter(content, config)
    elif coach_type == "diet":
        letter = generate_diet_letter(content, config)
    else:
        letter = generate_letter(content, config)

    send_email(letter, book_name, recipient_email)
