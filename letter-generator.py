import os
import json
import re
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

import psycopg
from psycopg.rows import dict_row
from openai import OpenAI


def html_to_plain(html: str) -> str:
    """
    Very small HTML->plain fallback for email clients that don't render HTML well.
    Keeps it dependency-free (no external libs).
    """
    if not html:
        return ""

    # Convert common block breaks to newlines
    text = html
    text = re.sub(r"(?i)<\s*br\s*/?\s*>", "\n", text)
    text = re.sub(r"(?i)</\s*p\s*>", "\n\n", text)
    text = re.sub(r"(?i)</\s*li\s*>", "\n", text)
    text = re.sub(r"(?i)<\s*li\s*>", "• ", text)
    text = re.sub(r"(?i)</\s*blockquote\s*>", "\n", text)

    # Strip all remaining tags
    text = re.sub(r"<[^>]+>", "", text)

    # Unescape a few common entities
    text = (
        text.replace("&nbsp;", " ")
        .replace("&amp;", "&")
        .replace("&lt;", "<")
        .replace("&gt;", ">")
        .replace("&quot;", '"')
        .replace("&#39;", "'")
    )

    # Normalize whitespace
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


class LetterGenerator:
    LETTER_GENERATION_TOOLS = [
        {
            "type": "function",
            "name": "generate_parenting_letter",
            "description": "Generate a parenting coaching letter (HTML).",
            "parameters": {
                "type": "object",
                "properties": {"note_excerpt": {"type": "string"}},
                "required": ["note_excerpt"],
            },
        },
        {
            "type": "function",
            "name": "generate_investing_letter",
            "description": "Generate an investing coaching letter (HTML).",
            "parameters": {
                "type": "object",
                "properties": {"note_excerpt": {"type": "string"}},
                "required": ["note_excerpt"],
            },
        },
        {
            "type": "function",
            "name": "generate_diet_letter",
            "description": "Generate a diet coaching letter (HTML).",
            "parameters": {
                "type": "object",
                "properties": {"note_excerpt": {"type": "string"}},
                "required": ["note_excerpt"],
            },
        },
        {
            "type": "function",
            "name": "generate_general_letter",
            "description": "Generate a general self-improvement letter (HTML).",
            "parameters": {
                "type": "object",
                "properties": {"note_excerpt": {"type": "string"}},
                "required": ["note_excerpt"],
            },
        },
    ]

    ROUTER_SYSTEM_PROMPT = (
        "You are a helpful coach. "
        "Choose the appropriate coaching letter type based on the note excerpt. "
        "Call exactly one function."
    )

    # Shared HTML formatting rules for all letter prompts
    HTML_FORMATTING_RULES = """
Formatting rules (IMPORTANT):
- Output valid HTML ONLY (no Markdown).
- Use <p>, <strong>, <em>, <ul>, <ol>, <li>, <blockquote> where helpful.
- Do not include triple backticks or code blocks.
- Do not include headings like <h1>/<h2> unless necessary; prefer <p><strong>Section:</strong> ...
- Keep it email-friendly: short paragraphs, readable lists.
- Start with: <p>Dear Mykhailo,</p>
- Finish with a short closing line and signature: <p>Warmly,<br/>Your coach</p>
"""

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

    def _simple_response(self, prompt: str) -> str:
        response = self.client.responses.create(
            model="gpt-5.2",
            input=prompt,
            max_output_tokens=900,
            temperature=0.9,
        )
        return response.output_text.strip()

    def generate_parenting_letter(self, note_excerpt, config):
        prompt = f"""
You are a compassionate parenting coach.

{self.HTML_FORMATTING_RULES}

Family context:
{config['family_info']}

Letter content requirements:
- Encouraging parenting advice
- Stress management tips for a parent
- Positive parenting techniques
- Include the original excerpt clearly (use <blockquote>)

Original excerpt:
{note_excerpt}
"""
        return self._simple_response(prompt)

    def generate_investing_letter(self, note_excerpt, config):
        with open(os.path.expanduser(config["investment_strategy_txt"])) as f:
            strategy = f.read()

        prompt = f"""
You are a wise and conservative financial advisor.

{self.HTML_FORMATTING_RULES}

My investment strategy:
{strategy}

Letter content requirements:
- A short reflection tied to the excerpt
- 2–4 practical investing reminders consistent with the strategy
- Include the original excerpt clearly (use <blockquote>)
- Add 1–2 inspirational investor quotes (short)

Original excerpt:
{note_excerpt}
"""
        return self._simple_response(prompt)

    def generate_diet_letter(self, note_excerpt, config):
        prompt = f"""
You are a supportive nutrition coach.

{self.HTML_FORMATTING_RULES}

Health details:
{config['health_info']}

Letter content requirements:
- Nutritional insights
- Practical diet suggestions (small steps)
- Include the original excerpt clearly (use <blockquote>)

Original excerpt:
{note_excerpt}
"""
        return self._simple_response(prompt)

    def generate_general_letter(self, note_excerpt, config):
        prompt = f"""
You are a thoughtful personal coach.

{self.HTML_FORMATTING_RULES}

Personal details:
{config['personal_info']}

Letter content requirements:
- Insightful inspirational thoughts tied to the excerpt
- One simple measurable habit (Atomic Habits style: clear, trackable)
- Include the original excerpt clearly (use <blockquote>)

Original excerpt:
{note_excerpt}
"""
        return self._simple_response(prompt)

    # ---------------- EMAIL ----------------

    def send_email_html(self, html_body: str, subject: str, recipient_email: str):
        """
        Sends a multipart email with both plain-text and HTML versions.
        """
        from_email = self.config["email"]["from"]

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = from_email
        msg["To"] = recipient_email

        plain_body = html_to_plain(html_body)

        part_plain = MIMEText(plain_body, "plain", "utf-8")
        part_html = MIMEText(html_body, "html", "utf-8")

        msg.attach(part_plain)
        msg.attach(part_html)

        with smtplib.SMTP(
            self.config["email"]["smtp_server"],
            self.config["email"]["smtp_port"],
        ) as server:
            server.starttls()
            server.login(from_email, self.config["email"]["password"])
            server.sendmail(from_email, [recipient_email], msg.as_string())

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

        html_letter = self.letter_generators[tool_name](args["note_excerpt"], self.config)

        # Send as HTML email (with plain-text fallback)
        self.send_email_html(
            html_letter,
            record["book_name"],
            self.config["recipient_email"],
        )

        self.mark_as_sent(record["id"])
        print(f"Letter sent successfully. Record {record['id']} marked as sent.")


if __name__ == "__main__":
    LetterGenerator().generate_and_send_letter()
