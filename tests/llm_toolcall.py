import re, json, time, threading
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer
from utils.parse import try_parse_tool_calls
from tools import tools
from tools.functions import run_tool_call

# ---- Model Setup ----
model_name = "Qwen/Qwen2.5-1.5B-Instruct"
tokenizer = AutoTokenizer.from_pretrained(model_name)
model = AutoModelForCausalLM.from_pretrained(model_name, torch_dtype="auto", device_map="auto")
model.eval()

prompt = "Show me you can call a tool and also print normal text. First, say something normal. Then call a tool!"

messages = [
    {"role": "system", "content": "You are Qwen, created by Alibaba Cloud. You are a helpful assistant."},
    {"role": "user", "content": prompt}
]
text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
    tools=tools,
    tool_choice="auto"
)
model_inputs = tokenizer([text], return_tensors="pt").to(model.device)

streamer = TextIteratorStreamer(tokenizer, skip_prompt=True, skip_special_tokens=True)
thread = threading.Thread(
    target=model.generate,
    kwargs=dict(**model_inputs, streamer=streamer, max_new_tokens=512)
)
thread.start()

# ---- Streaming + Tool Parse ----
buffer = ""
for token in streamer:
    print(token, end="", flush=True)
    buffer += token

result = try_parse_tool_calls(buffer)
if "tool_calls" in result:
    print("\n\n🔧 Parsed tool call:\n", result["tool_calls"])
    for tool_call in result["tool_calls"]:
        res = run_tool_call(tool_call["function"])
        print(f"Tool Result:\n{res}")

