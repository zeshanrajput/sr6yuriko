"""
Character Data Engine for Shadowrun 6th Edition (sr6yuriko)
Provides clean, dynamic access to Yuriko Star's character attributes, skills, and derived statistics.
"""

import os
import sys
from typing import Dict, Any, Optional
import yaml

_CACHE: Optional[Dict[str, Any]] = None

def get_base_dir() -> str:
    """Returns the absolute path to the project root directory."""
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_master_data(yaml_path: str = "yuriko_master.yaml", force_reload: bool = False) -> Dict[str, Any]:
    """Loads and caches the master character YAML file."""
    global _CACHE
    if _CACHE is not None and not force_reload:
        return _CACHE

    base_dir = get_base_dir()
    if not os.path.isabs(yaml_path):
        yaml_path = os.path.join(base_dir, yaml_path)

    if os.path.exists(yaml_path):
        with open(yaml_path, "r", encoding="utf-8") as f:
            _CACHE = yaml.safe_load(f) or {}
    else:
        _CACHE = {}
    return _CACHE

def get_attribute(name: str, default: int = 0) -> int:
    """Retrieves an attribute rating by name (case-insensitive)."""
    data = load_master_data()
    attrs = data.get("attributes", {})
    return attrs.get(name.lower(), default)

def get_skill(name: str) -> Dict[str, Any]:
    """Retrieves a skill definition dictionary by name (case-insensitive)."""
    data = load_master_data()
    skills = data.get("skills", [])
    target = name.lower()
    for s in skills:
        if s.get("name", "").lower() == target or s.get("id", "").lower() == target:
            return s
    return {}

def get_dice_pool(skill_name: str, attribute_name: str) -> int:
    """Calculates base dice pool for a skill + attribute combination."""
    skill_info = get_skill(skill_name)
    skill_rating = skill_info.get("rating", 0)
    attr_rating = get_attribute(attribute_name, 0)
    return skill_rating + attr_rating

def get_living_persona() -> Dict[str, Any]:
    """
    Returns Living Persona Matrix attributes (ASDF) for AI-Pilot Technomancer:
    Base, Resonance Point Allocations, Sprite Symbiosis, Programs (Toolbox/Encryption), and Active Totals.
    """
    data = load_master_data()
    base_fwl = get_attribute("Body", 5)
    base_slz = get_attribute("Reaction", 5)
    base_dpr = get_attribute("Agility", 3)
    base_atk = get_attribute("Strength", 3)
    
    asdf_b = data.get("living_persona", {}).get("asdf_bonuses", {})
    res_fwl = asdf_b.get("firewall", 3)
    res_slz = asdf_b.get("sleaze", 1)
    res_dpr = asdf_b.get("data_processing", 1)
    res_atk = asdf_b.get("attack", 3)
    
    sym_fwl = 1
    sym_slz = 3
    sym_dpr = 2
    sym_atk = 0
    
    prg_fwl = 0  # Unslotted Encryption/RCC Firewall (replaced by 8th Resonance point)
    prg_slz = 0
    prg_dpr = 1  # Toolbox program
    prg_atk = 0
    
    active_fwl = base_fwl + res_fwl + sym_fwl + prg_fwl
    active_slz = base_slz + res_slz + sym_slz + prg_slz
    active_dpr = base_dpr + res_dpr + sym_dpr + prg_dpr
    active_atk = base_atk + res_atk + sym_atk + prg_atk
    
    return {
        "base": {"A": base_atk, "S": base_slz, "D": base_dpr, "F": base_fwl},
        "resonance": {"A": res_atk, "S": res_slz, "D": res_dpr, "F": res_fwl},
        "symbiosis": {"A": sym_atk, "S": sym_slz, "D": sym_dpr, "F": sym_fwl},
        "programs": {"A": prg_atk, "S": prg_slz, "D": prg_dpr, "F": prg_fwl},
        "active": {"A": active_atk, "S": active_slz, "D": active_dpr, "F": active_fwl},
        "formatted_base": f"{base_atk:02d} {base_slz:02d} {base_dpr:02d} {base_fwl:02d}",
        "formatted_resonance": f"{res_atk:02d} {res_slz:02d} {res_dpr:02d} {res_fwl:02d}",
        "formatted_symbiosis": f"{base_atk + sym_atk:02d} {base_slz + sym_slz:02d} {base_dpr + sym_dpr:02d} {base_fwl + sym_fwl:02d}",
        "formatted_active": f"{active_atk:02d} {active_slz:02d} {active_dpr:02d} {active_fwl:02d}",
    }



