"""Content type registry — structural templates per genre."""

CONTENT_TYPES = {
    "travel_blog": {
        "label": "Travel Blog",
        "structure": [
            "Opening — a personal moment or sense of place",
            "Why this place?",
            "What I saw and did",
            "Practical notes",
            "Closing note / recommendation",
        ],
        "tone": "first person, warm, speaks directly to the reader",
        "length": "800-1500 words",
    },
    "travel_guide": {
        "label": "Travel Guide",
        "structure": [
            "Overview",
            "How to get there",
            "When to go",
            "What to see",
            "Where to stay and eat",
            "Practical information",
        ],
        "tone": "authoritative, advisory, information-first",
        "length": "1500-3000 words",
    },
    "magazine": {
        "label": "Magazine Article",
        "structure": [
            "Striking opening (an anecdote or a scene)",
            "Subject / thesis",
            "In-depth narrative",
            "Expert or witness voice",
            "Closing",
        ],
        "tone": "narrative, layered, draws the reader in",
        "length": "1200-2500 words",
    },
    "news": {
        "label": "News",
        "structure": [
            "Lead (who/what/when/where/why/how)",
            "Context",
            "Details",
            "Quote / source",
            "Background",
        ],
        "tone": "objective, plain, direct",
        "length": "400-800 words",
    },
    "story": {
        "label": "Story",
        "structure": [
            "Setting the scene",
            "Character / conflict",
            "Development",
            "Turning point",
            "Resolution",
        ],
        "tone": "narrative, vivid, emotional",
        "length": "1000-3000 words",
    },
    "column": {
        "label": "Column",
        "structure": [
            "Trigger event / observation",
            "The writer's take",
            "Argument / example",
            "Conclusion / call to action",
        ],
        "tone": "opinionated, provocative, original",
        "length": "500-900 words",
    },
}


def list_types() -> dict:
    return {k: v["label"] for k, v in CONTENT_TYPES.items()}


def get(content_type: str) -> dict:
    return CONTENT_TYPES.get(content_type, CONTENT_TYPES["travel_blog"])
