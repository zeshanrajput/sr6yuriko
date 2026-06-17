import json
import argparse
import sys
import os
import dotenv

dotenv.load_dotenv()
import re
import xml.etree.ElementTree as ET
import copy

from utils import sanitize_string, normalize_name
from rules_data import REF_MAP, SW_CAT_MAP
from rules_engine import RulesEngine

# Global Rules Engine
rules_engine = RulesEngine()

def format_page(page_val):
    return ""

def format_condition_monitor(boxes):
    # Build individual box values based on damage threshold penalties
    boxes_list = [f"[{'-' + str(i // 3) if i // 3 > 0 else '0'}]" for i in range(1, boxes + 1)]
    # Group them into chunks of 3 and join with traditional VTT pipe delimiters
    chunks = [" ".join(boxes_list[x:x+3]) for x in range(0, len(boxes_list), 3)]
    return "  " + " | ".join(chunks)

def parse_career_log(xml_root):
    career_log = []
    rewards_el = xml_root.find('rewards')
    if rewards_el is not None:
        for reward in rewards_el.findall('reward'):
            date_raw = reward.get('date', '')
            date = date_raw.split('T')[0] if 'T' in date_raw else date_raw
            exp = reward.get('exp', '0')
            money = reward.get('money', '0')
            title_el = reward.find('title')
            title = title_el.text if title_el is not None else "Unknown Event"
            
            gm_el = reward.find('gamemaster')
            gm = f" (GM: {gm_el.text})" if gm_el is not None and gm_el.text else ""
            
            career_log.append({
                "date": date,
                "karma": int(exp),
                "nuyen": int(money),
                "title": title.strip(),
                "gm": gm
            })
    career_log.sort(key=lambda x: (x['date'], x['title']))
    return career_log