def compute_weapon_ar(
    base_ar_str: str,
    is_ranged: bool = True,
    has_smartlink: bool = False,
    is_networked: bool = True,
    has_personalized_grip: bool = False,
    link_fired_count: int = 0,
    is_vehicle_mounted: bool = False
) -> str:
    """
    Dynamically calculates modified Attack Rating (AR) string for any weapon based on:
    - Smartlink (+2 to valid ranges)
    - Networked Smartgun benefit (+1 to valid ranges)
    - Personalized Grip (+1 to Close/Near ranges for ranged; +2 for melee)
    - Link-firing (+1 per secondary weapon)
    - Vehicle/Drone/Cyberarm Weapon Mount (+2 to valid ranges, Double Clutch p. 142)
    """
    parts = base_ar_str.split("/")
    modified = []
    
    base_bonus = 0
    if has_smartlink:
        base_bonus += 2
        if is_networked:
            base_bonus += 1
    if link_fired_count > 0:
        base_bonus += link_fired_count
    if is_vehicle_mounted:
        base_bonus += 2
        
    for idx, p in enumerate(parts):
        p_strip = p.strip()
        if p_strip.isdigit():
            val = int(p_strip) + base_bonus
            if has_personalized_grip:
                if is_ranged and idx in [0, 1]:
                    val += 1
                elif not is_ranged and idx == 0:
                    val += 2
            modified.append(str(val))
        else:
            modified.append(p_strip)
            
    return " / ".join(modified)


