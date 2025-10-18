# Saving LLM based option for later to avoid HF and CPU/GPU bullshit
from openai import OpenAI
import os, re, json

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))

srt_text = open("output.srt", encoding="utf-8").read()

system_prompt = """You are labeling speakers in an interview transcript.
Assume exactly two voices: an interviewer (A) and a respondent (B).
Use the text and context to decide who is speaking each line.
Keep timestamps intact and output JSON:
[
  {"start": "...", "end": "...", "speaker": "A", "text": "..."},
  ...
]
"""

# Collapse SRT entries to text blocks for clarity
entries = re.split(r"\n\d+\n", srt_text)
srt_excerpt = "\n".join(entries[:200])  # truncate if huge

resp = client.chat.completions.create(
    model="gpt-4o-mini",
    temperature=0,
    messages=[
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": srt_excerpt}
    ],
)

json_output = resp.choices[0].message.content
segments = json.loads(re.sub(r"```(json)?", "", json_output))
print(segments[:3])