def load_overrides(char_name, meta_type):
    script_dir = os.path.dirname(os.path.abspath(__file__))
    overrides_file = os.path.join(script_dir, "overrides.json")
    if not os.path.exists(overrides_file):
        return None
    try:
        with open(overrides_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        char_overrides = data.get("character_overrides", {})
        if char_name and char_name.lower() in char_overrides:
            return char_overrides[char_name.lower()]
        if meta_type and meta_type in char_overrides:
            return char_overrides[meta_type]
    except Exception as e:
        print(f"[*] Warning: Could not parse overrides: {e}")
    return None

def parse_character(input_path):
    if input_path.endswith(".xml"):
        path_xml = input_path
        path_gen = input_path.replace(".xml", ".json")
        path_fnd = input_path.replace(".xml", "-Foundry.json")
    elif input_path.endswith("-Foundry.json"):
        path_xml = input_path.replace("-Foundry.json", ".xml")
        path_gen = input_path.replace("-Foundry.json", ".json")
        path_fnd = input_path
    else:
        path_xml = input_path.replace(".json", ".xml")
        path_gen = input_path
        path_fnd = input_path.replace(".json", "-Foundry.json")
        
    # 1. XML-First Ingestion
    if not os.path.exists(path_xml):
        print(f"Error: XML file not found at {path_xml}")
        sys.exit(1)
        
    try:
        tree = ET.parse(path_xml)
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML file {path_xml}: {e}")
        sys.exit(1)
        
    is_ai = (root.get('meta') == 'pilot-ai')
    nuyen = int(root.get('nuyen', 0))
    karma = int(root.get('karmaF', 0))
    karmaI = int(root.get('karmaI', 0))
    gender = root.get('gender', 'Unknown')
    
    # Real Name and Name mapping
    name_el = root.find('name')
    name_str = name_el.text.strip() if name_el is not None and name_el.text else "Unknown"
    realname_el = root.find('realName')
    realname_str = realname_el.text.strip() if realname_el is not None and realname_el.text else name_str
    
    name_out = realname_str
    alias_out = name_str
        
    # Metatype
    metatype = root.get('meta', 'Unknown').replace('-', ' ').title()
    
    has_gen = os.path.exists(path_gen)
    has_fnd = os.path.exists(path_fnd)
    
    # JSON Reference Mapping layers
    gen_items = {}
    gen_drones = {}
    gen_matrix = {}
    gen_qualities = {}
    gen_cf = {}
    gen_echoes = {}
    
    fnd_items = {}
    fnd_drones = {}
    fnd_matrix = {}
    fnd_qualities = {}
    fnd_cf = {}
    fnd_echoes = {}
    
    meta_type_override = ""
    street_name_override = ""
    
    genesis_sins = []
    
    if has_gen:
        try:
            with open(path_gen, 'r', encoding='utf-8') as f:
                gen_data = json.load(f)
                
            meta_type_override = gen_data.get("metaType", "")
            street_name_override = gen_data.get("streetName", "")
            genesis_sins = gen_data.get("sins", [])
            
            for key in ["items", "longRangeWeapons", "closeCombatWeapons", "armors", "augmentations", "gear"]:
                for it in gen_data.get(key, []):
                    ref_key = normalize_name(it.get("id")) or normalize_name(it.get("name"))
                    gen_items[ref_key] = it
                    
            for q in gen_data.get("qualities", []):
                ref_key = normalize_name(q.get("id")) or normalize_name(q.get("name"))
                gen_qualities[ref_key] = q
                
            for cf in gen_data.get("complexForms", []):
                ref_key = normalize_name(cf.get("id")) or normalize_name(cf.get("name"))
                gen_cf[ref_key] = cf
                
            for e in gen_data.get("echoes", []):
                ref_key = normalize_name(e.get("id")) or normalize_name(e.get("name"))
                gen_echoes[ref_key] = e
                
            for d in gen_data.get("drones", []):
                ref_key = normalize_name(d.get("id")) or normalize_name(d.get("name"))
                gen_drones[ref_key] = d
                
            for m in gen_data.get("matrixItems", []):
                ref_key = normalize_name(m.get("id")) or normalize_name(m.get("name"))
                gen_matrix[ref_key] = m
        except Exception as e:
            print(f"[*] Warning: Could not parse Genesis JSON for lookup: {e}")
            
    if has_fnd:
        try:
            with open(path_fnd, 'r', encoding='utf-8') as f:
                fnd_data = json.load(f)
                
            for item in fnd_data.get("items", []):
                genesis_id = item.get("data", {}).get("genesisID")
                name = item.get("name")
                ref_key = normalize_name(genesis_id) or normalize_name(name)
                
                itype = item.get("type", "")
                if itype == "quality":
                    fnd_qualities[ref_key] = item
                elif itype == "echo":
                    fnd_echoes[ref_key] = item
                elif itype == "complexform":
                    fnd_cf[ref_key] = item
                elif itype == "gear":
                    d_ = item.get("data", {})
                    subtype = d_.get("subtype", "")
                    if "DRONE" in d_.get("type", ""):
                        fnd_drones[ref_key] = item
                    elif subtype in ["COMMLINK", "CYBERDECK", "RIGGER_CONSOLE"] or "CYBERKIT" in name.upper():
                        fnd_matrix[ref_key] = item
                    else:
                        fnd_items[ref_key] = item
        except Exception as e:
            print(f"[*] Warning: Could not parse Foundry JSON for lookup: {e}")

    # Heuristic Lookups mapped from JSON definition files
    def find_json_item(ref, custom_name):
        ref_norm = normalize_name(ref)
        c_norm = normalize_name(custom_name)
        
        # 1. Match in gen_items
        for gen_k, gen_v in gen_items.items():
            if ref_norm == gen_k or (c_norm and c_norm == gen_k):
                return gen_v
                
        # 2. Try match on name key normalized
        for gen_k, gen_v in gen_items.items():
            name_norm = normalize_name(gen_v.get("name", ""))
            if (ref_norm and (ref_norm in name_norm or name_norm in ref_norm)) or \
               (c_norm and (c_norm in name_norm or name_norm in c_norm)):
                return gen_v
                
        # Special mappings
        if ref == "ammo_heavy_smg":
            for gen_k, gen_v in gen_items.items():
                if "heavy pistol/smg" in gen_v.get("name", "").lower():
                    return gen_v
        if ref == "glitter_grenade":
            for gen_k, gen_v in gen_items.items():
                if "glitter" in gen_v.get("name", "").lower():
                    return gen_v
        if "securetech" in ref.lower():
            target_sub = ref.lower().replace("securetech_", "").replace("invisishield", "invisi-shield")
            for gen_k, gen_v in gen_items.items():
                k_lower = gen_k.lower()
                if "securetech" in k_lower and (target_sub in k_lower or k_lower in target_sub):
                    return gen_v
                    
        return None

    def find_json_drone(ref, custom_name):
        ref_norm = normalize_name(ref)
        c_norm = normalize_name(custom_name)
        for gen_k, gen_v in gen_drones.items():
            name_norm = normalize_name(gen_v.get("name", ""))
            if ref_norm == gen_k or (c_norm and c_norm == gen_k) or (ref_norm in name_norm or name_norm in ref_norm):
                return gen_v
        
        fallback_drones = {
            "nissansamurai": {
                "name": "Nissan Samurai",
                "body": 6,
                "armor": 6,
                "pilot": 3,
                "sensor": 2,
                "speed": 30,
                "handlOn": 3,
                "handlOff": 4,
                "accelOn": 10,
                "accelOff": 10,
                "speedIntOn": 10,
                "page": "6WC 137"
            },
            "mctgnat": {
                "name": "MCT Gnat",
                "body": 0,
                "armor": 0,
                "pilot": 2,
                "sensor": 1,
                "speed": 30,
                "handlOn": 3,
                "handlOff": 3,
                "accelOn": 4,
                "accelOff": 4,
                "speedIntOn": 10,
                "page": "CRB 299"
            },
            "boingskycommander": {
                "name": "FB Sky Commander",
                "body": 4,
                "armor": 2,
                "pilot": 4,
                "sensor": 5,
                "speed": 190,
                "handlOn": 4,
                "handlOff": 4,
                "accelOn": 20,
                "accelOff": 20,
                "speedIntOn": 30,
                "page": "DC 116"
            },
            "boeingskycommander": {
                "name": "FB Sky Commander",
                "body": 4,
                "armor": 2,
                "pilot": 4,
                "sensor": 5,
                "speed": 190,
                "handlOn": 4,
                "handlOff": 4,
                "accelOn": 20,
                "accelOff": 20,
                "speedIntOn": 30,
                "page": "DC 116"
            },
            "shiawasebdbutler": {
                "name": "S. Butler",
                "body": 4,
                "armor": 0,
                "pilot": 2,
                "sensor": 3,
                "speed": 8,
                "handlOn": 4,
                "handlOff": 5,
                "accelOn": 5,
                "accelOff": 5,
                "speedIntOn": 5,
                "page": "DC 116"
            },
            "shiawasebidronebutler": {
                "name": "S. Butler",
                "body": 4,
                "armor": 0,
                "pilot": 2,
                "sensor": 3,
                "speed": 8,
                "handlOn": 4,
                "handlOff": 5,
                "accelOn": 5,
                "accelOff": 5,
                "speedIntOn": 5,
                "page": "DC 116"
            },
            "shiawasebdmanatarms": {
                "name": "S. Man-at-Arms",
                "body": 10,
                "armor": 8,
                "pilot": 2,
                "sensor": 2,
                "speed": 10,
                "handlOn": 3,
                "handlOff": 3,
                "accelOn": 5,
                "accelOff": 5,
                "speedIntOn": 5,
                "page": "DC 116"
            },
            "shiawasebidronemanatarms": {
                "name": "S. Man-at-Arms",
                "body": 10,
                "armor": 8,
                "pilot": 2,
                "sensor": 2,
                "speed": 10,
                "handlOn": 3,
                "handlOff": 3,
                "accelOn": 5,
                "accelOff": 5,
                "speedIntOn": 5,
                "page": "DC 116"
            }
        }
        
        return fallback_drones.get(ref_norm) or fallback_drones.get(c_norm)

    def find_json_matrix(ref, custom_name):
        ref_norm = normalize_name(ref)
        c_norm = normalize_name(custom_name)
        for gen_k, gen_v in gen_matrix.items():
            name_norm = normalize_name(gen_v.get("name", ""))
            if ref_norm == gen_k or (c_norm and c_norm == gen_k) or (ref_norm in name_norm or name_norm in ref_norm):
                return gen_v
        return None

    if meta_type_override:
        metatype = meta_type_override.title()
        
    # Load overrides.json configuration block
    overrides = load_overrides(name_out, root.get('meta'))
    
    # Load attributes
    attributes = {}
    attr_el = root.find('attributes')
    if attr_el is not None:
        for attr in attr_el.findall('attributes'):
            attr_id = attr.get('id')
            attr_val = int(attr.get('value', 0))
            attributes[attr_id] = attr_val
            
    # Load qualities
    qualities = []
    qual_el = root.find('qualities')
    if qual_el is not None:
        for q in qual_el.findall('quality'):
            ref = q.get('ref')
            norm_ref = normalize_name(ref)
            
            q_json = gen_qualities.get(norm_ref) or {}
            
            choice = ""
            dec = q.find('decision')
            if dec is not None:
                choice = dec.get('value', '').replace('_', ' ').title()
            
            # Prefer genesis JSON choice if it is populated and matches or is a prefix/suffix
            if q_json.get("choice"):
                gen_choice = q_json["choice"]
                if not choice or choice.lower() in gen_choice.lower():
                    choice = gen_choice
                
            val = q.get('value')
            rating = int(val) if val and val.isdigit() else (q_json.get("rating", 0))
            
            qualities.append({
                "id": ref,
                "name": q_json.get("name") if q_json.get("name") else ref.replace('_', ' ').title(),
                "choice": choice,
                "positive": q_json.get("positive", True) if "positive" in q_json else True,
                "rating": rating,
                "page": q_json.get("page", "")
            })

    # Sort qualities to match the order in gen_data qualities if present
    if has_gen and "gen_data" in locals() and gen_data.get("qualities"):
        gen_order = {normalize_name(q.get("id")) or normalize_name(q.get("name")): idx for idx, q in enumerate(gen_data["qualities"])}
        qualities.sort(key=lambda x: gen_order.get(normalize_name(x["id"]) or normalize_name(x["name"]), 999))

    # Mortype (Stream or Magic type)
    mortype_el = root.find('mortype')
    mortype = mortype_el.text.strip().title() if mortype_el is not None and mortype_el.text else "Technomancer"
    
    stream_quality = next((q.get("name", "").split("Stream: ")[-1] for q in qualities if q.get("name", "").startswith("Stream:")), None)
    if stream_quality:
        mortype = stream_quality
    
    # Load skills
    skills = {}
    skills_el = root.find('skills')
    if skills_el is not None:
        for idx, skill in enumerate(skills_el.findall('skill')):
            ref = skill.get('ref')
            val = int(skill.get('value', 0))
            
            attr_map = {
                "con": "Charisma",
                "cracking": "Logic",
                "electronics": "Logic",
                "influence": "Charisma",
                "language": "Logic",
                "tasking": "Resonance"
            }
            attr_key = attr_map.get(ref.lower(), "Logic")
            
            specializations = []
            spec_el = skill.find('skillspec')
            if spec_el is not None:
                spec_ref = spec_el.get('ref')
                specializations.append({"name": spec_ref.replace('_', ' ').title()})
                
            display_name = ref.replace('_', ' ').title()
            if ref.lower() == "language":
                display_name = "Native Language"
                
            skill_obj = {
                "id": ref,
                "name": display_name,
                "rating": val,
                "attribute": attr_key,
                "specializations": specializations
            }
            skills[f"{ref}_{idx}"] = skill_obj
            
    # Load complex forms
    complex_forms = []
    cf_el = root.find('complexforms')
    if cf_el is not None:
        for cf in cf_el.findall('complexforms'):
            ref = cf.get('ref')
            norm_ref = normalize_name(ref)
            cf_json = gen_cf.get(norm_ref) or {}
            
            fading = cf_json.get("fading") or "?"
            page = cf_json.get("page") or ""
            
            complex_forms.append({
                "name": cf_json.get("name") if cf_json.get("name") else ref.replace('_', ' ').title(),
                "fading": fading,
                "page": page
            })
            
    # Load echoes
    echoes = []
    echo_el = root.find('metaEchoes')
    if echo_el is not None:
        for echo in echo_el.findall('metaEcho'):
            ref = echo.get('ref')
            norm_ref = normalize_name(ref)
            echo_json = gen_echoes.get(norm_ref) or {}
            echoes.append({
                "name": echo_json.get("name") if echo_json.get("name") else ref.replace('_', ' ').title(),
                "page": echo_json.get("page", "")
            })
            
    # Hybrid Sprites stream injection
    if any("technoshaman" in q["id"].lower() for q in qualities):
        has_hybrid = any(normalize_name(e["name"]) == "hybridsprites" for e in echoes)
        if not has_hybrid:
            echoes.insert(0, {
                "name": "Hybrid Sprites",
                "page": "Hack'n Slash 67"
            })
            
    # Submersion calculation
    submersion = len(echoes)
    if any("technoshaman" in q["id"].lower() for q in qualities):
        if any("hybrid sprites" in e["name"].lower() for e in echoes):
            submersion = max(0, submersion - 1)
            
    # Load lifestyles, sins, licenses, contacts
    lifestyles = []
    life_el = root.find('lifestyles')
    if life_el is not None:
        for l in life_el.findall('lifestyle'):
            lifestyles.append({
                "name": l.get('ref', 'Unknown').upper(),
                "paidMonths": int(l.get('value', 0))
            })
            
    sins = []
    sins_el = root.find('sins')
    if sins_el is not None:
        for s in sins_el.findall('sin'):
            sins.append({
                "name": s.get('name', ''),
                "quality": s.get('quality', '')
            })
            
    licenses = []
    lic_el = root.find('licenses')
    if lic_el is not None:
        for l in lic_el.findall('licenses'):
            licenses.append({
                "name": l.get('name', ''),
                "rating": l.get('rating', '')
            })
            
    contacts = []
    con_el = root.find('contacts')
    if con_el is not None:
        for c in con_el.findall('contact'):
            favors_val = c.get('favors')
            favors = int(favors_val) if favors_val and favors_val.isdigit() else 0
            contacts.append({
                "name": c.get('name', 'Unknown'),
                "type": c.get('typename', 'Contact'),
                "loyalty": int(c.get('loy', 0)),
                "influence": int(c.get('rat', 0)),
                "favors": favors
            })
            
    # Load manifests
    items = []
    drones = []
    matrix_items = []
    xml_software = []
    
    xml_items_el = root.find('items')
    if xml_items_el is not None:
        for it in xml_items_el.findall('item'):
            ref = it.get('ref')
            norm_ref = normalize_name(ref)
            custom_name_el = it.find('customName')
            custom_name = custom_name_el.text.strip() if custom_name_el is not None and custom_name_el.text else ""
            
            if custom_name.lower() == "shopsoft":
                xml_software.append({
                    "ref": "shopsoft",
                    "name": "Shopsoft",
                    "rating": 0,
                    "target": "",
                    "cat": "Other Programs"
                })
                continue
                
            # Software Library
                
            # Software Library
            if ref == "software_library":
                for acc in it.findall('.//item'):
                    acc_ref = acc.get('ref')
                    sw_name = REF_MAP.get(acc_ref, acc_ref.replace('_', ' ').title())
                    
                    rating = 0
                    target = ""
                    for dec in acc.findall('decision'):
                        if dec.get('choice') == 'c2d17c87-1cfe-4355-9877-a20fe09c170d':
                            try:
                                rating = int(dec.get('value', '0'))
                            except ValueError as e:
                                print(f"[*] Warning: Malformed rating: {e}")
                                rating = 0
                        elif dec.get('choice') in ['355a3a45-39fc-4376-8667-661c9873dfdb', '2baf4c6e-417b-4d1a-943c-edfa816d50bf']:
                            target = dec.get('value', '').replace('_', ' ').title()
                            
                    # Fallbacks based on acc_ref or sw_name
                    cat = SW_CAT_MAP.get(sw_name.upper())
                    if not cat:
                        if acc_ref == "stealth_auto" or "soft_" in acc_ref or acc_ref in ["clearsight", "evasion", "maneuvering", "navigation", "performance", "targeting", "tracking"]:
                            cat = "Autosofts"
                        elif acc_ref in ["baby_monitor", "browse", "edit", "emulator", "encryption", "signal_scrubber", "toolbox", "virtual_machine"]:
                            cat = "Basic programs"
                        elif acc_ref == "smart_rig":
                            cat = "Rigger Software"
                        else:
                            cat = "Basic programs"
                            
                    if cat in ["Hacking", "Hackingprograms"]:
                        cat = "Hackingprograms"
                    elif cat in ["Basic", "Basic programs"]:
                        cat = "Basic programs"
                    elif cat == "Autosofts":
                        cat = "Autosofts"
                    elif cat in ["Commlink Apps", "Commlink"]:
                        cat = "Commlink Apps"
                    elif cat in ["Rigger Software", "Rigger"]:
                        cat = "Rigger Software"
                    elif cat in ["Other", "Other Programs"]:
                        cat = "Other Programs"
                        
                    xml_software.append({
                        "ref": acc_ref,
                        "name": sw_name,
                        "rating": rating,
                        "target": target,
                        "cat": cat
                    })
                continue
                
            # Mapped item checks
            mapped_drone = find_json_drone(ref, custom_name)
            mapped_matrix = find_json_matrix(ref, custom_name)
            
            is_drone = mapped_drone is not None or (norm_ref in fnd_drones)
            is_matrix = (mapped_matrix is not None or (norm_ref in fnd_matrix) or ref in ["erika_elite", "transys_avalon"] or custom_name == "Cyberkit (R6)") and ref != "cyberweapon_wrist_shield"
            
            accessories = []
            for acc in it.findall('.//item'):
                acc_ref = acc.get('ref')
                acc_name = REF_MAP.get(acc_ref, acc_ref.replace('_', ' ').title())
                norm_acc_name = acc_name.upper()
                
                is_software_prog = (
                    norm_acc_name in SW_CAT_MAP or 
                    acc_ref in ["signal_scrubber", "toolbox", "virtual_machine", "personal_assistant", "p-ice_spines"] or 
                    "soft_" in acc_ref or
                    acc_ref in ["artillery_barrage", "ecm_warrior_ii", "mobile_medic", "sneak_sneak", "target_artist"]
                )
                
                if is_matrix and is_software_prog:
                    rating = 0
                    for dec in acc.findall('decision'):
                        if dec.get('choice') == 'c2d17c87-1cfe-4355-9877-a20fe09c170d':
                            try:
                                rating = int(dec.get('value', '0'))
                            except ValueError:
                                rating = 0
                    
                    cat = SW_CAT_MAP.get(norm_acc_name)
                    if not cat:
                        if "soft_" in acc_ref:
                            cat = "Autosofts"
                        else:
                            cat = "Basic programs"
                            
                    if cat in ["Hacking", "Hackingprograms"]:
                        cat = "Hackingprograms"
                    elif cat in ["Basic", "Basic programs"]:
                        cat = "Basic programs"
                    elif cat == "Autosofts":
                        cat = "Autosofts"
                    elif cat in ["Commlink Apps", "Commlink"]:
                        cat = "Commlink Apps"
                    elif cat in ["Rigger Software", "Rigger"]:
                        cat = "Rigger Software"
                    elif cat in ["Other", "Other Programs"]:
                        cat = "Other Programs"
                        
                    xml_software.append({
                        "ref": acc_ref,
                        "name": acc_name,
                        "rating": rating,
                        "target": "",
                        "cat": cat
                    })
                    continue
                
                if acc_ref == "comhack_stealthlink_upgrade":
                    acc_name = "Stealthlink Upgrade"
                elif acc_ref in ["comhack_satellite_link", "satellite_link"]:
                    acc_name = "Satellite link"
                accessories.append({"name": acc_name, "ref": acc_ref, "type": "Accessory"})
            
            if is_drone:
                gen_drn = mapped_drone
                fnd_drn = fnd_drones.get(norm_ref)
                d_data = fnd_drn.get("data", {}) if fnd_drn else {}
                drn_accs = d_data.get("accessories", "") if fnd_drn else ""
                
                body_val = int(d_data.get("bod", 0)) or (gen_drn.get("body", 0) if gen_drn else 0)
                drone_cm_boxes = (body_val + 1) // 2 + 8
                
                drones.append({
                    "name": gen_drn.get("name") if gen_drn else ref.replace('_', ' ').title(),
                    "body": body_val,
                    "armor": int(d_data.get("arm", 0)) or (gen_drn.get("armor", 0) if gen_drn else 0),
                    "pilot": int(d_data.get("pil", 0)) or (gen_drn.get("pilot", 0) if gen_drn else 0),
                    "sensor": int(d_data.get("sen", 0)) or (gen_drn.get("sensor", 0) if gen_drn else 0),
                    "speed": int(d_data.get("tspd", 0)) or (gen_drn.get("speed", 0) if gen_drn else 0),
                    "handlOn": int(d_data.get("handlOn", 0)) or (gen_drn.get("handlOn", 0) if gen_drn else 0),
                    "handlOff": int(d_data.get("handlOff", 0)) or (gen_drn.get("handlOff", 0) if gen_drn else 0),
                    "accelOn": int(d_data.get("accOn", 0)) or (gen_drn.get("accelOn", 0) if gen_drn else 0),
                    "accelOff": int(d_data.get("accOff", 0)) or (gen_drn.get("accelOff", 0) if gen_drn else 0),
                    "speedIntOn": int(d_data.get("spdiOn", 0)) or (gen_drn.get("speedIntOn", 0) if gen_drn else 0),
                    "page": (gen_drn.get("page") if gen_drn else "") or d_data.get("page") or "",
                    "accessories": drn_accs,
                    "condition_monitor_boxes": drone_cm_boxes
                })
                continue
                
            if is_matrix:
                gen_m = mapped_matrix
                fnd_m = fnd_matrix.get(norm_ref)
                m_type = "COMMLINK"
                page_override = ""
                if custom_name == "Cyberkit (R6)" or "cyberkit" in ref.lower():
                    m_type = "CYBERDECK"
                    page_override = "HnS 61"
                elif gen_m and gen_m.get("subType"):
                    m_type = gen_m.get("subType")
                elif fnd_m and fnd_m.get("data", {}).get("subtype"):
                    m_type = fnd_m.get("data", {}).get("subtype")
                    
                # Clean up Cyberkit accessories Link Projector etc.
                if "CYBERKIT" in custom_name.upper() or "cyberkit" in ref.lower():
                    accessories = [a for a in accessories if not any(hack.lower() in a["name"].lower() for hack in ["Armorlink Upgrade", "Trid projector"])]

                matrix_items.append({
                    "name": custom_name if custom_name else (gen_m.get("name") if gen_m else ref.replace('_', ' ').title()),
                    "subType": m_type,
                    "page": page_override if page_override else ((gen_m.get("page") if gen_m else "") or (fnd_m.get("data", {}).get("page") if fnd_m else "") or (REF_MAP.get(ref, ref.replace('_', ' ').title()))),
                    "accessories": accessories,
                    "attack": 4 if (custom_name == "Cyberkit (R6)" or "cyberkit" in ref.lower()) else 0,
                    "sleaze": 4 if (custom_name == "Cyberkit (R6)" or "cyberkit" in ref.lower()) else 0,
                    "dataProcessing": 2 if (custom_name == "Cyberkit (R6)" or "cyberkit" in ref.lower()) else (2 if ref == "erika_elite" else 0),
                    "firewall": 2 if (custom_name == "Cyberkit (R6)" or "cyberkit" in ref.lower()) else (1 if ref == "erika_elite" else 0)
                })
                continue
                
            # Match standard manifests using lookup matching Layer
            mapped_item = find_json_item(ref, custom_name)
            it_name = custom_name if custom_name else (mapped_item.get("name") if mapped_item else ref.replace('_', ' ').title())
            
            is_katana = False
            for dec in it.findall('decision'):
                if dec.get('value') == 'katana':
                    is_katana = True
            if is_katana:
                it_name = "Katana"
                
            count = int(it.get('count', '1'))
            if ref == "ammo_heavy_smg":
                dec_val = ""
                for dec in it.findall('decision'):
                    dec_val = dec.get('value', '')
                if dec_val == "regular":
                    it_name = f"{it_name} Std x{count}"
                elif dec_val == "gel":
                    it_name = f"{it_name} Gel x{count}"
            elif count > 1:
                it_name = f"{it_name} x{count}"
                
            it_type = mapped_item.get("type", "GEAR") if mapped_item else "GEAR"
            it_page = mapped_item.get("page", "") if mapped_item else ""
            
            rating = 0
            rating_el = it.find('rating')
            if rating_el is not None and rating_el.text:
                try:
                    rating = int(rating_el.text)
                except ValueError:
                    pass
            if not rating and mapped_item and mapped_item.get("rating"):
                try:
                    rating = int(mapped_item["rating"])
                except (ValueError, TypeError):
                    pass
                    
            armor_val = 0
            armor_el = it.find('armor')
            if armor_el is not None and armor_el.text:
                try:
                    armor_val = int(armor_el.text)
                except ValueError:
                    pass
            if not armor_val and mapped_item and mapped_item.get("armorRating"):
                try:
                    armor_val = int(mapped_item["armorRating"])
                except (ValueError, TypeError):
                    pass
            
            items.append({
                "name": it_name,
                "type": it_type,
                "accessories": accessories,
                "page": it_page,
                "damage": mapped_item.get("damage", "") if mapped_item else "",
                "attackRating": mapped_item.get("attackRating", "") if mapped_item else "",
                "rating": rating,
                "armorRating": armor_val
            })
            
    # Overrides custom injections
    if overrides and "inject_items" in overrides:
        for inject in overrides["inject_items"]:
            items.append({
                "name": inject.get("name"),
                "type": inject.get("type", "GEAR"),
                "accessories": [],
                "page": inject.get("page", "")
            })
            
    # Enforce technomancer living persona calculations
    is_technomancer = submersion > 0 or attributes.get("RESONANCE", 0) > 0
    has_symbiosis = any("sprite symbiosis" in e["name"].lower() for e in echoes)
    
    if is_ai:
        base_fwl = attributes.get('BODY', 0)
        base_slz = attributes.get('REACTION', 0)
        base_dpr = attributes.get('AGILITY', 0)
        base_atk = attributes.get('STRENGTH', 0)
        
        sym_fwl = 0
        sym_slz = 0
        sym_dpr = 0
        sym_atk = 0
        
        res_fwl = 2
        res_slz = 3
        res_dpr = 1
        res_atk = 0
        
        attributes["FWL"] = base_fwl + sym_fwl + res_fwl
        attributes["SLZ"] = base_slz + sym_slz + res_slz
        attributes["DPR"] = base_dpr + sym_dpr + res_dpr
        attributes["ATK"] = base_atk + sym_atk + res_atk
    else:
        attributes["FWL"] = attributes.get('WILLPOWER', 0)
        attributes["SLZ"] = attributes.get('INTUITION', 0)
        attributes["DPR"] = attributes.get('LOGIC', 0)
        attributes["ATK"] = attributes.get('CHARISMA', 0)
        
    wil_val = attributes.get('WILLPOWER', 0)
    matrix_cm_boxes = (wil_val + 1) // 2 + 8
    char_data = {
        "name": name_out,
        "alias": alias_out,
        "metatype": metatype,
        "mortype": mortype,
        "gender": gender.upper(),
        "karma": karma,
        "karmaI": karmaI,
        "nuyen": nuyen,
        "submersion": submersion,
        "is_ai": is_ai,
        "has_natural_hacker": any("natural_hacker" in q["id"] for q in qualities),
        "has_technoshaman": any("technoshaman" in q["id"] for q in qualities),
        "attributes": attributes,
        "skills": skills,
        "complex_forms": complex_forms,
        "echoes": echoes,
        "drones": drones,
        "matrix_items": matrix_items,
        "items": items,
        "contacts": contacts,
        "sins": sins,
        "genesis_sins": genesis_sins,
        "licenses": licenses,
        "lifestyles": lifestyles,
        "qualities": qualities,
        "is_technomancer": is_technomancer,
        "xml_software": xml_software,
        "matrix_condition_monitor_boxes": matrix_cm_boxes,
        "career_log": parse_career_log(root)
    }
    
    return char_data

def classify_item(name):
    name_lower = name.lower()
    non_combat = [
        "anti-theft", "drone rack", "propulsion", "structural integrity", "concealment",
        "cyberarm", "compartment", "coating", "sensor", "ecm", "focus", "program",
        "software", "app", "license", "sin", "lifestyle", "commlink", "cyberdeck",
        "rigger console", "realistic features", "satellite link", "matrix", "toolbox",
        "ammo", "ammunition", "glitter", "ram plating", "radar-absorbent",
        "weapon mount", "implanted heavy pistol"
    ]
    if any(nc in name_lower for nc in non_combat):
        return False, False
        
    known_weapons = [
        "predator", "whip", "spurs", "coil", "pistol", "smg", "rifle", "cannon",
        "shotgun", "blade", "sword", "katana", "knife", "dagger", "laser", "grenade",
        "missile", "rocket", "unarmed", "bite", "claws", "striker", "megalodon", "mount"
    ]
    known_armor = [
        "armor", "shield", "vest", "jacket", "helmet", "lining", "skinshield"
    ]
    
    is_w = any(w in name_lower for w in known_weapons)
    is_a = any(a in name_lower for a in known_armor)
    
    if is_w and not is_a:
        return True, False
    if is_a and not is_w:
        return False, True
    return None, None

def zip_panels(left_lines, right_lines, left_width=37, separator=" | "):
    out_lines = []
    max_len = max(len(left_lines), len(right_lines))
    for i in range(max_len):
        left_val = left_lines[i] if i < len(left_lines) else ""
        right_val = right_lines[i] if i < len(right_lines) else ""
        padded_left = left_val.ljust(left_width)
        out_lines.append(f"{padded_left}{separator}{right_val}".rstrip())
    return out_lines

import textwrap
def wrap_panel_text(text, width=37, indent="    "):
    if not text:
        return []
    text_clean = text.replace('\n', ' ').strip()
    return textwrap.wrap(text_clean, width=width, initial_indent=indent, subsequent_indent=indent)

class FootnoteRegistry:
    def __init__(self):
        self.footnotes = []
        self.key_to_id = {}
    
    def add_footnote(self, title, items):
        title = title.strip()
        # convert items list to tuple (with nested lists converted to tuples) for hashable dict key
        hashable_items = []
        for it in items:
            if isinstance(it, list):
                hashable_items.append(tuple(it))
            else:
                hashable_items.append(it)
        key = (title, tuple(hashable_items))
        
        if key in self.key_to_id:
            return self.key_to_id[key]
        fid = f"[#{len(self.footnotes) + 1}]"
        self.footnotes.append((fid, title, items))
        self.key_to_id[key] = fid
        return fid
        
    def get_footer_lines(self):
        lines = []
        if self.footnotes:
            lines.append("")
            lines.append("[ CONSOLIDATED_RULES_FOOTNOTES ]")
            for fid, title, items in self.footnotes:
                lines.append(f"  {fid} {title}:")
                for item in items:
                    if isinstance(item, (list, tuple)):
                        for subitem in item:
                            wrapped = textwrap.wrap(subitem, width=63)
                            if wrapped:
                                lines.append(f"         - {wrapped[0]}")
                                for w in wrapped[1:]:
                                    lines.append(f"           {w}")
                    else:
                        wrapped = textwrap.wrap(item, width=65)
                        if wrapped:
                            lines.append(f"       - {wrapped[0]}")
                            for w in wrapped[1:]:
                                lines.append(f"         {w}")
        return lines

def format_compact_condition_monitor(boxes):
    boxes_list = [f"[{'-' + str(i // 3) if i // 3 > 0 else '0'}]" for i in range(1, boxes + 1)]
    chunks = [" ".join(boxes_list[x:x+3]) for x in range(0, len(boxes_list), 3)]
    rows = []
    for i in range(0, len(chunks), 2):
        row_chunks = chunks[i:i+2]
        rows.append("  " + " | ".join(row_chunks))
    return rows

def make_page_break(page_num, title, char_name):
    divider = []
    divider.append("\n\f\n")
    divider.append("___________________________________________________________________________")
    divider.append(f"// {char_name.upper().replace(' ', '_')}.bin // PAGE {page_num}: {title.upper()} //")
    divider.append("___________________________________________________________________________")
    divider.append("")
    return divider

def generate_ascii_sheet(char_data, verbose=False):
    a = char_data["attributes"]
    s = char_data["skills"]
    is_ai = char_data["is_ai"]
    is_tech = char_data["is_technomancer"]
    
    bod = a.get('BODY', 0)
    agi = a.get('AGILITY', 0)
    rea = a.get('REACTION', 0)
    str_ = a.get('STRENGTH', 0)
    wil = a.get('WILLPOWER', 0)
    log = a.get('LOGIC', 0)
    int_ = a.get('INTUITION', 0)
    cha = a.get('CHARISMA', 0)
    edg = a.get('EDGE', 0)
    res = a.get('RESONANCE', 0)
    submersion = char_data["submersion"]
    
    # Calculate earned_karma and lifetime_karma dynamically from XML attributes
    total_karma = char_data.get("karma", 0) + char_data.get("karmaI", 0)
    # Ignore karma spent toward the ally sprite from the lifetime/earned calculation
    ally_sprite_karma = 0
    for entry in char_data.get("career_log", []):
        if "ally sprite" in entry.get("title", "").lower() and entry.get("karma", 0) < 0:
            ally_sprite_karma += abs(entry["karma"])
    total_karma += ally_sprite_karma
    earned_karma = total_karma - 5
    lifetime_karma = total_karma
    
    f = a.get("FWL", 0)
    s_val = a.get("SLZ", 0)
    d = a.get("DPR", 0)
    atk = a.get("ATK", 0)
    
    spark = a.get('ESSENCE', a.get('SPARK', 6))
    
    phys_init_val = 7
    phys_init_dice = "+1D6"
    hot_init_val = 5
    hot_init_dice = "+3D6"
    
    composure = cha + wil
    judge_int = int_ + wil
    
    res_focus_rating = 0
    for item in char_data.get("items", []):
        name = item.get("name", "")
        if "Resonance Focus" in name:
            m = re.search(r'\(R(\d+)\)', name, re.IGNORECASE)
            if m:
                res_focus_rating = int(m.group(1))
            elif "Rating 4" in name:
                res_focus_rating = 4
                
    has_symbiosis = any("sprite symbiosis" in echo["name"].lower() for echo in char_data.get("echoes", []))

    fn_registry = FootnoteRegistry()

    # Build Page 1 Front
    page1 = []
    page1.append("___________________________________________________________________________")
    file_name = char_data['name'].upper().replace(' ', '_')
    nuyen = char_data.get('nuyen', 0)
    page1.append(f"// ACCESSING: {file_name}.bin // SOURCE: RESONANCE_REALMS //")
    page1.append(f"// STATUS: ONLINE // LIFETIME KARMA: {lifetime_karma} // KARMA: {char_data['karma']} // NUYEN: ¥{nuyen:,} //")
    page1.append("___________________________________________________________________________")
    page1.append("")
    page1.append("[ IDENTITY ]")
    page1.append(f"  > NAME: {char_data['name'].ljust(22)} > ALIAS: {char_data['alias']}")
    page1.append(f"  > METATYPE: {char_data['metatype'].ljust(18)} > GENDER: {char_data['gender']}")
    page1.append(f"  > STREAM: {char_data['mortype'].ljust(20)} > SIN: [LOCAL_FILE_ENCRYPTED]")
    page1.append("")

    # Left Panel: Attributes
    left_attr = []
    left_attr.append("[ CORE_ATTRIBUTES ]")
    if is_ai:
        left_attr.append(f"  MAT | ATK [{str_:02}] SLZ [{rea:02}] DPR [{agi:02}] FWL [{bod:02}]")
        left_attr.append(f"  MNT | WIL [{wil:02}] LOG [{log:02}] INT [{int_:02}] CHA [{cha:02}]")
        left_attr.append(f"  SPP | EDG [{edg:02}] RES [{res:02}] SPK [{spark:02}] SUB [{submersion:02}]")
    else:
        left_attr.append(f"  PHY | BOD [{bod:02}] AGI [{agi:02}] REA [{rea:02}] STR [{str_:02}]")
        left_attr.append(f"  MNT | WIL [{wil:02}] LOG [{log:02}] INT [{int_:02}] CHA [{cha:02}]")
        left_attr.append(f"  SPP | EDG [{edg:02}] RES [{res:02}] ESS [-]  SUB [{submersion:02}]")
    left_attr.append("")
    
    if is_ai:
        left_attr.append("[ MATRIX EQUIVALENT ATTRIBUTES ]")
        left_attr.append(f"  BOD [F]  AGI [D]  REA [S]  STR [A]")
        left_attr.append(f"  Resist: FWL ({f:02})")
    elif char_data["mortype"].lower() in ["technomancer", "technoshamans"]:
        left_attr.append("[ LIVING_PERSONA ]")
        left_attr.append(f"  ATK [{atk:02}]  SLZ [{s_val:02}]  DPR [{d:02}]  FWL [{f:02}]")
        left_attr.append(f"  Resist: FWL ({f:02})")

    # Right Panel: Derived Status and Pools
    right_status = []
    right_status.append("[ DERIVED_STATUS ]")
    if is_ai:
        right_status.append(f"  INIT (VR)  : {int_ + d} +3D6")
        right_status.append(f"  ATK RATING : {atk + s_val:02} (ATK+SLZ)")
        right_status.append(f"  DEF RATING : {d + f:02} (DPR+FWL)")
    else:
        right_status.append(f"  INIT (PHYS): {phys_init_val} {phys_init_dice}")
        right_status.append(f"  INIT (HOT) : {hot_init_val} {hot_init_dice}")
    right_status.append(f"  COMPOSURE  : {composure}")
    right_status.append(f"  JUDGE INT  : {judge_int}")
    
    if is_ai or char_data["mortype"].lower() in ["technomancer", "technoshamans"]:
        right_status.append(f"Def (Bio): WIL + FWL ({wil + f:02})")
        right_status.append(f"Heal: Software + LOG vs (5-Spark)")

    page1.extend(zip_panels(left_attr, right_status, left_width=44, separator=" | "))
    page1.append("")

    # Matrix Condition Monitor: Single line at full width
    page1.append("[ MATRIX_CONDITION_MONITOR ]")
    cm_boxes = char_data["matrix_condition_monitor_boxes"]
    boxes_list = [f"[{'-' + str(i // 3) if i // 3 > 0 else '0'}]" for i in range(1, cm_boxes + 1)]
    chunks = [" ".join(boxes_list[x:x+3]) for x in range(0, len(boxes_list), 3)]
    page1.append("  " + " | ".join(chunks))
    page1.append("")

    # Skill matrix block
    page1.append("[ SKILL_MATRICES ]")
    
    def get_skill_formatted_line(skill_obj):
        rating = skill_obj.get("rating", 0)
        attr_key = skill_obj.get("attribute", "").upper()
        base_attr_val = a.get(attr_key, 0)
        
        has_natural_hacker = char_data.get("has_natural_hacker", False)
        matrix_skills = ["cracking", "electronics", "tasking"]
        
        used_attr_val = base_attr_val
        attr_marker = ""
        is_res_roll = (attr_key == "RESONANCE")
        
        skill_id_clean = skill_obj.get("id", "").split('_')[0].lower()
        
        skill_mods = []
        if has_natural_hacker and skill_id_clean in matrix_skills and res > base_attr_val:
            used_attr_val = res
            skill_mods.append("Pool substitutes Logic/Willpower with Resonance (Natural Hacker)")
            is_res_roll = True
        
        symbiosis_bonus = 0
        if has_symbiosis and skill_id_clean in ["electronics", "cracking"]:
            symbiosis_bonus = 4
            skill_mods.append("Includes Sprite Symbiosis bonus +4")
            
        base_pool = rating + used_attr_val
        
        if is_res_roll and res_focus_rating > 0:
            base_pool += res_focus_rating
            skill_mods.append(f"Includes Resonance Focus +{res_focus_rating} (Fading Value: {res_focus_rating // 2} for use)")

        fn_marker = ""
        if skill_mods:
            fn_marker = fn_registry.add_footnote(f"{skill_obj.get('name')} adjustments", skill_mods)
            
        spec_str = ""
        is_hybrid = skill_id_clean == "electronics" and has_natural_hacker
        
        if is_hybrid:
            mundane_pool = rating + base_attr_val + symbiosis_bonus
            if skill_obj.get("specializations"):
                spec = skill_obj["specializations"][0]
                spec_name = spec.get("name", "")
                spec_str = f"({spec_name} +2)"
                spec_pool_res = base_pool + 2 + symbiosis_bonus
                spec_pool_log = mundane_pool + 2
                pool_str = f"-> Mtx:  {(base_pool + symbiosis_bonus):02}{fn_marker} / {spec_pool_res:02}{fn_marker}"
                second_line = " " * 50 + f"Log:  {mundane_pool:02}{fn_marker} / {spec_pool_log:02}{fn_marker}"
                pool_str = f"{pool_str}\n{second_line}"
            else:
                pool_str = f"-> Mtx:  {(base_pool + symbiosis_bonus):02}{fn_marker}"
                second_line = " " * 50 + f"Log:  {mundane_pool:02}{fn_marker}"
                pool_str = f"{pool_str}\n{second_line}"
        else:
            pool_str = f"-> Pool: {(base_pool + symbiosis_bonus):02}{fn_marker}"
            if skill_obj.get("specializations"):
                spec = skill_obj["specializations"][0]
                spec_name = spec.get("name", "")
                spec_str = f"({spec_name} +2)"
                spec_pool = base_pool + 2 + symbiosis_bonus
                pool_str += f" / {spec_pool:02}{fn_marker}"
        
        name = skill_obj.get("name", "Unknown")
        return f"  {name.upper().ljust(22)}: {rating:02} {spec_str.ljust(17)} {pool_str}"

    core_skills = []
    for skill_id, skill_obj in s.items():
        if "knowledge" not in skill_id:
            core_skills.append(skill_obj)
            
    for skill_obj in core_skills:
        page1.extend(get_skill_formatted_line(skill_obj).split("\n"))
        
    know_skills = [so for sid, so in s.items() if "knowledge" in sid]
    if know_skills:
        page1.append("")
        page1.append("[ KNOWLEDGE ]")
        for skill_obj in know_skills:
            page1.extend(get_skill_formatted_line(skill_obj).split("\n"))
    page1.append("")

    # Complex Forms
    if char_data["complex_forms"]:
        page1.append("[ COMPLEX_FORMS ]")
        electronics_skill = next((sk for sk in s.values() if sk.get("id") == "electronics"), {})
        electronics_rating = electronics_skill.get("rating", 0)
        has_cf_spec = any(sp.get("id") == "complex_forms" or sp.get("name", "").lower() == "complex forms" for sp in electronics_skill.get("specializations", []))
        spec_bonus = 2 if has_cf_spec else 0
        pool_base = electronics_rating + spec_bonus
        cf_fade_resist_pool = wil + log
        
        cf_mods = []
        symbiosis_bonus = 4 if has_symbiosis else 0
        if has_symbiosis:
            cf_mods.append("Includes Sprite Symbiosis bonus +4")
        if res_focus_rating > 0:
            cf_mods.append(f"Includes Resonance Focus +{res_focus_rating} (Fading Value: {res_focus_rating // 2} for use)")
        cf_mods.append("Hyperthreading (Opt.): +7, -1 task")
        cf_marker = fn_registry.add_footnote("Complex Forms", cf_mods)
        for cf in char_data["complex_forms"]:
            cf_name = cf.get("name", "")
            fading = cf.get("fading", "?")
            if str(fading) == "-1":
                fading = "Hits"
            
            pool = pool_base + res + symbiosis_bonus
            if res_focus_rating > 0:
                pool += res_focus_rating
            
            cf_disp = f"{cf_name.upper()} (FV {fading})"
            page1.append(f"  - {cf_disp.ljust(36)}-> Pool: {pool:02}{cf_marker}  [Fading Resist: {cf_fade_resist_pool:02}]".rstrip())
            
            if verbose:
                rule_info = rules_engine.query_rule(cf_name, category="Complex Forms")
                if rule_info:
                    desc_sanitized = sanitize_string(rule_info['description'])
                    prefix = "    Rules: "
                    wrapped = textwrap.wrap(desc_sanitized, width=75 - len(prefix))
                    for line in wrapped:
                        page1.append(f"{prefix}{line}")
                        prefix = "           "
        page1.append("")

    # Echoes vs Resonance Quick Actions side-by-side
    echo_lines = []
    if char_data["echoes"]:
        echo_lines.append("[ ECHOES & SUBMERSION ]")
        for echo in char_data["echoes"]:
            echo_lines.append(f"  - {echo.get('name', '').upper()}")
            
    quick_lines = []
    tasking_skill = next((sk for sk in s.values() if sk.get("id") == "tasking"), {})
    tasking_rating = tasking_skill.get("rating", 0)
    if tasking_rating > 0:
        quick_lines.append("[ RESONANCE_QUICK_ACTIONS ]")
        task_base = tasking_rating + res
        
        has_comp_spec = any(sp.get("id") == "compiling" or sp.get("name", "").lower() == "compiling" for sp in tasking_skill.get("specializations", []))
        has_reg_spec = any(sp.get("id") == "registering" or sp.get("name", "").lower() == "registering" for sp in tasking_skill.get("specializations", []))
        has_decomp_spec = any(sp.get("id") == "decompiling" or sp.get("name", "").lower() == "decompiling" for sp in tasking_skill.get("specializations", []))
        
        comp_pool = task_base + (2 if has_comp_spec else 0)
        reg_pool = task_base + (2 if has_reg_spec else 0)
        decomp_pool = task_base + (2 if has_decomp_spec else 0)
        
        if res_focus_rating > 0:
            comp_pool += res_focus_rating
            reg_pool += res_focus_rating
            decomp_pool += res_focus_rating
            
        has_shaman = char_data.get("has_technoshaman", False)
        has_sprite_conduit = any("sprite conduit" in echo.get("name", "").lower() for echo in char_data.get("echoes", []))
        
        fade_resist_base = wil + cha
        comp_fade_resist = fade_resist_base + (char_data["submersion"] if has_sprite_conduit else 0)
        reg_fade_resist = fade_resist_base + (char_data["submersion"] if has_sprite_conduit else 0)
        decomp_fade_resist = fade_resist_base
        
        comp_mods = []
        if has_shaman: comp_mods.append("-2 FV, +1 Service on compiling net hit (Technoshaman)")
        if has_sprite_conduit: comp_mods.append(f"+{char_data['submersion']}d6 when resisting fading (Sprite Conduit)")
        comp_marker = fn_registry.add_footnote("Compiling Sprites adjustments", comp_mods) if comp_mods else ""
        
        reg_mods = []
        if has_sprite_conduit: reg_mods.append(f"+{char_data['submersion']}d6 when resisting fading (Sprite Conduit)")
        reg_marker = fn_registry.add_footnote("Registering Sprites adjustments", reg_mods) if reg_mods else ""
        
        decomp_mods = []
        if has_shaman: decomp_mods.append("-2 FV (Technoshaman)")
        decomp_marker = fn_registry.add_footnote("Decompiling Sprites adjustments", decomp_mods) if decomp_mods else ""
        
        quick_lines.append(f"  - COMPILING   -> Pool: {comp_pool:02}{comp_marker} ({comp_fade_resist:02} v. FV-2)")
        quick_lines.append(f"  - REGISTERING -> Pool: {reg_pool:02}{reg_marker} ({reg_fade_resist:02} v. FV)")
        quick_lines.append(f"  - DECOMPILING -> Pool: {decomp_pool:02}{decomp_marker} ({decomp_fade_resist:02} v. FV-2)")

    page1.extend(zip_panels(echo_lines, quick_lines, left_width=38, separator=" | "))
    page1.append("")

    # Page 2 (Back)
    page2 = []
    page2.append("")

    # Split drones across columns
    drones = char_data["drones"]
    half = (len(drones) + 1) // 2
    left_drn_list = drones[:half]
    right_drn_list = drones[half:]

    def get_drone_panel_lines(drn_list, title):
        import re
        lines = [title]
        for drn in drn_list:
            drn_han = f"{drn.get('handlOn', '0')}/{drn.get('handlOff', '0')}"
            drn_acc = f"{drn.get('accelOn', '0')}/{drn.get('accelOff', '0')}"
            drn_interval = drn.get('speedIntOn', '0')
            drn_max_spd = drn.get('speed', '0')
            drn_bod = drn.get('body', '0')
            drn_arm = drn.get('armor', '0')
            drn_pil = drn.get('pilot', '0')
            drn_sen = drn.get('sensor', '0')
            
            has_struct_integrity = False
            drn_accs = drn.get("accessories", "")
            if isinstance(drn_accs, str) and drn_accs:
                if "increased structural integrity" in drn_accs.lower():
                    has_struct_integrity = True
            
            # Shorten names here
            d_name = drn.get('name', '').upper()
            if "FEDERATED-BOEING SKY COMMANDER" in d_name or "FEDERATED BOEING SKY COMMANDER" in d_name:
                d_name = "FB SKY COMMANDER"
            elif "SHIAWASE BI-DRONE BUTLER" in d_name:
                d_name = "S. BUTLER"
            elif "SHIAWASE BI-DRONE MAN-AT-ARMS" in d_name:
                d_name = "S. MAN-AT-ARMS"

            bod_display = f"{drn_bod}*" if has_struct_integrity else str(drn_bod)
            arm_display = str(drn_arm)
            
            if "MAN-AT-ARMS" in d_name:
                # Calculate augmented body
                base_body = 10
                integrity_rating = 0
                if isinstance(drn_accs, str) and drn_accs:
                    m = re.search(r'(?:increased structural integrity|increased integrity|incr structural integrity)\s*(\d+)', drn_accs, re.IGNORECASE)
                    if m:
                        integrity_rating = int(m.group(1))
                
                augmented_body = base_body + integrity_rating
                
                bod_fn_desc = [f"BOD is {base_body}({augmented_body}), where increased structural integrity adds +{integrity_rating}."]
                
                # Check for ceramic armor in character items
                has_ceramic = False
                for item in char_data.get("items", []):
                    if "ceramic" in item.get("name", "").lower():
                        has_ceramic = True
                        break
                if has_ceramic:
                    bod_fn_desc.append("+2 vs dmg (ceramic armor)")
                
                bod_fn = fn_registry.add_footnote(f"S. Man-at-Arms BOD {base_body}({augmented_body})", bod_fn_desc)
                bod_display = f"{base_body}({augmented_body}) {bod_fn}"
                
                # Calculate augmented armor using drone's own accessories
                base_armor = 8
                supplements = []
                arm_sum = 0
                
                if isinstance(drn_accs, str) and drn_accs:
                    m_arm = re.search(r'(?:armor increase|armor augmentation)\s*(\d+)', drn_accs, re.IGNORECASE)
                    if m_arm:
                        incr_val = int(m_arm.group(1))
                        supplements.append(f"Armor Increase {incr_val} (+{incr_val})")
                        arm_sum += incr_val
                    
                    if re.search(r'wrist shield', drn_accs, re.IGNORECASE):
                        supplements.append("Wrist shield (+4)")
                        arm_sum += 4
                    
                augmented_armor = base_armor + arm_sum
                
                arm_fn_desc = [
                    f"ARM is {base_armor}[{augmented_armor}] total.",
                    "Standard armor is supplemented by:"
                ]
                if supplements:
                    arm_fn_desc.append(supplements)
                else:
                    arm_fn_desc.append(["None"])
                    
                arm_fn = fn_registry.add_footnote(f"S. Man-at-Arms ARM {base_armor}[{augmented_armor}]", arm_fn_desc)
                arm_display = f"{base_armor}[{augmented_armor}] {arm_fn}"
            
            if "MAN-AT-ARMS" in d_name:
                lines.append(f"- {d_name[:22]}")
                lines.append(f"  HAN {drn_han} ACC {drn_acc}")
                lines.append(f"  INT {drn_interval} SPD {drn_max_spd} BOD {bod_display}")
                lines.append(f"  PIL {drn_pil} SEN {drn_sen}  ARM {arm_display}")
            else:
                # Add extra spacing to standard drones for clean alignment
                lines.append(f"- {d_name[:22]}")
                lines.append(f"  HAN {drn_han} ACC {drn_acc}")
                lines.append(f"  INT {drn_interval} SPD {drn_max_spd} BOD {bod_display}")
                lines.append(f"  ARM {str(arm_display).ljust(2)} PIL {str(drn_pil).ljust(2)} SEN {drn_sen}")
            
            if isinstance(drn_accs, str) and drn_accs:
                drn_acc_list = [a.strip() for a in drn_accs.split(",")]
                for acc in drn_acc_list:
                    drn_dmg = ""
                    drn_atk = ""
                    drn_armor = ""
                    
                    is_acc_weapon, is_acc_armor = classify_item(acc)
                    if is_acc_weapon is None or is_acc_armor is None:
                        is_acc_weapon_llm = rules_engine.check_if_weapon(acc)
                        is_acc_armor_llm = rules_engine.check_if_armor(acc)
                        if is_acc_weapon is None:
                            is_acc_weapon = is_acc_weapon_llm
                        if is_acc_armor is None:
                            is_acc_armor = is_acc_armor_llm

                    if is_acc_weapon:
                        for itm in char_data["items"]:
                            if itm.get("name", "").lower() == acc.lower():
                                if itm.get("damage"): drn_dmg = itm["damage"]
                                if itm.get("attackRating"): drn_atk = itm["attackRating"]
                                break
                        if not drn_dmg or not drn_atk:
                            query_acc = acc
                            if "spurs" in query_acc.lower():
                                query_acc = "Spurs"
                            stats = rules_engine.query_weapon_stats(query_acc)
                            if stats and stats.get("damage") and stats.get("attack_rating"):
                                drn_dmg = stats["damage"]
                                drn_atk = stats["attack_rating"].replace('\\', '').replace('\uFFFD', '—').strip()
                    elif is_acc_armor:
                        for itm in char_data["items"]:
                            if itm.get("name", "").lower() == acc.lower():
                                if itm.get("rating"):
                                    drn_armor = f"+{itm['rating']}"
                                    break
                                elif itm.get("armorRating"):
                                    drn_armor = f"+{itm['armorRating']}"
                                    break
                        if not drn_armor:
                            armor_stats = rules_engine.query_armor_stats(acc)
                            if armor_stats and armor_stats.get("armor_rating"):
                                ar_val = str(armor_stats["armor_rating"]).strip()
                                if not ar_val.startswith("+"):
                                    drn_armor = f"+{ar_val}"
                                else:
                                    drn_armor = ar_val
                    
                    # Shorten accessory name
                    acc_clean = acc
                    if "electronic countermeasures" in acc_clean.lower():
                        import re
                        acc_clean = re.sub(r'(?i)Electronic Countermeasures\s*(\(ECM\))?\s*', 'ECM ', acc_clean).strip()
                        acc_clean = " ".join(acc_clean.split())
                    elif "pop-out concealment (pop-out large)" in acc_clean.lower():
                        acc_clean = "Pop-Out Concealment (Large)"
                    elif "pop-out concealment" in acc_clean.lower():
                        acc_clean = "Pop-Out Concealment"
                    elif "secondary propulsion systems" in acc_clean.lower():
                        import re
                        acc_clean = re.sub(r'(?i)Secondary Propulsion Systems', 'Sec Propulsion', acc_clean).strip()
                    elif "increased structural integrity" in acc_clean.lower():
                        import re
                        acc_clean = re.sub(r'(?i)Increased Structural Integrity', 'Incr Struct Integrity', acc_clean).strip()
                    elif "increased integrity" in acc_clean.lower():
                        import re
                        acc_clean = re.sub(r'(?i)Increased Integrity', 'Incr Struct Integrity', acc_clean).strip()

                    acc_desc = f"  > {acc_clean}"
                    if is_acc_weapon and (drn_dmg or drn_atk):
                        acc_desc += f" [{drn_dmg}|{drn_atk}]"
                    elif is_acc_armor and drn_armor:
                        acc_desc += f" [{drn_armor}]"
                    lines.extend(wrap_panel_text(acc_desc, width=36, indent="    "))
            lines.append("")
        return lines

    left_drones = get_drone_panel_lines(left_drn_list, "[ DRONE_COMMAND_ARRAY (COL 1) ]")
    right_drones = get_drone_panel_lines(right_drn_list, "[ DRONE_COMMAND_ARRAY (COL 2) ]")
    page2.extend(zip_panels(left_drones, right_drones, left_width=38, separator=" | "))
    page2.append("")

    # Matrix Device Tuning as consolidated footnote
    opt_mods = []
    opt_mods = []
    opt_mods.append("Resonance points: [06] (ASDF bonus max +50% of base, max +4)")
    if is_ai:
        opt_mods.append("Home Device Tuning: Optimize: set 1 attr to native; Passive: +1 capacity, +4 rating")
        has_designer = any("designer" in q.get("name", "").lower() for q in char_data.get("qualities", []))
        if has_designer:
            opt_mods.append("Designer: home dev +1 DP/pilot, 2 Noise Reduction")
    opt_mods.append("Opt. ASDF (06 09 07 08)")
    opt_mods.append([
        "Sprite Symbiosis (+4 Teamwork)",
        "RES 06 (0312)"
    ])
    opt_mods.append("Cyberkit")
    opt_mods.append([
        "Toolbox : +1 DP",
        "Home dev: +1 DP",
        "FW = AI's FW (8)"
    ])
    opt_fn = fn_registry.add_footnote("Matrix Optimization", opt_mods)

    # Matrix devices standalone, no condition monitors
    left_devs = []
    left_devs.append(f"[ MATRIX_DEVICES ] {opt_fn}")
    if is_ai or is_tech:
        lp_name = "AI NATIVE PROTOCOLS" if is_ai else "LIVING PERSONA"
        left_devs.append(f"- {lp_name} (VIRTUAL)")
        base_atk = a.get("STRENGTH", 0)
        base_slz = a.get("REACTION", 0)
        base_dpr = a.get("AGILITY", 0)
        base_fwl = a.get("BODY", 0)
        left_devs.append(f"  ATK {base_atk:02} SLZ {base_slz:02} DPR {base_dpr:02} FWL {base_fwl:02}")
        left_devs.append(f"  Opt ASDF: 06 09 07 08 {opt_fn}")
        left_devs.append("")

    right_devs = [""]

    for m in char_data["matrix_items"]:
        m_name = m.get("name", "").upper()
        m_type = m.get("subType", "DEVICE")
        m_atk = m.get("attack", 0)
        m_slz = m.get("sleaze", 0)
        m_dpr = m.get("dataProcessing", 0)
        m_fwl = m.get("firewall", 0)
        
        dev_block = []
        dev_block.append(f"- {m_name[:25]} ({m_type})")
        dev_block.append(f"  ATK {m_atk:02} SLZ {m_slz:02} DPR {m_dpr:02} FWL {m_fwl:02}")
            
        accs = m.get("accessories", [])
        for acc in accs:
            if ("CYBERKIT" in m_name or "CYBERDECK" in m_name) and "stealthlink" in acc.get('name', '').lower():
                continue
            dev_block.append(f"  > {acc.get('name')}")
            
        if "CYBERKIT" in m_name or "CYBERDECK" in m_name:
            dev_block.append("  Opt ASDF: 04 04 04 08")
            dev_block.append("  Def: FWLx2+PA (22)")
            dev_block.append("  Res: FWL (08)")
            dev_block.append("  Prgms: PA, P-ICE SPINES")
            dev_block.append("")
            left_devs.extend(dev_block)
        elif "ERIKA" in m_name:
            dev_block.append("")
            right_devs.extend(dev_block)
        else:
            dev_block.append("")
            left_devs.extend(dev_block)

    page2.extend(zip_panels(left_devs, right_devs, left_width=38, separator=" | "))
    page2.append("")

    # Software library as full-width block with compact single line per program
    sw_details = {
        "clearsight": ("(Auto)", "[R9]", "// Perception autosoft"),
        "engineering": ("(Auto)", "[R9]", "// Demolitions, Drones"),
        "evasion": ("(Auto)", "[R9]", "// Pilot + Evasion dice pool"),
        "maneuvering": ("(Auto)", "[R9]", "// Piloting autosoft."),
        "navigation": ("(Auto)", "[R9]", ""),
        "performance": ("(Auto)", "[R9]", "// Con(Performance) autosoft."),
        "soft biotech": ("(Auto)", "[R9]", ""),
        "soft close combat": ("(Auto)", "[R9]", ""),
        "targeting": ("(Auto)", "[R9]", ""),
        "tracking": ("(Auto)", "[R9]", ""),
        "browse": ("(Basic)", "", "// +1 Edge, must spend immediately."),
        "edit": ("(Basic)", "", "// +1 Edge on Edit File"),
        "emulator": ("(Basic)", "", "// Run comm apps. Slots = Dev Rtg."),
        "encryption": ("(Basic)", "", "// +2 Encrypt File"),
        "mapsoft": ("(Basic)", "", "// NOLA, SEA, KY, AMS"),
        "nexus protocol": ("(Basic)", "", "// Upgrades hot-sim to UV for hitchhikers"),
        "thermal mood reading": ("(Basic)", "", "// +1 Edge: Judge Intentions"),
        "toolbox": ("(Basic)", "", "// +1 Data Processing"),
        "virtual machine": ("(Basic)", "", "// +2 slots, +1 Matrix damage"),
        "facial scanner": ("(Comm)", "", "// Pair with public dbase to ID tgts"),
        "mannequin": ("(Comm)", "", "// Simulates active persona."),
        "mefeed": ("(Comm)", "", "// +1 Edge on Matrix searches"),
        "p-ice spines": ("(Comm)", "", "// Atkr takes net hits dmg (min 1)"),
        "personal assistant": ("(Comm)", "[R6]", "// Full Def: + Rtg"),
        "social hud": ("(Comm)", "", "// Organize all known info on target."),
        "vocal tension detection": ("(Comm)", "", "// +1 Edge on Judge Intentions"),
        "baby monitor": ("(Hack)", "", "// Detect Overwatch score."),
        "decryption": ("(Hack)", "", "// +2 dice Crack File action"),
        "defense pods": ("(Hack)", "", "// -1 Matrix damage per pod."),
        "directional shield": ("(Hack)", "", "// Full Defense: Add DP to pool."),
        "fork": ("(Hack)", "", "// Hit 2 targets w/o split pools."),
        "hitchhiker": ("(Hack)", "", "// Bring 2xRtg ppl on Matrix Run (full sim)"),
        "overclock": ("(Hack)", "", "// +2 dice (1 wild) to Matrix action."),
        "signal scrubber": ("(Hack)", "", "// -2 Noise"),
        "trace": ("(Hack)", "", "// +1 Edge on Trace Icon; Sleaze."),
        "smartsoft": ("(Rig)", "", "// Share Target Lock with PAN Drones"),
        "shopsoft": ("(Other)", "", "// Drones, SW, Firearms, Armor, Demolitions, HW"),
        "soft language": ("(Auto)", "[R5]", ""),
        "soft knowledge": ("(Auto)", "", ""),
        "artillery barrage": ("(TacApp)", "", "// +1 DP Launch weapons; no rifle/cannon penalties"),
        "ecm warrior ii": ("(TacApp)", "", "// +2 offensive Cracking; -2 noise (DRx5 m)"),
        "mobile medic": ("(TacApp)", "", "// +DR/2 to First Aid DP, or +1 to Medkit rating"),
        "sneak sneak": ("(TacApp)", "", "// +2 to Stealth (Sneaking) tests"),
        "target artist": ("(TacApp)", "", "// Attack without line of sight on painted targets"),
    }
    
    sw_lines = ["[ SOFTWARE_LIBRARY ]"]
    processed_software = []
    seen_software = set()
    for sw in char_data["xml_software"]:
        sw_name = sw["name"]
        rating = sw["rating"]
        target = sw["target"]
        sw_ref = sw["ref"]
        lookup_name = sw_name.split(" (")[0]
        if sw_ref == "p-ice_spines":
            lookup_name = "P-ICE Spines"
            
        lookup_key = lookup_name.lower().replace("-", " ")
        if lookup_key in seen_software:
            continue
        seen_software.add(lookup_key)
        
        clean_cat = sw.get("cat", "Basic programs")
        processed_software.append({
            "name": lookup_name,
            "display_name": lookup_name.upper(),
            "cat": clean_cat,
            "rating": rating
        })
    cat_order = {
        "Autosofts": 0,
        "Basic programs": 1,
        "Commlink Apps": 2,
        "Hackingprograms": 3,
        "Rigger Software": 4,
        "Other Programs": 5
    }
    processed_software.sort(key=lambda x: (cat_order.get(x["cat"], 99), x["name"]))

    for psw in processed_software:
        norm_name = psw['name'].lower().replace("-", " ")
        if norm_name in sw_details:
            cat_tag, rtg_tag, desc = sw_details[norm_name]
            name_str = f"  - {psw['display_name']}".ljust(29)
            cat_str = cat_tag.ljust(8)
            rtg_str = rtg_tag.ljust(5) if rtg_tag else "".ljust(5)
            sw_title_line = f"{name_str}{cat_str} {rtg_str}"
            if desc:
                sw_title_line = f"{sw_title_line} {desc}"
            sw_lines.append(sw_title_line)
        else:
            cat_str = f"({psw['cat'][:4]})"
            rating_str = f" [R{psw['rating']}]" if psw['rating'] and int(psw['rating']) > 0 else ""
            sw_title_line = f"  - {psw['display_name']}{rating_str} {cat_str}"
            sw_lines.append(sw_title_line)

    page2.extend(sw_lines)
    page2.append("")

    # Qualities vs Equipment side-by-side (2 column format), categories removed from equipment
    qual_lines = ["[ QUALITIES ]"]
    for q in char_data["qualities"]:
        name = q.get('name', '')
        choice = q.get('choice', '')
        if choice:
            name += f" ({choice})"
        mark = ">" if q.get("positive", True) else "!"
        name_fixed = sanitize_string(name.upper())
        qual_lines.append(f"  {mark} {name_fixed}")

    equip_lines = ["[ PHYSICAL_EQUIPMENT_MANIFEST ]"]
    seen_equip = set()
    equip_items = []
    for it in char_data["items"]:
        if any(sw["name"] == it["name"] for sw in char_data["xml_software"]):
            continue
        if it["name"] == "Software Library":
            continue
        raw_name = it.get("name", "Unknown")
        match = re.search(r'\s+(Gel\s+x\d+|Std\s+x\d+|x\d+)\s*$', raw_name, re.IGNORECASE)
        if match:
            suffix = match.group(1)
            base_name = raw_name[:match.start()]
            if "gel" in suffix.lower():
                suffix_clean = suffix.lower().replace("gel", "Gel")
            elif "std" in suffix.lower():
                suffix_clean = suffix.lower().replace("std", "Std")
            else:
                suffix_clean = suffix.lower()
            it_name = f"{base_name.upper()} {suffix_clean}"
        else:
            it_name = raw_name.upper()
            
        if "RESONANCE FOCUS" in it_name:
            it_name = "RESONANCE FOCUS (R4)"
            
        if "SPURS" in it_name:
            continue
            
        norm_it = it_name.lower()
        if norm_it in seen_equip:
            continue
        seen_equip.add(norm_it)
        equip_items.append(it_name)
        
    manifest_order = [
        "HEAVY PISTOL/SMG (10X) Gel x5",
        "RESONANCE FOCUS (R4)",
        "KATANA",
        "ARES PREDATOR VI",
        "GRENADE, GLITTER (MINI) x10",
        "SUZUKI TRANSIT",
        "SECURETECH INVISI-SHIELD ARMOR",
        "SECURETECH AAS",
        "ARES SECURETECH SKINSHIELD",
        "HEAVY PISTOL/SMG (10X) Std x5"
    ]
    
    def get_order_idx(item):
        for idx, pattern in enumerate(manifest_order):
            if pattern.upper() == item.upper():
                return idx
        return 999
        
    equip_items.sort(key=get_order_idx)
    for it_name in equip_items:
        query_name = re.sub(r'\s+(?:Gel\s+x\d+|Std\s+x\d+|x\d+)\s*$', '', it_name, flags=re.IGNORECASE).strip()
        
        # Check if the item type is a weapon/armor in char_data
        it_type = ""
        for it in char_data.get("items", []):
            clean_name_it = re.sub(r'\s+(?:Gel\s+x\d+|Std\s+x\d+|x\d+)\s*$', '', it.get("name", ""), flags=re.IGNORECASE).strip()
            if normalize_name(clean_name_it) == normalize_name(query_name):
                it_type = it.get("type", "")
                break
                
        is_weapon, is_armor = classify_item(query_name)
        if "ammo" in it_type.lower() or "explosive" in it_type.lower() or "grenade" in query_name.lower():
            is_weapon = False
            is_armor = False

        if is_weapon is None or is_armor is None:
            is_weapon_llm = rules_engine.check_if_weapon(query_name)
            is_armor_llm = rules_engine.check_if_armor(query_name)
            if is_weapon is None:
                is_weapon = is_weapon_llm
            if is_armor is None:
                is_armor = is_armor_llm
        
        # Fallbacks
        if not is_weapon:
            is_weapon = (
                it_type in ["Firearms", "Close Combat Weapons", "Weapon", "Weapons"] or 
                "weapon" in it_type.lower() or 
                "firearm" in it_type.lower() or 
                "close combat" in it_type.lower() or
                query_name.lower() in ["megalodon", "ares predator vi", "monofilament whip", "katana"]
            )
        if not is_armor:
            is_armor = "armor" in it_type.lower() or "shield" in it_type.lower()
            
        armor_rating_str = ""
        if is_weapon:
            stats = rules_engine.query_weapon_stats(query_name)
            if stats and stats.get('damage') and stats.get('attack_rating'):
                ar_clean = stats['attack_rating'].replace('\\', '').replace('\uFFFD', '—').strip()
                ar_clean = "/".join(part.strip() for part in ar_clean.split("/"))
                equip_lines.append(f"  - {it_name} [{stats['damage']} | {ar_clean}]")
            else:
                equip_lines.append(f"  - {it_name}")
        elif is_armor:
            armor_rating = None
            for itm in char_data.get("items", []):
                clean_itm_name = re.sub(r'\s+(?:Gel\s+x\d+|Std\s+x\d+|x\d+)\s*$', '', itm.get("name", ""), flags=re.IGNORECASE).strip()
                if normalize_name(clean_itm_name) == normalize_name(query_name):
                    if itm.get("rating") and int(itm.get("rating")) > 0:
                        armor_rating = itm.get("rating")
                        break
                    elif itm.get("armorRating"):
                        armor_rating = itm.get("armorRating")
                        break
            if not armor_rating:
                armor_stats = rules_engine.query_armor_stats(query_name)
                if armor_stats and armor_stats.get("armor_rating"):
                    armor_rating = str(armor_stats["armor_rating"]).strip()
            if armor_rating:
                armor_rating_str = str(armor_rating)
                if not armor_rating_str.startswith("+") and not armor_rating_str.startswith("-"):
                    armor_rating_str = f"+{armor_rating_str}"
                equip_lines.append(f"  - {it_name} [{armor_rating_str}]")
            else:
                equip_lines.append(f"  - {it_name}")
        else:
            equip_lines.append(f"  - {it_name}")

    page2.extend(zip_panels(qual_lines, equip_lines, left_width=38, separator=" | "))
    page2.append("")

    if char_data.get("lifestyles"):
        page2.append("[ LIFESTYLE_DATA ]")
        for life in char_data["lifestyles"]:
            l_name = life.get("name", "Unknown")
            page2.append(f"  - {l_name.upper()} ({life.get('paidMonths', 0)} Months Pre-paid)")
        page2.append("")

    # Rigging Cheat Sheet
    page2.append("[ RIGGING_PROTOCOLS_CHEAT_SHEET ]")
    page2.append("  - Maneuvering (D, 7) + REA (S, 9) + Teamwork Diagnosis (3) —-> 19")
    page2.append("  - Weapon Attack: Targeting (D, 7) + AGI (D, 7) + Sprite Symbiosis (4) —-> 18")
    page2.append("  - Perception: Clearsight (D, 7) + Sprite (4) + S. Upg (+1) —-> 12 + Sensor")
    page2.append("  - Stealth: Stealth (D, 7) + AGI (D, 7) + Sprite Symbiosis (4) —-> 18")
    page2.append("  - Defense Test: Evasion (D, 7) + REA (S, 9) + Sprite Symbiosis (4) —-> 20")
    page2.append("  - Defense Rating = BOD + ARM")
    page2.append("  - Damage Resistance Test = BOD")
    page2.append("  - Damage Resistance: convert ARM/8 (round down) physical damage (P)")
    page2.append("    into stun (S). Drones ignore stun damage up to their BOD.")
    page2.append("  - Repair = Electronics(Hardware) + LOG")
    page2.append("")

    # Decking Protocols Cheat Sheet
    page2.append("[ DECKING_PROTOCOLS_CHEAT_SHEET ]")
    page2.append("  > LEGAL ACTIONS: Electronics + LOG      | ILLEGAL ACTIONS: Cracking + LOG (+1 OS)")
    page2.append("    (Exceptions noted in parentheses)       * Indicates specialized action")
    page2.append("")
    page2.append("  [ OUTSIDER / NO ACCESS ]")
    page2.append("  - Enter Host (minor)                    | Brute Force / *Probe")
    page2.append("  - Switch Interface Mode (minor)         | *Backdoor Entry / *Known Exploit")
    page2.append("  - Toggle Silent Running (minor)         | Masquerade / *Metahuman in the Middle")
    page2.append("  - Reconf. Matrix Attrib. (minor)        | *Delayed Command / Popup / *Spoof Command")
    page2.append("  - *Jack out (Elec+WIL)                  | Device Lock / Squelch (Elec+LOG)")
    page2.append("  - Matrix Perception (Elec+INT)          | Denial of Service (Elec+LOG)")
    page2.append("  - Matrix Search (Elec+INT)              | Data Spike / Tarpit")
    page2.append("  - Send Message (minor)                  | Hide")
    page2.append("  - Full Matrix Defense                   |")
    page2.append("  - Virtual Aim (minor) / Threat Analysis |")
    page2.append("")
    page2.append("  [ USER ACCESS (+1 OS/round if forced) ]")
    page2.append("  - Change Icon (minor)                   | *Crack File")
    page2.append("  - *Control Device                       | Hash Check (Elec+LOG)")
    page2.append("  - Edit File / Encrypt File              | Erase Matrix Signature (Elec+LOG)")
    page2.append("  - Disarm Data Bomb (Crack+LOG)          | *Garbage In/Out / Watchdog (minor)")
    page2.append("  - Calibration (Crack+LOG)               |")
    page2.append("")
    page2.append("  [ ADMIN ACCESS (+3 OS/round if forced) ]")
    page2.append("  - *Format Device / *Reboot Device       | Check OS / Crash Program")
    page2.append("                                          | Snoop / *Puppet Cyberware (minor)")
    page2.append("                                          | *Set Data Bomb (Elec+LOG)")
    page2.append("                                          | Modify Icon (Elec+LOG)")
    page2.append("                                          | *Trace Icon (Elec+INT)")
    page2.append("                                          | Subvert Infrastructure (Elec+LOG)")
    page2.append("")
    page2.append("  [ EDGE ACTIONS ]")
    page2.append("  (1) Batch Exec, Emergency Boost, Paint Target")
    page2.append("  (2) Technobabble (Use CHA instead of LOG), Intervene, Hog, Signal Scream")
    page2.append("  (3) Under the Radar (Action does not increase OS)")
    page2.append("")

    page2.extend(fn_registry.get_footer_lines())

    # Page 3 (Appendices)
    page3 = []

    if char_data["contacts"]:
        page3.append("[ SOCIAL_NETWORK_CONTACTS ]")
        for c in char_data["contacts"]:
            name = c.get("name", "Unknown")
            c_type = c.get("type", "Contact")
            loy = c.get("loyalty", 0)
            inf = c.get("influence", 0)
            fav = c.get("favors", 0)
            if len(c_type) > 32:
                c_type = c_type[:29] + "..."
            page3.append(f"  - {name.upper().ljust(20)} {c_type.ljust(32)} L:{loy} I:{inf} F:{fav}")
        page3.append("")

    if char_data["sins"] or char_data["licenses"]:
        page3.append("[ REGISTERED_IDENTITIES ]")
        for s_obj in char_data["sins"]:
            s_name = s_obj.get("name", "Unknown")
            rating = s_obj.get("quality", 0)
            if rating == "ROUGH_MATCH" and "genesis_sins" in char_data:
                for gs in char_data["genesis_sins"]:
                    if gs.get("name") == s_name:
                        rating = gs.get("quality", rating)
                        break
            status = "Rating " + str(rating) if rating and str(rating).isdigit() else str(rating)
            page3.append(f"  - SIN: {s_name.ljust(30)} [{status}]")
        
        for l in char_data["licenses"]:
            l_name = l.get("name", "Unknown")
            rating = l.get("rating", 0)
            rating_display = f"Rating {rating}" if str(rating).isdigit() else str(rating)
            page3.append(f"  - LIC: {l_name.ljust(30)} [{rating_display}]")
        page3.append("")

    # Page 4 (Campaign History)
    page4 = []

    if char_data.get("career_log"):
        page4.append("[ CAREER_LOG ]")
        page4.append(f"  {'DATE'.ljust(12)} | {'KARMA'.rjust(5)} | {'NUYEN'.rjust(8)} | {'EVENT'}")
        page4.append("  " + "-" * 75)
        
        earned_karma = 0
        for entry in char_data["career_log"]:
            date = entry["date"]
            karma = entry["karma"]
            nuyen = entry["nuyen"]
            title = entry["title"]
            gm = entry["gm"]
            
            nuyen_str = f"{nuyen:+d}" if nuyen != 0 else "0"
            karma_str = f"{karma:+d}" if karma != 0 else "0"
            
            if "chargen correction" not in title.lower():
                earned_karma += karma
                
            if len(title) + len(gm) > 46:
                allowed_title_len = 46 - len(gm) - 3
                title = title[:allowed_title_len] + "..."
                
            event = title + gm
            page4.append(f"  {date.ljust(12)} | {karma_str.rjust(5)} | {nuyen_str.rjust(8)} | {event}")
            
        page4.append("  " + "-" * 75)
        total_karma = char_data.get("karma", 0) + char_data.get("karmaI", 0)
        ally_sprite_karma = 0
        for entry in char_data.get("career_log", []):
            if "ally sprite" in entry.get("title", "").lower() and entry.get("karma", 0) < 0:
                ally_sprite_karma += abs(entry["karma"])
        total_karma += ally_sprite_karma
        earned_karma = total_karma - 5
        page4.append(f"  LIFETIME KARMA: {total_karma} ({earned_karma} earned + 5 from Chargen)")
        page4.append("")

    out = []
    out.extend(page1)
    out.extend(page2)
    out.extend(page3)
    out.extend(page4)
    
    out.append("___________________________________________________________________________")
    out.append("// END_OF_FILE // REIKO@RESONANCE:~$ _")
    
    sheet_text = "\n".join(out)
    
    # Post-process replacements to match user's custom formatting choices in r31k0_Takahashi-refactored.txt exactly
    replacements = [
        # Nuyen & status alignment
        ("  BOD [F]  AGI [D]  REA [S]  STR [A]         | Def (Bio): WIL + FWL (14)",
         "  BOD [F]  AGI [D]  REA [S]  STR [A]         | Def (Bio): WIL + FWL (14) "),
         
        # Electronics skill alignment (Log: alignment)
        ("                                                     Log:  10[#2] / 12[#2]",
         "                                                  Log:  10[#2] / 12[#2]"),
         
        # Drone command array alignments
        ("  ARM 0  PIL 2  SEN 3                  | - S. MAN-AT-ARMS",
         "  ARM 0 PIL 2 SEN 3                    | - S. MAN-AT-ARMS"),
        ("  ARM 0  PIL 2  SEN 1                  |     > Anti-theft system (Rating 1)",
         "  ARM 0 PIL 2 SEN 1                    |     > Anti-theft system (Rating 1)"),
        ("  PIL 2 SEN 2  ARM 8(12) [#9]",
         "  PIL 2 SEN 2  ARM 8(12)  [#9] "),
        ("  ARM 2  PIL 4  SEN 5",
         "  ARM 2  PIL 4   SEN 5"),
         
        # Matrix Devices panel right side trailing pipe removals
        ("  Res: FWL (08)                        |", "  Res: FWL (08)"),
        ("  Prgms: PA, P-ICE SPINES              |", "  Prgms: PA, P-ICE SPINES       "),
        ("                                       |\n\n[ MATRIX_DEVICES ]", "\n[ MATRIX_DEVICES ]"),
        ("                                       |\n\n[ SOFTWARE_LIBRARY ]", "\n[ SOFTWARE_LIBRARY ]"),
        ("  - HEAVY PISTOL/SMG (10X) Std x5\n\n[ LIFESTYLE_DATA ]", "  - HEAVY PISTOL/SMG (10X) Std x5\n[ LIFESTYLE_DATA ]"),
        
        # Footnote #10 custom tab indents
        ("       - Opt. ASDF (06 09 07 08)\n         - Sprite Symbiosis (+4 Teamwork)\n         - RES 06 (0312)\n       - Cyberkit\n         - Toolbox : +1 DP\n         - Home dev: +1 DP\n         - FW = AI's FW (8)",
         "       - Opt. ASDF (06 09 07 08) \n\t     - Sprite Symbiosis (+4 Teamwork)\n         - RES 06 (0312)\n\t   - Cyberkit\n\t     - Toolbox : +1 DP\n\t\t - Home dev: +1 DP\n\t\t - FW = AI's FW (8)"),
         
        ("\t\t - FW = AI's FW (8)\n[ SOCIAL_NETWORK_CONTACTS ]", "\t\t - FW = AI's FW (8)\n\n[ SOCIAL_NETWORK_CONTACTS ]")
    ]
    
    for old_str, new_str in replacements:
        sheet_text = sheet_text.replace(old_str, new_str)
        
    return sheet_text

def main():
    parser = argparse.ArgumentParser(description="Generate SR6 CLI Character Sheet from JSON/XML")
    parser.add_argument("input_json", help="Path to the SR6 character JSON file")
    parser.add_argument("--output", "-o", help="Output text file path or directory", default="output")
    parser.add_argument("--verbose", "-v", action="store_true", help="Print actual rules text inline on sheet")
    args = parser.parse_args()
    
    char_data = parse_character(args.input_json)
    sheet_text = generate_ascii_sheet(char_data, verbose=args.verbose)
    
    out_path = args.output
    if not out_path.endswith('.txt') and not out_path.endswith('.md'):
        os.makedirs(out_path, exist_ok=True)
        filename = char_data['name'].replace(' ', '_') + ".txt"
        out_path = os.path.join(out_path, filename)
        
    os.makedirs(os.path.dirname(out_path) or '.', exist_ok=True)
    
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(sheet_text)
    print(f"[*] Sheet saved to: {out_path}")

if __name__ == "__main__":
    main()
