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
    base = re.sub(r'\[.*?\]', '', base)  # Remove tags like [parent] or [invest]
    base = base.replace('_', ' ').strip()
    return base


def generate_letter(note_content):
    prompt = f"""
    You are a thoughtful personal coach. Using the provided excerpts, write an inspiring, personalized letter to encourage self-improvement. Your response must always be unique and creatively presented.

    Letter should contain:
    1. Warm greeting addressing me as 'Dear Mykhailo,'.
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
        temperature=0.9
    )
    return response.choices[0].message.content.strip()


def generate_parenting_letter(note_content):
    prompt = f"""
    You are a compassionate and cheerful parenting coach. Based on the provided excerpts, write a supportive, engaging, and personalized letter aimed at helping me and my wife improve our parenting experience.

    Family context:
    - Two daughters aged 11 and 4.
    - Our oldest daughter tends to be very sloppy, causing frustration.
    - Our youngest daughter is loud, energetic, and often unintentionally destructive, which triggers us to yell.

    Letter should contain:
    1. Warm greeting addressing me as 'Dear Mykhailo,'.
    2. Encouraging and cheerful advice drawn from the provided content.
    3. Practical suggestions for managing stress and fostering patience and positivity in parenting.
    4. Positive parenting tips specifically addressing challenges with both daughters.
    5. Recommend one insightful parenting book or movie related to the provided content.

    Excerpts:
    "{note_content}"

    Provide unique perspectives and actionable advice each time.
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
    with open(os.path.expanduser(config["investment_strategy_txt"]), 'r') as file:
        strategy = file.read()

    prompt = f"""
    You are a wise financial advisor. Using the provided excerpts from investment notes, my current portfolio asset allocations (provided below), and my declared investment strategy, craft an insightful, practical, and personalized investing letter.

    Letter should contain:
    1. Warm greeting addressing me as 'Dear Mykhailo,'.
    2. Briefly summarize my current portfolio and strategy alignment.
    3. Highlight any misalignments between my current portfolio and the declared investment strategy.
    4. Provide practical recommendations for portfolio adjustments or strategy enhancements.
    5. Include inspiring quotes or practical wisdom from famous investors relevant to my current investment scenario.

    Investment Strategy Declaration:
    "{strategy}"

    Current Portfolio Allocation:
    "{portfolio.to_string(index=False)}"

    Investment Excerpts:
    "{note_content}"

    Deliver unique, actionable insights and inspirational investment guidance each time.
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

    if "[parent]" in note:
        letter = generate_parenting_letter(content)
    elif "[invest]" in note:
        letter = generate_investing_letter(content, config)
    else:
        letter = generate_letter(content)

    send_email(letter, book_name, recipient_email)
