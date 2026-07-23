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
                eval(inline, env)
            except Exception:
                try:
                    exec(inline, env)
                except Exception as e:
                    print(f"Warning: Failed to evaluate inline python expression '{inline}': {e}")

    rep_dict = env.get("Reputation", {})
    total_rep = sum(rep_dict.values()) if isinstance(rep_dict, dict) else 0

    get_active_fn = env.get("get_active_sprites")
    active_sprites = get_active_fn() if callable(get_active_fn) else []

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
    }

if __name__ == "__main__":
    totals = get_log_totals()
    print("Log Totals:", totals)
