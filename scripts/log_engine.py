import re
import os

def get_log_totals(log_path="chapters/character_log.qmd"):
    if not os.path.exists(log_path):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        log_path = os.path.join(base_dir, "chapters", "character_log.qmd")
        
    with open(log_path, "r", encoding="utf-8") as f:
        content = f.read()

    env = {}

    # Execute Python blocks and inline expressions sequentially in document order
    pattern = re.compile(r'```\{python\}(.*?)```|`\{python\}\s*(.*?)`', re.DOTALL)
    for match in pattern.finditer(content):
        block = match.group(1)
        inline = match.group(2)
        if block is not None:
            clean_lines = [line for line in block.splitlines() if not line.strip().startswith('#|')]
            exec("\n".join(clean_lines), env)
        elif inline is not None:
            try:
                eval(inline.strip(), env)
            except Exception:
                try:
                    exec(inline.strip(), env)
                except Exception as e:
                    print(f"Warning: Failed to evaluate inline python expression '{inline}': {e}")

    rep_dict = env.get("Reputation", {})
    total_rep = sum(rep_dict.values()) if isinstance(rep_dict, dict) else 0

    get_active_fn = env.get("get_active_sprites")
    active_sprites = get_active_fn() if callable(get_active_fn) else []

    # Parse detailed structured session logs from Markdown sections starting with '### **'
    session_sections = re.split(r'\n(?=###\s+\*\*)', content)
    session_logs = []

    for section in session_sections:
        if not section.strip().startswith("### **"):
            continue

        header_match = re.search(r'###\s+\*\*(?:(\d{4}-[A-Za-z]{3}-\d{2}):\s*)?([^*]+)\*\*(?:`\{python\}\s*start_mission\((.*?)\)`|\s*)', section)
        if not header_match:
            continue

        date_str = header_match.group(1) or ""
        title_str = header_match.group(2).strip()
        mission_code = ""
        if header_match.group(3):
            mission_code = header_match.group(3).strip("'\" ")
        elif title_str:
            mission_code = title_str

        gm_match = re.search(r'\*\s+\*\*GM:\*\*\s*(.+)', section)
        gm_str = gm_match.group(1).strip() if gm_match else ""

        karma_val = 0
        karma_matches = re.findall(r"inc\s*\(\s*'Karma'\s*,\s*(-?\d+)\s*\)|inc_many\s*\(\s*\(\s*'Karma'\s*,\s*(-?\d+)\s*\)", section)
        for km in karma_matches:
            k1, k2 = km
            if k1:
                karma_val += int(k1)
            if k2:
                karma_val += int(k2)

        nuyen_val = 0
        nuyen_matches = re.findall(r"inc\s*\(\s*'Nuyen'\s*,\s*(-?\d+)\s*\)|inc_many\s*\(\s*\(\s*'Nuyen'\s*,\s*(-?\d+)\s*\)", section)
        for nm in nuyen_matches:
            n1, n2 = nm
            if n1:
                nuyen_val += int(n1)
            if n2:
                nuyen_val += int(n2)

        summary_match = re.search(r'\*\s+\*\*Summary:\*\*\s*(.+)', section)
        summary_str = summary_match.group(1).strip() if summary_match else ""

        c_matches = re.findall(r"contact\s*\(\s*\"([^\"]+)\"", section)

        session_logs.append({
            "code": mission_code,
            "title": title_str,
            "date": date_str,
            "gm": gm_str,
            "karma": karma_val,
            "nuyen": nuyen_val,
            "summary": summary_str,
            "contacts": c_matches,
            "notes": section.strip()
        })

    return {
        "Karma": env.get("Karma", 0),
        "Lifetime_Karma": env.get("Lifetime_Karma", 0),
        "Nuyen": env.get("Nuyen", 0),
        "Submersion_Grade": env.get("Submersion_Grade", 0),
        "Resonance": env.get("Resonance", 6),
        "Heat": env.get("Heat", 0),
        "Reputation": rep_dict,
        "Total_Reputation": total_rep,
        "Sprites": env.get("Sprites", []),
        "Active_Sprites": active_sprites,
        "Active_Sprite_Count": len(active_sprites),
        "Contacts": env.get("Contacts", {}),
        "Missions": env.get("Missions", []),
        "Session_Logs": session_logs
    }

if __name__ == "__main__":
    totals = get_log_totals()
    print(f"Log Totals: Karma={totals['Karma']}, Contacts={len(totals['Contacts'])}, Sessions={len(totals['Session_Logs'])}")
