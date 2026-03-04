from rag.retrieve_context import retrieve

query = "Napoli gezilecek yerler deneyim"

ctx = retrieve(query)

print("\n--- RAG CONTEXT ---\n")

for i,c in enumerate(ctx):
    print(f"[{i+1}]")
    print(c[:200])
    print()
