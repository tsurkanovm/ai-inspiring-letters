import os
import json
import smtplib
from email.mime.text import MIMEText
from openai import OpenAI
import psycopg
from psycopg.rows import dict_row


class LetterGenerator:
    LETTER_GENERATION_TOOLS = [
        {
            "type": "function",
            "name": "generate_parenting_letter",
            "description": "Generate a parenting coaching letter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_excerpt": {"type": "string"}
                },
                "required": ["note_excerpt"],
            },
        },
        {
            "type": "function",
            "name": "generate_investing_letter",
            "description": "Generate an investing coaching letter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_excerpt": {"type": "string"}
                },
                "required": ["note_excerpt"],
            },
        },
        {
            "type": "function",
            "name": "generate_diet_letter",
            "description": "Generate a diet coaching letter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_excerpt": {"type": "string"}
                },
                "required": ["note_excerpt"],
            },
        },
        {
            "type": "function",
            "name": "generate_general_letter",
            "description": "Generate a general self-improvement letter.",
            "parameters": {
                "type": "object",
                "properties": {
                    "note_excerpt": {"type": "string"}
                },
                "required": ["note_excerpt"],
            },
        },
    ]


    ROUTER_SYSTEM_PROMPT = (
        "You are a helpful coach. "
        "Choose the appropriate coaching letter type based on the note excerpt. "
        "Call exactly one function."
    )

    def __init__(self, config_file_path="config.json"):
        self.config = self._load_config(config_file_path)
        self.client = OpenAI(api_key=self.config["openai_api_key"])

        self.letter_generators = {
            "generate_parenting_letter": self.generate_parenting_letter,
            "generate_investing_letter": self.generate_investing_letter,
            "generate_diet_letter": self.generate_diet_letter,
            "generate_general_letter": self.generate_general_letter,
        }

    def _load_config(self, config_file_path):
        with open(config_file_path) as f:
            return json.load(f)

    # ---------------- DB ----------------

    def get_random_unsent_record(self):
        with psycopg.connect(self.config["postgres_dsn"], row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT id, book_name, chunk_text, headings
                    FROM book_chunks
                    WHERE sent_as_letter = FALSE
                    ORDER BY RANDOM()
                    LIMIT 1
                """
                )
                record = cur.fetchone()
                if not record:
                    raise Exception("No unsent records available!")
                return record

    def mark_as_sent(self, record_id):
        with psycopg.connect(self.config["postgres_dsn"], row_factory=dict_row) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    UPDATE book_chunks
                    SET sent_as_letter = TRUE
                    WHERE id = %s
                """,
                    (record_id,),
                )
                conn.commit()

    # ---------------- LETTER GENERATORS ----------------

    def _simple_response(self, prompt):
        response = self.client.responses.create(
            model="gpt-5.2",
            input=prompt,
            max_output_tokens=700,
            temperature=0.9,
        )
        return response.output_text.strip()

    def generate_parenting_letter(self, note_excerpt, config):
        prompt = f"""
You are a compassionate parenting coach.

Family context:
"{config['family_info']}"

Letter requirements:
1. Warm greeting: 'Dear Mykhailo,'
2. Encouraging parenting advice
3. Stress management tips
4. Positive parenting techniques
5. The origin excerpt itself.

Excerpts:
"{note_excerpt}"
"""
        return self._simple_response(prompt)

    def generate_investing_letter(self, note_excerpt, config):
        with open(os.path.expanduser(config["investment_strategy_txt"])) as f:
            strategy = f.read()

        prompt = f"""
You are a wise financial advisor.

My investment strategy:
"{strategy}"

Letter requirements:
1. Greeting: 'Dear Mykhailo,'
2. The origin excerpt itself.
3. Inspirational investor quotes

Excerpts:
"{note_excerpt}"
"""
        return self._simple_response(prompt)

    def generate_diet_letter(self, note_excerpt, config):
        prompt = f"""
You are a supportive nutrition coach.

Health details:
"{config['health_info']}"

Letter requirements:
1. Greeting: 'Dear Mykhailo,'
2. Nutritional insights
3. Practical diet suggestions
4. The origin excerpt itself.

Excerpts:
"{note_excerpt}"
"""
        return self._simple_response(prompt)

    def generate_general_letter(self, note_excerpt, config):
        prompt = f"""
You are a thoughtful personal coach.

Personal details:
"{config['personal_info']}"

Letter requirements:
1. Warm greeting: 'Dear Mykhailo,'
2. Insightful inspirational thoughts
3. One simple measurable habit (Atomic Habits)
4. The origin excerpt itself.

Excerpts:
"{note_excerpt}"
"""
        return self._simple_response(prompt)

    # ---------------- EMAIL ----------------

    def send_email(self, letter, subject, recipient_email):
        msg = MIMEText(letter)
        msg["Subject"] = subject
        msg["From"] = self.config["email"]["from"]
        msg["To"] = recipient_email

        with smtplib.SMTP(
            self.config["email"]["smtp_server"],
            self.config["email"]["smtp_port"],
        ) as server:
            server.starttls()
            server.login(
                self.config["email"]["from"],
                self.config["email"]["password"],
            )
            server.sendmail(msg["From"], [recipient_email], msg.as_string())

    # ---------------- MAIN FLOW ----------------

    def generate_and_send_letter(self):
        record = self.get_random_unsent_record()

        response = self.client.responses.create(
            model="gpt-5.2",
            input=[
                {"role": "system", "content": self.ROUTER_SYSTEM_PROMPT},
                {"role": "user", "content": record["chunk_text"]},
            ],
            tools=self.LETTER_GENERATION_TOOLS,
            tool_choice="auto",
            parallel_tool_calls=False,
            temperature=0.0,
            max_output_tokens=200,
        )

        tool_call = None
        for item in response.output:
            if item.type == "function_call":
                tool_call = item
                break

        if tool_call is None:
            raise RuntimeError("No function tool call returned by model")

        tool_name = tool_call.name
        args = json.loads(tool_call.arguments)

        letter = self.letter_generators[tool_name](
            args["note_excerpt"], self.config
        )

        self.send_email(
            letter,
            record["book_name"],
            self.config["recipient_email"],
        )

        self.mark_as_sent(record["id"])
        print(f"Letter sent successfully. Record {record['id']} marked as sent.")


if __name__ == "__main__":
    LetterGenerator().generate_and_send_letter()
