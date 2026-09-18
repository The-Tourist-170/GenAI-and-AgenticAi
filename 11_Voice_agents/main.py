import speech_recognition as sr
from openai import OpenAI
import dotenv
import os
import sounddevice as sd
from pathlib import Path
from kokoro_onnx import Kokoro

dotenv.load_dotenv()

CURRENT_DIR = Path(__file__).resolve().parent
MODEL_PATH = str(CURRENT_DIR / "kokoro-v1.0.onnx")
VOICES_PATH = str(CURRENT_DIR / "voices-v1.0.bin")

client = OpenAI(
    api_key=os.getenv("CMD_API_KEY"),
    base_url=os.getenv("CMD_BASE_URL"),
)

SYSTEM_PROMPT = """
                    You are an expert voice agent. You will be given a transcript of the user's audio, what you have to do is you have to process the transcript and give a response in such a way like you are speaking naturally. Your transcribed text will be used to convert back to the voice and given to the user, so as you are acting as an voice agent.
                """

def stt() -> str:
    r = sr.Recognizer()

    with sr.Microphone() as source:
        r.adjust_for_ambient_noise(source)
        r.pause_threshold = 2

        print("\n>>> Listening...\n")
        audio = r.listen(source)
        text = r.recognize_google(audio)
        print(f"\n>>> You said: {text}\n")

        return text

def tts(text: str | None) -> None:
    if text is None:
        return
    kokoro = Kokoro(MODEL_PATH, VOICES_PATH)
    samples, sample_rate = kokoro.create(
        text,
        voice="af_sarah",
        speed=1.0,
        lang="en-us"
    )
    sd.play(samples, sample_rate)
    sd.wait()

def main():
    text = stt()
    response = client.chat.completions.create(
        model="deepseek/deepseek-v4-flash",
        messages=[{"role": "user", "content": text}],
    )
    print(f"\n>>> Response: {response.choices[0].message.content}\n")
    tts(response.choices[0].message.content)

if __name__ == "__main__":
    main()