def get_processed_weapons() -> Dict[str, Any]:
    """
    Returns processed ranged and close combat weapons with dynamically calculated ARs,
    math breakdowns, burst fire adjustments, and firing mode constraints.
    """
    data = load_master_data()
    weapons_data = data.get("weapons", {})
    
    ranged_processed = []
    for w in weapons_data.get("ranged", []):
        accs = [str(a).lower() for a in w.get("accessories", [])]
        has_smart = w.get("smartlink", False) or any("smartlink" in a for a in accs) or "predator" in w.get("name", "").lower()
        has_grip = w.get("personalized_grip", False) or any("grip" in a for a in accs)
        link_count = w.get("link_fired_count", 0)
        is_mounted = w.get("is_vehicle_mounted", False) or any("mount" in a for a in accs)
        
        breakdown = [f"Base AR: {w.get('attack_rating', '')}"]
        total_bonus = 0
        if has_smart:
            breakdown.append("Smartlink Base: +2 AR")
            breakdown.append("Networked Smartgun: +1 AR")
            total_bonus += 3
        if has_grip:
            breakdown.append("Personalized Grip: +1 AR (Close & Near ranges only)")
            total_bonus += 1

        if is_mounted:
            breakdown.append("Vehicle/Drone Mount: +2 AR (Halves burst AR penalty)")
            total_bonus += 2
        if link_count > 0:
            breakdown.append(f"Link-Firing ({link_count}x Wasps): +{link_count} AR")
            total_bonus += link_count
            
        breakdown.append(f"Total AR Bonus: +{total_bonus} AR")
        
        mod_ar = compute_weapon_ar(
            w.get("attack_rating", ""),
            is_ranged=True,
            has_smartlink=has_smart,
            is_networked=True,
            has_personalized_grip=has_grip,
            link_fired_count=link_count,
            is_vehicle_mounted=is_mounted
        )
        
        sa_penalty = -1 if is_mounted else -2
        bf_penalty = -2 if is_mounted else -4
        
        def apply_mode_penalty(ar_str: str, pen: int) -> str:
            parts = []
            for p in ar_str.split("/"):
                p_strip = p.strip()
                if p_strip.isdigit():
                    parts.append(str(max(0, int(p_strip) + pen)))
                else:
                    parts.append(p_strip)
            return " / ".join(parts)

        ss_ar_str = mod_ar
        sa_ar_str = apply_mode_penalty(mod_ar, sa_penalty)
        bf_ar_str = apply_mode_penalty(mod_ar, bf_penalty)
        
        base_dv_str = w.get("damage", "3P")
        import re
        m_dv = re.match(r"(\d+)([A-Z]+.*)", base_dv_str)
        if m_dv:
            base_val, suffix = int(m_dv.group(1)), m_dv.group(2)
            sa_dv_str = f"{base_val + 1}{suffix}"
            bf_dv_str = f"{base_val + 2}{suffix}"
        else:
            sa_dv_str = base_dv_str
            bf_dv_str = base_dv_str

        name_lower = w.get("name", "").lower()
        if "red fox" in name_lower or "firebrand" in name_lower:
            eff_modes = "SS, SA, BF (Link-Fired Array)"
            mode_note = "Link-fired array with 2x Wasps. Drone mount halves SA/BF AR penalties to -1/-2 AR."
            ss_dv_str = "10P"
            sa_dv_str = "11P"
            bf_dv_str = "12P"
        elif link_count > 0 or "crimson wasp" in name_lower or "wasp" in name_lower or "firebolt" in name_lower:
            eff_modes = "SS, SA, BF (Link-Fired Array)"
            mode_note = "Link-fired 2x Wasps array (+2 DV array bonus). Drone mount halves SA/BF AR penalties to -1/-2 AR."
            ss_dv_str = "7P"
            sa_dv_str = "8P"
            bf_dv_str = "9P"
        elif "predator" in name_lower:
            eff_modes = "SS, SA, BF"
            mode_note = "Hand-held sidearm. SA: -2 AR (+1 DV); BF (Narrow): -4 AR (+2 DV)."
            ss_dv_str = base_dv_str
        else:
            eff_modes = w.get("mode", "SA")
            mode_note = "Mounted support weapon. Drone mount halves SA AR penalty to -1 AR."
            ss_dv_str = base_dv_str

        w_copy = dict(w)
        w_copy["modified_attack_rating"] = mod_ar
        w_copy["ss_ar"] = ss_ar_str
        w_copy["sa_ar"] = sa_ar_str
        w_copy["bf_ar"] = bf_ar_str
        w_copy["ss_dv"] = ss_dv_str
        w_copy["sa_dv"] = sa_dv_str
        w_copy["bf_dv"] = bf_dv_str
        w_copy["total_ar_bonus"] = total_bonus
        w_copy["math_breakdown"] = breakdown
        w_copy["effective_modes"] = eff_modes
        ranged_processed.append(w_copy)
        if w_copy["name"] == "Red Fox Array (Link-Fired)":
            alias = dict(w_copy)
            alias["name"] = "Red Fox"
            ranged_processed.append(alias)
        elif w_copy["name"] == "Red Fox":
            alias = dict(w_copy)
            alias["name"] = "Red Fox Array (Link-Fired)"
            ranged_processed.append(alias)

        if w_copy["name"] == "Crimson Wasp Array (2x Link-Fired)":
            alias = dict(w_copy)
            alias["name"] = "Crimson Wasp"
            ranged_processed.append(alias)
        elif w_copy["name"] == "Crimson Wasp":
            alias = dict(w_copy)
            alias["name"] = "Crimson Wasp Array (2x Link-Fired)"
            ranged_processed.append(alias)


    close_processed = []
    for w in weapons_data.get("close_combat", []):
        accs = [str(a).lower() for a in w.get("accessories", [])]
        has_grip = w.get("personalized_grip", False) or any("grip" in a for a in accs)
        is_mounted = w.get("is_vehicle_mounted", False) or any("mount" in a for a in accs)
        
        breakdown = [f"Base AR: {w.get('attack_rating', '')}"]
        total_bonus = 0
        if has_grip:
            breakdown.append("Personalized Grip (Melee): +2 AR")
            total_bonus += 2
        if is_mounted:
            breakdown.append("Fingertip Cyberarm Mount: +2 AR")
            total_bonus += 2
            
        breakdown.append(f"Total AR Bonus: +{total_bonus} AR")
        
        mod_ar = compute_weapon_ar(
            w.get("attack_rating", ""),
            is_ranged=False,
            has_smartlink=False,
            is_networked=False,
            has_personalized_grip=has_grip,
            is_vehicle_mounted=is_mounted
        )
        w_copy = dict(w)
        w_copy["modified_attack_rating"] = mod_ar
        w_copy["ss_ar"] = mod_ar
        w_copy["sa_ar"] = "N/A"
        w_copy["bf_ar"] = "N/A"
        w_copy["ss_dv"] = w.get("damage", "6P")
        w_copy["sa_dv"] = "N/A"
        w_copy["bf_dv"] = "N/A"
        w_copy["total_ar_bonus"] = total_bonus
        w_copy["math_breakdown"] = breakdown
        w_copy["effective_modes"] = "Melee (Close)"
        w_copy["mode_note"] = "Close Combat Attack."
        close_processed.append(w_copy)
        if w_copy["name"] == "Amalgam Cestas (Phys)":
            alias = dict(w_copy)
            alias["name"] = "Amalgam Cestas"
            close_processed.append(alias)
            alias_old = dict(w_copy)
            alias_old["name"] = "Krime Gloves"
            close_processed.append(alias_old)


    return {
        "ranged": ranged_processed,
        "close_combat": close_processed
    }


