import sys
import os

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from main import parse_character

def get_character_stats(xml_path="input/Yuriko Star.xml"):
    if not os.path.exists(xml_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        xml_path = os.path.join(base_dir, "input", "Yuriko Star.xml")
        if not os.path.exists(xml_path):
            input_dir = os.path.join(base_dir, "input")
            if os.path.exists(input_dir):
                xml_files = [f for f in os.listdir(input_dir) if f.endswith(".xml")]
                if xml_files:
                    xml_path = os.path.join(input_dir, xml_files[0])

    char_data = parse_character(xml_path)
    attrs = char_data.get("attributes", {})
    skills = char_data.get("skills", {})

    tasking_obj = next((s for s in skills.values() if s.get("id") == "tasking"), {})
    electronics_obj = next((s for s in skills.values() if s.get("id") == "electronics"), {})
    cracking_obj = next((s for s in skills.values() if s.get("id") == "cracking"), {})
    influence_obj = next((s for s in skills.values() if s.get("id") == "influence"), {})

    stats = {
        "Body": attrs.get("BODY", 0),
        "Agility": attrs.get("AGILITY", 0),
        "Reaction": attrs.get("REACTION", 1),
        "Strength": attrs.get("STRENGTH", 0),
        "Willpower": attrs.get("WILLPOWER", 6),
        "Logic": attrs.get("LOGIC", 4),
        "Intuition": attrs.get("INTUITION", 5),
        "Charisma": attrs.get("CHARISMA", 4),
        "Resonance": attrs.get("RESONANCE", 7),
        "Edge": attrs.get("EDGE", 5),
        "Tasking": tasking_obj.get("rating", 6),
        "Electronics": electronics_obj.get("rating", 5),
        "Cracking": cracking_obj.get("rating", 5),
        "Influence": influence_obj.get("rating", 1),
    }
    return stats

if __name__ == "__main__":
    stats = get_character_stats()
    print("Character Stats:", stats)
