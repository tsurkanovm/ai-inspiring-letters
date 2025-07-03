import os
import random
import docx
from openai import OpenAI
import smtplib
from email.mime.text import MIMEText
import json

# Load configuration
with open("config.json") as f:
    config = json.load(f)

client = OpenAI(api_key=config["openai_api_key"])


# Randomly pick a note
def pick_random_note(notes_folder):
    notes = [f for f in os.listdir(notes_folder) if f.endswith('.docx')]
    if not notes:
        raise Exception("No notes available!")
    return random.choice(notes)


# Extract content (limited to ~4000 characters for better responses)
def get_note_content(filepath, char_limit=4000):
    doc = docx.Document(filepath)
    full_text = "\n".join([p.text for p in doc.paragraphs if p.text.strip() != ""])
    return full_text[:char_limit]


# Generate unique letter by varying the prompt slightly
def generate_letter(note_content):
    prompt = f"""
    You are a thoughtful personal coach. Using the provided excerpts, write an inspiring, personalized letter to encourage self-improvement. Your response must always be unique and creatively presented.

    Letter should contain:
    1. Warm greeting.
    2. Insightful inspirational thoughts from provided content.
    3. Practical habit suggestions for life improvement.
    4. Recommend one book or movie related to these themes.

    Excerpts:
    "{note_content}"

    Provide a fresh perspective each time.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
        max_tokens=700,
        temperature=0.9  # High creativity to avoid repetition
    )
    return response.choices[0].message.content.strip()


# Send via email
def send_email(letter, subject, recipient_email):
    msg = MIMEText(letter)
    msg['Subject'] = subject
    msg['From'] = config["email"]["from"]
    msg['To'] = recipient_email

    with smtplib.SMTP(config["email"]["smtp_server"], config["email"]["smtp_port"]) as server:
        server.starttls()
        server.login(config["email"]["from"], config["email"]["password"])
        server.sendmail(msg['From'], [recipient_email], msg.as_string())


# Main workflow
if __name__ == "__main__":
    notes_folder = config["notes_folder"]
    recipient_email = config["recipient_email"]

    note = pick_random_note(notes_folder)
    content = get_note_content(os.path.join(notes_folder, note))
    letter = generate_letter(content)

    send_email(letter, "Your Daily Inspirational Letter", recipient_email)