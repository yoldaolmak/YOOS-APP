from retrieve_context import retrieve
def build_prompt(query):

    ctx = retrieve(query)

    context_block = "\n\n".join(ctx)

    prompt = f"""
Kemal Voice örnekleri:

{context_block}

Aşağıdaki konuyu Kemal Kaya'nın anlatı stilinde yaz.

KURALLAR:
- birinci tekil şahıs
- somut gözlem
- broşür dili yok
- deneyim aktarımı

KONU:
{query}
"""

    return prompt


if __name__ == "__main__":

    q = "Napoli gezilecek yerler deneyim"

    p = build_prompt(q)

    print(p)
