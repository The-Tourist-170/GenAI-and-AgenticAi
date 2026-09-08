import tiktoken

enc = tiktoken.encoding_for_model("gpt-4o")
text = "Hello, world!"
tokens = enc.encode(text)
print(tokens)
print(enc.decode(tokens))
