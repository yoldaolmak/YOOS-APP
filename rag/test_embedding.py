from sentence_transformers import SentenceTransformer

model = SentenceTransformer("BAAI/bge-small-en-v1.5")

text = "Kemal Kaya'nın seyahat yazıları kişisel gözlem ve deneyime dayanır."

vec = model.encode(text)

print("vector size:", len(vec))
print("sample:", vec[:5])