def get_resonance_focus_rating() -> int:
    """Returns the Resonance Focus rating (default 4)."""
    return 4

def get_character_stats(yaml_path: str = "yuriko_master.yaml") -> Dict[str, int]:
    """
    Returns character attribute and core skill ratings as a dictionary.
    Used by identity_core.qmd and rules_and_downtime.qmd.
    """
    data = load_master_data(yaml_path)
    attrs = data.get("attributes", {})
    
    return {
        "Body": attrs.get("body", 5),
        "Agility": attrs.get("agility", 3),
        "Reaction": attrs.get("reaction", 5),
        "Strength": attrs.get("strength", 3),
        "Willpower": attrs.get("willpower", 6),
        "Logic": attrs.get("logic", 4),
        "Intuition": attrs.get("intuition", 2),
        "Charisma": attrs.get("charisma", 4),
        "Resonance": attrs.get("resonance", 7),
        "Edge": attrs.get("edge", 5),
        "Tasking": get_skill("Tasking").get("rating", 6),
        "Electronics": get_skill("Electronics").get("rating", 5),
        "Cracking": get_skill("Cracking").get("rating", 5),
        "Influence": get_skill("Influence").get("rating", 1),
    }

if __name__ == "__main__":
    stats = get_character_stats()
    lp = get_living_persona()
    w_proc = get_processed_weapons()
    print("[*] Character Stats Loaded:")
    for stat_name, val in stats.items():
        print(f"    - {stat_name}: {val}")
    print(f"[*] Living Persona ASDF (Active): {lp['formatted_active']}")
    print("[*] Processed Ranged Weapons:")
    for w in w_proc["ranged"]:
        print(f"    - {w['name']}: Base {w['attack_rating']} -> Mod {w['modified_attack_rating']}")
    print("[*] Processed Close Combat Weapons:")
    for w in w_proc["close_combat"]:
        print(f"    - {w['name']}: Base {w['attack_rating']} -> Mod {w['modified_attack_rating']}")




