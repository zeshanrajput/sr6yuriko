import os
import re
import json
import dotenv
from utils import normalize_name

INDEX_PATH = ".rules_index.json"

class RulesEngine:
    def __init__(self, vault_dir="rules_vault"):
        dotenv.load_dotenv()
        self.vault_dir = os.environ.get("RULES_VAULT_DIR", vault_dir)
        self.cache_index_path = os.environ.get("CACHE_INDEX_PATH", "cache_index.json")
        self.gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
        self.rules = {}  # key (normalized) -> rule info
        self.sub_items = {}  # key (normalized) -> sub-item info
        self.load_index()

    def parse_frontmatter_fast(self, content):
        if not content.startswith('---'):
            return None
        end_idx = content.find('---', 3)
        if end_idx == -1:
            return None
        fm_block = content[3:end_idx]
        
        fm = {}
        current_key = None
        for line in fm_block.split('\n'):
            line_strip = line.strip()
            if not line_strip:
                continue
            if ':' in line_strip and not line_strip.startswith('-'):
                parts = line_strip.split(':', 1)
                key = parts[0].strip()
                val = parts[1].strip()
                if val.startswith('[') and val.endswith(']'):
                    val = [v.strip().strip("'").strip('"') for v in val[1:-1].split(',')]
                elif val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                fm[key] = val
                current_key = key
            elif line_strip.startswith('-') and current_key:
                val = line_strip[1:].strip().strip("'").strip('"')
                if current_key not in fm or not isinstance(fm[current_key], list):
                    fm[current_key] = []
                fm[current_key].append(val)
        return fm

    def _get_namespaces(self, fm):
        namespaces = set()
        if not fm:
            return namespaces
            
        # Chapter
        ch = fm.get('chapter', '')
        if isinstance(ch, list):
            ch = " ".join(ch)
        if ch:
            namespaces.add(normalize_name(ch))
            
        # Topic
        tp = fm.get('topic', '')
        if isinstance(tp, list):
            tp = " ".join(tp)
        if tp:
            namespaces.add(normalize_name(tp))
            
        # Tags
        tags = fm.get('tags', [])
        if isinstance(tags, str):
            tags = [tags]
        for tag in tags:
            namespaces.add(normalize_name(tag))
            
        expanded = set()
        for ns in namespaces:
            if not ns:
                continue
            expanded.add(ns)
            if ns.endswith('s'):
                expanded.add(ns[:-1])
            else:
                expanded.add(ns + 's')
                
            # Domain mapping
            if ns in ['hacking', 'hackingprogram', 'hackingprograms']:
                expanded.update(['hacking', 'hackingprogram', 'hackingprograms'])
            if ns in ['autosoft', 'autosofts']:
                expanded.update(['autosoft', 'autosofts'])
            if ns in ['commlinkapp', 'commlinkapps', 'commlink']:
                expanded.update(['commlinkapp', 'commlinkapps', 'commlink'])
            if ns in ['riggerprogram', 'riggerprograms', 'rigging']:
                expanded.update(['riggerprogram', 'riggerprograms', 'rigging'])
                
        return expanded

    def load_index(self):
        if os.path.exists(INDEX_PATH):
            try:
                with open(INDEX_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.rules = data.get("rules", {})
                    self.sub_items = data.get("sub_items", {})
                    self.rules_all = data.get("rules_all", {})
                    self.sub_items_all = data.get("sub_items_all", {})
                    return
            except Exception:
                pass
        self.compile_index()

    def compile_index(self):
        self.rules = {}
        self.sub_items = {}
        self.rules_all = {}
        self.sub_items_all = {}
        if not os.path.exists(self.vault_dir):
            return

        pattern = r'\*\*([^*]+)\*\*\s*([^\n]+(?:\n(?!\*\*)[^\n]+)*)'

        for filename in os.listdir(self.vault_dir):
            if filename.endswith(".md"):
                filepath = os.path.join(self.vault_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Parse frontmatter
                fm = self.parse_frontmatter_fast(content)
                if not fm:
                    continue
                
                rule_id = fm.get('id', '')
                if isinstance(rule_id, list):
                    rule_id = " ".join(rule_id)
                topic = fm.get('topic', '')
                if isinstance(topic, list):
                    topic = " ".join(topic)
                source = fm.get('source', '')
                if isinstance(source, list):
                    source = " ".join(source)
                tags = fm.get('tags', [])
                
                try:
                    authority_level = int(fm.get('authority_level', 3))
                except Exception:
                    authority_level = 3

                end_idx = content.find('---', 3)
                body = content[end_idx+3:].strip() if end_idx != -1 else ""

                # Store rule mapping
                rule_info = {
                    'file': filepath,
                    'id': rule_id,
                    'topic': topic,
                    'source': source,
                    'tags': tags,
                    'body': body,
                    'authority_level': authority_level
                }

                if rule_id:
                    rid_norm = normalize_name(rule_id)
                    self.rules[rid_norm] = rule_info
                    if rid_norm not in self.rules_all:
                        self.rules_all[rid_norm] = []
                    self.rules_all[rid_norm].append(rule_info)
                if topic:
                    topic_norm = normalize_name(topic)
                    self.rules[topic_norm] = rule_info
                    if topic_norm not in self.rules_all:
                        self.rules_all[topic_norm] = []
                    self.rules_all[topic_norm].append(rule_info)

                namespaces = self._get_namespaces(fm)
                for ns in namespaces:
                    if rule_id:
                        self.rules[f"{ns}:{normalize_name(rule_id)}"] = rule_info
                    if topic:
                        self.rules[f"{ns}:{normalize_name(topic)}"] = rule_info

                # Search body for sub-items format: **Name:** Description
                for m in re.finditer(pattern, body):
                    raw_name = m.group(1).strip()
                    desc = m.group(2).strip()
                    if raw_name.endswith(':'):
                        name = raw_name[:-1].strip()
                        clean_key = normalize_name(name)
                        if len(clean_key) < 50:
                            sub_info = {
                                'name': name,
                                'description': desc,
                                'file': filepath,
                                'source': source,
                                'id': rule_id,
                                'authority_level': authority_level
                            }
                            # Traditional flat match
                            self.sub_items[clean_key] = sub_info
                            
                            # Scoped
                            for ns in namespaces:
                                self.sub_items[f"{ns}:{clean_key}"] = sub_info
                                
                            if clean_key not in self.sub_items_all:
                                self.sub_items_all[clean_key] = []
                            self.sub_items_all[clean_key].append(sub_info)

        # Cache to disk
        try:
            with open(INDEX_PATH, 'w', encoding='utf-8') as f:
                json.dump({
                    "rules": self.rules,
                    "sub_items": self.sub_items,
                    "rules_all": self.rules_all,
                    "sub_items_all": self.sub_items_all
                }, f)
        except Exception:
            pass

    def _load_cache(self):
        if hasattr(self, '_cache'):
            return self._cache
        self._cache = {}
        if os.path.exists(self.cache_index_path):
            try:
                with open(self.cache_index_path, 'r', encoding='utf-8') as f:
                    self._cache = json.load(f)
            except Exception:
                pass
        return self._cache

    def _save_cache(self):
        try:
            with open(self.cache_index_path, 'w', encoding='utf-8') as f:
                json.dump(self._cache, f, indent=2)
        except Exception:
            pass

    def _cloud_summarize(self, file_id, topic, body_content, max_chars=160):
        if not self.gemini_api_key:
            print(f"[DEBUG WARNING] GEMINI_API_KEY is not initialized. Falling back to standard truncation for {topic}.")
            return None
            
        cache_suffix = "short_summary" if max_chars <= 40 else "summary"
        cache_key = f"{file_id}:{cache_suffix}"
        cache = self._load_cache()
        if cache_key in cache:
            return cache[cache_key]
            
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self.gemini_api_key)
            tools = [
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=["fileSearchStores/shadowrun-6e-srm-vault-d31wtxa55r5l"]
                    )
                )
            ]
            
            if max_chars <= 40:
                system_instruction = (
                    "You are a compact data extraction utility for a Shadowrun 6th Edition rules database.\n"
                    "Analyze the provided markdown rule document. Extract and rewrite a precise, extremely short phrase focused strictly on game mechanics, modifiers, and dice pools.\n"
                    f"Do not include introductory flavor text or book citations. Keep the response under {max_chars} characters so it fits on a single line."
                )
            else:
                system_instruction = (
                    "You are a compact data extraction utility for a Shadowrun 6th Edition rules database.\n"
                    "Analyze the provided markdown rule document. Extract and rewrite a precise, 1-to-2 sentence summary focused strictly on game mechanics, modifiers, and dice pools.\n"
                    f"Do not include introductory flavor text or book citations. Keep the response under {max_chars} characters so it fits neatly into a character sheet printout layout."
                )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=f"Rule Topic: {topic}\n\nDocument Body:\n{body_content}",
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=100,
                    tools=tools
                )
            )
            summary = response.text.strip()
            if len(summary) > max_chars:
                summary = summary[:max_chars-3] + "..."
            
            cache[cache_key] = summary
            self._save_cache()
            return summary
        except Exception as e:
            print(f"[DEBUG WARNING] Cloud summarization failed: {e}")
            return None

    def _cloud_disambiguate(self, query, candidates, category):
        if not self.gemini_api_key:
            print(f"[DEBUG WARNING] GEMINI_API_KEY is not initialized. Cannot disambiguate {query}.")
            return None
            
        candidate_ids = sorted([c[1].get('id') or c[1].get('name') for c in candidates])
        cache_key = f"ambiguity:{normalize_name(query)}_{'_'.join(candidate_ids)}"
        
        cache = self._load_cache()
        if cache_key in cache:
            return cache[cache_key]
            
        try:
            from google import genai
            from google.genai import types
            
            cand_info = []
            for i, cand in enumerate(candidates):
                c_type, data = cand
                cand_info.append(
                    f"Candidate {i+1}:\n"
                    f"File ID/Name: {data.get('id') or data.get('name')}\n"
                    f"Topic/Name: {data.get('topic') or data.get('name')}\n"
                    f"Source: {data.get('source')}\n"
                    f"Description/Body:\n{data.get('body') or data.get('description')}\n"
                )
            candidates_text = "\n".join(cand_info)
            
            client = genai.Client(api_key=self.gemini_api_key)
            tools = [
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=["fileSearchStores/shadowrun-6e-srm-vault-d31wtxa55r5l"]
                    )
                )
            ]
            
            system_instruction = (
                "Analyze the character sheet asset node context and the candidate rule files provided.\n"
                "Determine which file logically applies to the character's active inventory slot (e.g., distinguishing a drone autosoft from a matrix hacking program).\n"
                "Respond with ONLY the exact canonical file ID matching the correct rule. Do not include commentary."
            )
            
            payload = (
                f"Query Item Name: {query}\n"
                f"Active Category Context: {category}\n\n"
                f"Candidates:\n{candidates_text}"
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=payload,
                config=types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    max_output_tokens=50,
                    tools=tools
                )
            )
            resolved_id = response.text.strip().replace('"', '').replace("'", "")
            
            cache[cache_key] = resolved_id
            self._save_cache()
            return resolved_id
        except Exception as e:
            print(f"[DEBUG WARNING] Cloud disambiguation failed: {e}")
            return None

    def query(self, q, category=None, max_chars=160):
        if not q:
            return None
        norm_q = normalize_name(q)
        
        is_software = False
        if category:
            is_software = normalize_name(category) in [
                'autosofts', 'autosoft', 'hackingprograms', 'hackingprogram',
                'commlinkapps', 'commlinkapp', 'basicprograms', 'basicprogram',
                'riggersoftware', 'otherprograms'
            ]
        target_max_chars = 35 if is_software else max_chars

        def format_rule_return(rule):
            body_lines = [l.strip() for l in rule['body'].split('\n')]
            body_lines = [l for l in body_lines if not l.startswith('#')]
            clean_body = "\n".join(body_lines).strip()
            
            game_effect = None
            for line in body_lines:
                if 'game effect:' in line.lower() or 'effect:' in line.lower():
                    effect_match = re.search(r'(?:game\s+)?effect:\s*(.*)', line, re.IGNORECASE)
                    if effect_match:
                        game_effect = effect_match.group(1).strip()
                        break
            
            first_p = ""
            for line in body_lines:
                if line and not line.startswith('-') and not line.startswith('*'):
                    first_p = line
                    break
            
            description = game_effect if game_effect else (first_p if first_p else clean_body)
            
            needs_sum = not game_effect or is_software
            if not needs_sum:
                keywords = ["+", "-", "dice", "pool", "test", "action", "rating", "bonus", "level", "limit", "soak", "damage"]
                has_kw = any(kw in game_effect.lower() for kw in keywords)
                if not has_kw:
                    needs_sum = True
                    
            if needs_sum:
                summary = self._cloud_summarize(rule['id'], rule['topic'], rule['body'], max_chars=target_max_chars)
                if summary:
                    description = summary
            
            return {
                'name': rule['topic'],
                'description': description,
                'source': rule['source'],
                'id': rule['id'],
                'full_text': clean_body,
                'type': 'rule'
            }

        def format_sub_item_return(sub):
            description = sub['description']
            
            keywords = ["+", "-", "dice", "pool", "test", "action", "rating", "bonus", "level", "limit", "soak", "damage"]
            has_kw = any(kw in description.lower() for kw in keywords)
            
            needs_sum = not has_kw or is_software
            if needs_sum:
                rule_info = self.rules.get(normalize_name(sub['id'])) if sub['id'] else None
                sub_context = f"Sub-item to summarize: {sub['name']}\nSub-item original description: {sub['description']}\n\nFull parent document body:\n"
                body_content = sub_context + (rule_info['body'] if rule_info else sub['description'])
                cache_file_id = f"{sub['id']}:{normalize_name(sub['name'])}" if sub['id'] else sub['name']
                summary = self._cloud_summarize(cache_file_id, sub['name'], body_content, max_chars=target_max_chars)
                if summary:
                    description = summary
                    
            return {
                'name': sub['name'],
                'description': description,
                'source': sub['source'],
                'id': sub['id'],
                'type': 'sub-item'
            }

        # Tier 1: Scoped Check
        if category:
            norm_category = normalize_name(category)
            scoped_key = f"{norm_category}:{norm_q}"
            if scoped_key in self.sub_items:
                return format_sub_item_return(self.sub_items[scoped_key])
            if scoped_key in self.rules:
                return format_rule_return(self.rules[scoped_key])

        # Tier 2: Global Structural Fallback
        candidates = []
        for sub in self.sub_items_all.get(norm_q, []):
            candidates.append(('sub-item', sub))
        for rule in self.rules_all.get(norm_q, []):
            candidates.append(('rule', rule))

        if not candidates:
            return None

        if len(candidates) == 1:
            c_type, data = candidates[0]
            if c_type == 'sub-item':
                return format_sub_item_return(data)
            else:
                return format_rule_return(data)

        # Tier 3: Cloud Disambiguation Fallback (first filter by authority level)
        min_auth = min(c[1].get('authority_level', 3) for c in candidates)
        candidates = [c for c in candidates if c[1].get('authority_level', 3) == min_auth]

        if len(candidates) == 1:
            c_type, data = candidates[0]
            if c_type == 'sub-item':
                return format_sub_item_return(data)
            else:
                return format_rule_return(data)

        resolved_id = self._cloud_disambiguate(q, candidates, category or "Unknown")
        if resolved_id:
            for c_type, data in candidates:
                cand_id = data.get('id') or data.get('name')
                if cand_id == resolved_id or normalize_name(cand_id) == normalize_name(resolved_id):
                    if c_type == 'sub-item':
                        return format_sub_item_return(data)
                    else:
                        return format_rule_return(data)

        # Default fallback to first candidate
        c_type, data = candidates[0]
        if c_type == 'sub-item':
            return format_sub_item_return(data)
        else:
            return format_rule_return(data)

    def query_weapon_stats(self, weapon_name):
        cache_key = f"weapon_stats:{normalize_name(weapon_name)}"
        cache = self._load_cache()
        if cache_key in cache:
            return cache[cache_key]
            
        if not self.gemini_api_key:
            return None
            
        try:
            from google import genai
            from google.genai import types
            
            client = genai.Client(api_key=self.gemini_api_key)
            tools = [
                types.Tool(
                    file_search=types.FileSearch(
                        file_search_store_names=["fileSearchStores/shadowrun-6e-srm-vault-d31wtxa55r5l"]
                    )
                )
            ]
            
            prompt = (
                f"Search the shadowrun vault for the official weapon stats of '{weapon_name}'.\n"
                "Extract the Damage Value (DV) and the Attack Ratings (AR) for close/near/medium/far/extreme ranges.\n"
                "Respond with a raw JSON object only containing the keys 'damage' and 'attack_rating'. Do not include markdown code block formatting or comments."
            )
            
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
                config=types.GenerateContentConfig(
                    system_instruction="Extract and return ONLY a raw JSON object with 'damage' (e.g., '3P') and 'attack_rating' (e.g., '10/10/8/—/—').",
                    max_output_tokens=80,
                    tools=tools
                )
            )
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                text = "\n".join(lines).strip()
                
            text = text.replace('\uFFFD', '—')
            data = json.loads(text)
            if 'attack_rating' in data and isinstance(data['attack_rating'], str):
                data['attack_rating'] = data['attack_rating'].replace('\uFFFD', '—')
            cache[cache_key] = data
            self._save_cache()
            return data
        except Exception as e:
            try:
                from google import genai
                client = genai.Client(api_key=self.gemini_api_key)
                response = client.models.generate_content(
                    model='gemini-2.5-flash-lite',
                    contents=f"Return a raw JSON object containing the Shadowrun 6e weapon stats for '{weapon_name}' with keys 'damage' and 'attack_rating'. Do not include any commentary.",
                )
                text = response.text.strip()
                if text.startswith("```"):
                    lines = text.split("\n")
                    if lines[0].startswith("```json") or lines[0].startswith("```"):
                        lines = lines[1:-1]
                    text = "\n".join(lines).strip()
                text = text.replace('\uFFFD', '—')
                data = json.loads(text)
                if 'attack_rating' in data and not isinstance(data['attack_rating'], str):
                    data['attack_rating'] = str(data['attack_rating'])
                if 'attack_rating' in data:
                    data['attack_rating'] = data['attack_rating'].replace('\uFFFD', '—')
                cache[cache_key] = data
                self._save_cache()
                return data
            except Exception as e2:
                print(f"[DEBUG WARNING] Failed to query weapon stats for {weapon_name} (with fallback): {e2}")
                return None

    def check_if_weapon(self, item_name):
        cache_key = f"is_weapon:{normalize_name(item_name)}"
        cache = self._load_cache()
        if cache_key in cache:
            return cache[cache_key]
            
        if not self.gemini_api_key:
            return False
            
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_api_key)
            prompt = (
                f"Is the item '{item_name}' a weapon in Shadowrun 6th Edition (6e)?\n"
                "Respond with only a JSON object containing a single key 'is_weapon' with a boolean value (true or false). Do not include markdown formatting or comments."
            )
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                text = "\n".join(lines).strip()
            data = json.loads(text)
            res = bool(data.get('is_weapon', False))
            cache[cache_key] = res
            self._save_cache()
            return res
        except Exception as e:
            print(f"[DEBUG WARNING] Failed to check if weapon for {item_name}: {e}")
            return False

    def check_if_armor(self, item_name):
        cache_key = f"is_armor:{normalize_name(item_name)}"
        cache = self._load_cache()
        if cache_key in cache:
            return cache[cache_key]
            
        if not self.gemini_api_key:
            return False
            
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_api_key)
            prompt = (
                f"Is the item '{item_name}' armor, protective clothing, or a shield in Shadowrun 6th Edition (6e)?\n"
                "Respond with only a JSON object containing a single key 'is_armor' with a boolean value (true or false). Do not include markdown formatting or comments."
            )
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                text = "\n".join(lines).strip()
            data = json.loads(text)
            res = bool(data.get('is_armor', False))
            cache[cache_key] = res
            self._save_cache()
            return res
        except Exception as e:
            print(f"[DEBUG WARNING] Failed to check if armor for {item_name}: {e}")
            return False

    def query_armor_stats(self, armor_name):
        norm_name = normalize_name(armor_name)
        if norm_name in ["wristshield", "wrist_shield"]:
            return {"armor_rating": "+4"}
            
        cache_key = f"armor_stats:{norm_name}"
        cache = self._load_cache()
        if cache_key in cache:
            return cache[cache_key]
            
        if not self.gemini_api_key:
            return None
            
        try:
            from google import genai
            client = genai.Client(api_key=self.gemini_api_key)
            prompt = (
                f"What is the official Armor Rating of '{armor_name}' in Shadowrun 6th Edition (6e)?\n"
                "Respond with only a JSON object containing a single key 'armor_rating' with its numeric value or string (e.g. 2 or '+2' or '+1'). Do not include markdown formatting or comments."
            )
            response = client.models.generate_content(
                model='gemini-2.5-flash-lite',
                contents=prompt,
            )
            text = response.text.strip()
            if text.startswith("```"):
                lines = text.split("\n")
                if lines[0].startswith("```json") or lines[0].startswith("```"):
                    lines = lines[1:-1]
                text = "\n".join(lines).strip()
            data = json.loads(text)
            cache[cache_key] = data
            self._save_cache()
            return data
        except Exception as e:
            print(f"[DEBUG WARNING] Failed to query armor stats for {armor_name}: {e}")
            return None

    def query_rule(self, query, category=None):
        return self.query(query, category)
