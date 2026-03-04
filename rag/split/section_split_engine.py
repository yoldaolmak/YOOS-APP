def split_sections(text, max_len=800):
    sections = []
    current = ""

    for line in text.split("\n"):
        if len(current) + len(line) > max_len:
            sections.append(current.strip())
            current = line
        else:
            current += "\n" + line

    if current.strip():
        sections.append(current.strip())

    return sections
