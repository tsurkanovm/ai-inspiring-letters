import os
import random
import docx
import json
import re
import pandas as pd
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
import psycopg
from psycopg.rows import dict_row

class LetterGenerator:
    LETTER_GENERATION_TOOLS = [
        {"type": "function",
         "function": {"name": "generate_parenting_letter", "description": "Generate a parenting coaching letter.",
                      "parameters": {"type": "object", "properties": {"note_excerpt": {"type": "string"}},
                                     "required": ["note_excerpt"]}}},
        {"type": "function",
         "function": {"name": "generate_investing_letter", "description": "Generate an investing coaching letter.",
                      "parameters": {"type": "object", "properties": {"note_excerpt": {"type": "string"}},
                                     "required": ["note_excerpt"]}}},
        {"type": "function",
         "function": {"name": "generate_diet_letter", "description": "Generate a diet coaching letter.",
                      "parameters": {"type": "object", "properties": {"note_excerpt": {"type": "string"}},
                                     "required": ["note_excerpt"]}}},
        {"type": "function",
         "function": {"name": "generate_general_letter", "description": "Generate a general self-improvement letter.",
                      "parameters": {"type": "object", "properties": {"note_excerpt": {"type": "string"}},
                                     "required": ["note_excerpt"]}}},
    ]

    def __init__(self, config_file_path="config.json"):
        self.config = self._load_config(config_file_path)
        self.openai_client = self._create_openai_client()
        self.letter_generators = {
            "generate_parenting_letter": self.generate_parenting_letter,
            "generate_investing_letter": self.generate_investing_letter,
            "generate_diet_letter": self.generate_diet_letter,
            "generate_general_letter": self.generate_general_letter
        }

    def _load_config(self, config_file_path):
        with open(config_file_path) as f:
            return json.load(f)

    def _create_openai_client(self):
        return OpenAI(api_key=self.config["openai_api_key"])

    def get_random_unsent_record(self):
        """Get a random record from database that hasn't been sent as letter yet"""
        with psycopg.connect(self.config["postgres_dsn"], row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                # Get a random record where sent_as_letter is False
                cur.execute("""
                    SELECT id, book_name, chunk_text, headings 
                    FROM book_chunks 
                    WHERE sent_as_letter = FALSE 
                    ORDER BY RANDOM() 
                    LIMIT 1
                """)
                record = cur.fetchone()
                
                if not record:
                    raise Exception("No unsent records available!")
                
                return record

    def mark_as_sent(self, record_id):
        """Mark a record as sent by setting sent_as_letter to True"""
        with psycopg.connect(self.config["postgres_dsn"], row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    UPDATE book_chunks 
                    SET sent_as_letter = TRUE 
                    WHERE id = %s
                """, (record_id,))
                conn.commit()

    def generate_parenting_letter(self, note_excerpt, config):
        family = config["family_info"]
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
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.9
        )
        return response.choices[0].message.content.strip()

    def generate_investing_letter(self, note_excerpt, config):
        #does not use for now - provide the same suggestions about portfolio
        #portfolio = pd.read_csv(os.path.expanduser(config["portfolio_csv"]))
        with open(os.path.expanduser(config["investment_strategy_txt"])) as file:
            strategy = file.read()
        prompt = f"""
        You are a wise financial advisor. Using the provided excerpts, write an thoughtful, personalized letter. Check my investment strategy below:
        "{strategy}"

        Letter:
        1. Greeting: 'Dear Mykhailo,'.
        2. Insightful inspirational thoughts.
        3. Inspirational investor quotes.
        Excerpts:
        "{note_excerpt}"
        """
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.9
        )
        return response.choices[0].message.content.strip()

    def generate_diet_letter(self, note_excerpt, config):
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
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.9
        )
        return response.choices[0].message.content.strip()

    def generate_general_letter(self, note_excerpt, config):
        personal = config["personal_info"]
        prompt = f"""
        You are a thoughtful personal coach. Using the provided excerpts and personal details, write an inspiring, personalized letter.
        Personal details:
        "{personal}".
        Letter:
        1. Warm greeting: 'Dear Mykhailo,'.
        2. Insightful inspirational thoughts.
        3. Suggest one simple, measurable habit (as described in the book 'Atomic Habits' by James Clear).
        4. Recommendation of a book or movie.
        Excerpts:
        "{note_excerpt}"
        """
        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=700,
            temperature=0.9
        )
        return response.choices[0].message.content.strip()

    def send_email(self, letter, subject, recipient_email):
        msg = MIMEText(letter)
        msg['Subject'] = subject
        msg['From'] = self.config["email"]["from"]
        msg['To'] = recipient_email
        with smtplib.SMTP(self.config["email"]["smtp_server"], self.config["email"]["smtp_port"]) as server:
            server.starttls()
            server.login(self.config["email"]["from"], self.config["email"]["password"])
            server.sendmail(msg['From'], [recipient_email], msg.as_string())

    def generate_and_send_letter(self):
        recipient_email = self.config["recipient_email"]

        # Get a random unsent record from database
        record = self.get_random_unsent_record()
        
        note_content = record['chunk_text']
        email_subject = record['book_name']
        record_id = record['id']

        response = self.openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system",
                 "content": "You are a helpful coach. Choose the appropriate coaching letter type based on the note excerpt."},
                {"role": "user", "content": note_content}
            ],
            tools=self.LETTER_GENERATION_TOOLS,
            tool_choice="auto",
            temperature=0.0
        )

        #print(response.model_dump())

        tool_call = response.choices[0].message.tool_calls[0]
        tool_name = tool_call.function.name
        args = json.loads(tool_call.function.arguments)

        letter = self.letter_generators[tool_name](args["note_excerpt"], self.config)
        self.send_email(letter, email_subject, recipient_email)
        
        # Mark the record as sent
        self.mark_as_sent(record_id)
        print(f"Letter sent successfully and record {record_id} marked as sent.")


if __name__ == "__main__":
    letter_generator = LetterGenerator()
    letter_generator.generate_and_send_letter()