from RealtimeSTT import AudioToTextRecorder
from RealtimeTTS import TextToAudioStream, KokoroEngine
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
import threading
from time import sleep
import time
import threading

from langgraph_test import run_agent


# ============== Init TTS and Warmup =================
print("Initializing TTS system...")
engine = KokoroEngine()
stream = TextToAudioStream(engine, frames_per_buffer=256)
stream.feed("Warmup complete")
stream.play(muted=True)

# =================== LLM Setup =====================
model_name = "Qwen/Qwen2.5-1.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(
    model_name,
    torch_dtype="auto",
    device_map="auto"
).to('mps')
model.eval()


system_prompt = """You are a helpful assistant who responds naturally, like a real person speaking out loud. Start with short, clear sentences to reduce delay in speech. Avoid robotic or overly formal language. Speak conversationally, as if you’re talking to a friend. Keep your sentences concise, especially at the start of a response. Unless told otherwise, use shorter responses. Prioritize natural flow and clarity."""
messages = [
    {"role": "system", "content": system_prompt}
]

# Thread & streamer global
gen_thread = None
streamer = None
first = True
def process_text(text):
    global gen_thread, streamer, messages, first
    
    context = run_agent(text)

    messages.append({"role": "user", "content": text})
    messages.append({"role": "assistant", "content": context})

    text_prompt = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=True
    )

    model_inputs = tokenizer([text_prompt], return_tensors="pt").to(model.device)

    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)

    def generate():
        model.generate(**model_inputs, streamer=streamer, max_new_tokens=128)

    # Start generation thread
    gen_thread = threading.Thread(target=generate)
    gen_thread.start()

    def generator():
        global first
        full_response = ""
        for token in streamer:
            if first:
                first = False
                print(time.time() - start)
            full_response += token
            yield token
        messages.append({"role": "assistant", "content": full_response})


    # Process all test cases automatically
    print("Generating audio...")
    stream.feed(generator())
    stream.play(log_synthesized_text=True)

    print("\nAll generations completed!")


# ================ Main Audio Loop ==============
if __name__ == '__main__':

    print("Wait until it says 'speak now'")
    recorder = AudioToTextRecorder(
        enable_realtime_transcription=True, 
        silero_use_onnx=True,
        no_log_file=True,
    )

    while True:
        text = recorder.text() # Do it synchronously unless we wanna interrupt with voice later
        start = time.time()
        process_text(text)