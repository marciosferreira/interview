"""
Gera um audio WAV de exemplo usando Gemini TTS com o prompt de entrevista.
Uso: python gen_sample_audio.py
Saida: sample_output.wav
"""
import os
import struct
import mimetypes
import wave
from google import genai
from google.genai import types as _genai_types
from dotenv import load_dotenv

load_dotenv()

TEXT = """\
You mentioned solving managers' problems at FIT — what does that actually mean? \
What's a real example of something you built or solved for them in the last few months?\
"""

VOICE = os.getenv("GEMINI_TTS_VOICE", "Zephyr")
OUTPUT = "sample_followup_en.wav"

_TTS_PROMPT = """\
Read the following transcript based on the audio profile and director's note.

# Audio Profile
An experienced technical recruiter conducting a structured job interview.

# Director's note
Style: Natural. Pace: Measured. Accent: American (Gen).

## Scene:
A professional online job interview. The speaker is an experienced technical recruiter \
conducting a mock interview session to help candidates prepare for real job interviews. \
The interviewer is knowledgeable, organized, and genuinely invested in the candidate's success.

## Sample Context:
Speak with clear pronunciation and a calm, professional cadence. Use a warm but authoritative \
tone — encouraging without being casual. Pause naturally between questions to give the candidate \
space to think. Vary intonation to signal transitions between topics. Sound like a real interviewer, not a narrator.

## Transcript:
{text}"""


def _parse_audio_mime_type(mime_type: str) -> dict:
    bits_per_sample, rate = 16, 24000
    for param in mime_type.split(";"):
        param = param.strip()
        if param.lower().startswith("rate="):
            try:
                rate = int(param.split("=", 1)[1])
            except (ValueError, IndexError):
                pass
        elif param.startswith("audio/L"):
            try:
                bits_per_sample = int(param.split("L", 1)[1])
            except (ValueError, IndexError):
                pass
    return {"bits_per_sample": bits_per_sample, "rate": rate}


def _convert_to_wav(audio_data: bytes, mime_type: str) -> bytes:
    p = _parse_audio_mime_type(mime_type)
    bps, rate, ch = p["bits_per_sample"], p["rate"], 1
    block_align = ch * (bps // 8)
    header = struct.pack(
        "<4sI4s4sIHHIIHH4sI",
        b"RIFF", 36 + len(audio_data), b"WAVE",
        b"fmt ", 16, 1, ch, rate, rate * block_align, block_align, bps,
        b"data", len(audio_data),
    )
    return header + audio_data


def generate():
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY"))
    contents = [
        _genai_types.Content(
            role="user",
            parts=[_genai_types.Part.from_text(text=_TTS_PROMPT.format(text=TEXT))],
        )
    ]
    config = _genai_types.GenerateContentConfig(
        temperature=1,
        response_modalities=["audio"],
        speech_config=_genai_types.SpeechConfig(
            language_code="en-US",
            voice_config=_genai_types.VoiceConfig(
                prebuilt_voice_config=_genai_types.PrebuiltVoiceConfig(voice_name=VOICE)
            ),
        ),
    )

    chunks = []
    mime_used = "audio/L16;rate=24000"
    print(f"Gerando audio com voz '{VOICE}'...")
    for chunk in client.models.generate_content_stream(
        model="gemini-3.1-flash-tts-preview",
        contents=contents,
        config=config,
    ):
        if chunk.parts is None:
            continue
        part = chunk.parts[0]
        if part.inline_data and part.inline_data.data:
            mime_used = part.inline_data.mime_type
            chunks.append(part.inline_data.data)

    raw = b"".join(chunks)
    wav_bytes = _convert_to_wav(raw, mime_used) if mimetypes.guess_extension(mime_used) is None else raw

    with open(OUTPUT, "wb") as f:
        f.write(wav_bytes)
    print(f"Salvo em: {OUTPUT}")


if __name__ == "__main__":
    generate()
