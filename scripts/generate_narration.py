import os
import sys

# Exit early if running in GitHub Actions CI to avoid dependency issues & overhead
if os.environ.get("GITHUB_ACTIONS") == "true":
    print("[*] Running in GitHub Actions CI. Skipping narration generation since audio files are pre-rendered and committed.")
    sys.exit(0)

# Pre-load onnxruntime DLL from local virtual environment
base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ort_dll_dir = os.path.join(base_dir, ".venv", "Lib", "site-packages", "onnxruntime", "capi")
if os.path.exists(ort_dll_dir):
    os.environ["PATH"] = ort_dll_dir + os.pathsep + os.environ.get("PATH", "")
    if hasattr(os, "add_dll_directory"):
        try:
            os.add_dll_directory(ort_dll_dir)
        except Exception as e:
            print(f"[*] Warning adding DLL directory: {e}")

import re
import urllib.request
import urllib.parse
import tarfile
import numpy as np
import lameenc
import sherpa_onnx
import concurrent.futures

MODEL_URL = "https://github.com/k2-fsa/sherpa-onnx/releases/download/tts-models/kokoro-multi-lang-v1_0.tar.bz2"
MODEL_DIR = "kokoro-multi-lang-v1_0"
VOICE_SID = 3  # af_heart in kokoro-multi-lang-v1_0
VOICE_SPEED = 0.94  # Calibrated for natural, deliberate audio narrative pacing

def download_model():
    """Download and extract the Kokoro TTS model if not present."""
    if os.path.exists(MODEL_DIR):
        print(f"[*] Model directory '{MODEL_DIR}' already exists.")
        return

    tar_path = "kokoro-multi-lang-v1_0.tar.bz2"
    print(f"[*] Downloading Kokoro model from {MODEL_URL}...")
    
    def progress(count, block_size, total_size):
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\rDownloading: {percent}%")
        sys.stdout.flush()
        
    urllib.request.urlretrieve(MODEL_URL, tar_path, reporthook=progress)
    print("\n[*] Download complete. Extracting files...")
    
    with tarfile.open(tar_path, "r:bz2") as tar:
        tar.extractall()
    
    print("[*] Extraction complete.")
    if os.path.exists(tar_path):
        os.remove(tar_path)

def initialize_tts():
    """Set up the OfflineTts engine."""
    tts_config = sherpa_onnx.OfflineTtsConfig(
        model=sherpa_onnx.OfflineTtsModelConfig(
            kokoro=sherpa_onnx.OfflineTtsKokoroModelConfig(
                model=f"{MODEL_DIR}/model.onnx",
                voices=f"{MODEL_DIR}/voices.bin",
                tokens=f"{MODEL_DIR}/tokens.txt",
                data_dir=f"{MODEL_DIR}/espeak-ng-data",
                lexicon=f"{MODEL_DIR}/lexicon-us-en.txt,{MODEL_DIR}/lexicon-zh.txt",
                dict_dir=f"{MODEL_DIR}/dict",
            ),
        )
    )
    return sherpa_onnx.OfflineTts(tts_config)

def clean_pronunciation(text):
    """Applies pronunciation corrections for specialized Shadowrun terms."""
    text = re.sub(r'\br31-?k0\b', 'Rayko', text, flags=re.IGNORECASE)
    text = re.sub(r'\breiko\b', 'Rayko', text, flags=re.IGNORECASE)
    text = text.replace('T@z', 'Taz').replace('t@z', 'taz')
    text = text.replace('SINner', 'sinner').replace('SINners', 'sinners')
    text = re.sub(r'\bnuyens\b', 'new yens', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnuyen\b', 'new yen', text, flags=re.IGNORECASE)
    text = re.sub(r'\br3sP@wn\b', 'respawn', text, flags=re.IGNORECASE)
    text = re.sub(r'\br3sp@wn\b', 'respawn', text, flags=re.IGNORECASE)
    text = text.replace('\\', '')
    return text

def apply_edge_fades(samples, sample_rate=24000, fade_ms=5):
    """Applies a 5ms raised-cosine fade-in and fade-out to prevent mechanical audio clicks."""
    if samples is None or len(samples) < 100:
        return samples
    
    fade_len = int(sample_rate * (fade_ms / 1000.0))
    if len(samples) < fade_len * 2:
        return samples
    
    out = samples.copy()
    # Fade in
    fade_in = 0.5 * (1.0 - np.cos(np.pi * np.arange(fade_len) / fade_len))
    out[:fade_len] *= fade_in
    
    # Fade out
    fade_out = 0.5 * (1.0 + np.cos(np.pi * np.arange(fade_len) / fade_len))
    out[-fade_len:] *= fade_out
    
    return out

def split_into_narration_chunks(text):
    """
    Splits text into breath-aware speech chunks paired with natural silence pauses.
    Returns list of tuples: (chunk_text, pause_duration_seconds).
    """
    # Pattern to match sentence terminals or clause markers
    # Triggers on [.!?…], colons, semicolons, or dialogue quotes followed by spaces
    raw_tokens = re.split(r'((?<=[.!?…])\s+|(?<=[:;])\s+|(?<=[,])\s+)', text)
    
    chunks = []
    current_str = ""
    
    for token in raw_tokens:
        if not token:
            continue
        current_str += token
        
        # Determine pause duration based on trailing punctuation of current_str
        stripped = current_str.strip()
        if not stripped:
            continue
            
        pause = 0.0
        if stripped.endswith('...') or stripped.endswith('…') or stripped.endswith('--'):
            pause = 0.35
        elif stripped.endswith('?') or stripped.endswith('!'):
            pause = 0.55
        elif stripped.endswith('.'):
            pause = 0.48
        elif stripped.endswith('"') or stripped.endswith('”'):
            pause = 0.35
        elif stripped.endswith(':') or stripped.endswith(';'):
            pause = 0.25
        elif stripped.endswith(','):
            pause = 0.18
            
        if pause > 0.0 or len(current_str) > 120:
            chunks.append((stripped, pause if pause > 0.0 else 0.30))
            current_str = ""
            
    if current_str.strip():
        chunks.append((current_str.strip(), 0.40))
        
    return chunks

def process_chapter(file_path, tts):
    """Parse chapter markdown, clean pronunciation, apply dynamic pause mapping, synthesize audio."""
    chapter_name = os.path.splitext(os.path.basename(file_path))[0]
    print(f"[*] Processing: {chapter_name}")
    
    with open(file_path, 'r', encoding='utf-8') as f:
        lines = f.read().splitlines()
        
    paragraphs = []
    current_para = []
    
    for line in lines:
        stripped = line.strip()
        if not stripped:
            if current_para:
                paragraphs.append("\n".join(current_para))
                current_para = []
        elif stripped.startswith('#'):
            if current_para:
                paragraphs.append("\n".join(current_para))
                current_para = []
            paragraphs.append(stripped)
        else:
            if "<audio" in stripped:
                continue
            current_para.append(line)
            
    if current_para:
        paragraphs.append("\n".join(current_para))

    audio_segments = []
    sample_rate = 24000
    
    for para in paragraphs:
        if not para.strip():
            continue
            
        # Headers (Chapter Titles)
        if para.startswith('#'):
            header_text = para.replace('#', '').strip().replace('*', '').replace('_', '')
            header_text = clean_pronunciation(header_text)
            audio = tts.generate(text=header_text, sid=VOICE_SID, speed=VOICE_SPEED)
            if audio.samples is not None:
                smoothed = apply_edge_fades(audio.samples, sample_rate=sample_rate)
                audio_segments.append(smoothed)
                # 1.2s pause after chapter title
                audio_segments.append(np.zeros(int(sample_rate * 1.2), dtype=np.float32))
            continue

        # Clean formatting marks
        cleaned_para = para.replace('*', '').replace('_', '').replace('“', '"').replace('”', '"')
        cleaned_para = clean_pronunciation(cleaned_para)
        
        # Split into breath-aware speech chunks with dynamic pause durations
        chunks = split_into_narration_chunks(cleaned_para)
        for chunk_text, pause_sec in chunks:
            if not chunk_text.strip():
                continue
            audio = tts.generate(text=chunk_text, sid=VOICE_SID, speed=VOICE_SPEED)
            if audio.samples is not None:
                smoothed = apply_edge_fades(audio.samples, sample_rate=sample_rate)
                audio_segments.append(smoothed)
                if pause_sec > 0:
                    audio_segments.append(np.zeros(int(sample_rate * pause_sec), dtype=np.float32))
                
        # 0.95s pause between paragraphs for natural scene transitions
        audio_segments.append(np.zeros(int(sample_rate * 0.95), dtype=np.float32))

    if not audio_segments:
        print(f"[!] No audio generated for {chapter_name}")
        return

    full_audio = np.concatenate(audio_segments)
    
    pcm_ints = np.clip(full_audio, -1.0, 1.0) * 32767
    pcm_ints = pcm_ints.astype(np.int16)
    pcm_bytes = pcm_ints.tobytes()
    
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1)
    encoder.set_quality(2)
    encoder.silence()
    
    mp3_data = encoder.encode(pcm_bytes)
    mp3_data += encoder.flush()
    
    inject_audio_player(file_path, chapter_name)

    os.makedirs("chapters/audio", exist_ok=True)
    mp3_path = f"chapters/audio/{chapter_name}.mp3"
    
    import time
    for attempt in range(5):
        try:
            with open(mp3_path, 'wb') as mp3_file:
                mp3_file.write(mp3_data)
            break
        except PermissionError as e:
            if attempt == 4:
                raise e
            time.sleep(0.5)
            
    print(f"[+] Saved audio to {mp3_path}")

def inject_audio_player(file_path, chapter_name):
    """Ensure HTML5 audio player tag is injected immediately below the chapter title."""
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
        
    encoded_name = urllib.parse.quote(f"{chapter_name}.mp3")
    audio_rel_path = f"audio/{encoded_name}"
    
    player_tag = f'<audio controls src="{audio_rel_path}" style="width: 100%; margin-bottom: 20px;"></audio>'
    
    if player_tag in content:
        return
        
    content = re.sub(r'<audio.*?</audio>\n*', '', content)
    
    lines = content.splitlines()
    inserted = False
    for idx, line in enumerate(lines):
        if line.strip().startswith('#'):
            lines.insert(idx + 1, "")
            lines.insert(idx + 2, player_tag)
            inserted = True
            break
            
    if inserted:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write("\n".join(lines) + "\n")
        print(f"    [+] Injected audio player into {file_path}")

def process_chapter_wrapper(args):
    """Worker process entry point."""
    file_path, _ = args
    try:
        tts = initialize_tts()
        process_chapter(file_path, tts)
    except Exception as e:
        print(f"[-] Error processing {file_path}: {e}")
        raise e

def main():
    download_model()
    
    chapters_dir = "chapters"
    md_files = [
        os.path.join(chapters_dir, f) 
        for f in os.listdir(chapters_dir) 
        if f.endswith('.md') and f[0].isdigit()
    ]
    md_files.sort()
    
    print(f"[*] Found {len(md_files)} story chapters.")
    
    tasks = []
    for md_file in md_files:
        chapter_name = os.path.splitext(os.path.basename(md_file))[0]
        mp3_path = f"chapters/audio/{chapter_name}.mp3"
        
        recreate = False
        if not os.path.exists(mp3_path):
            recreate = True
        else:
            md_mtime = os.path.getmtime(md_file)
            mp3_mtime = os.path.getmtime(mp3_path)
            if md_mtime > mp3_mtime:
                recreate = True
                
        if recreate:
            tasks.append(md_file)
        else:
            print(f"[*] Up to date: {chapter_name}")
            inject_audio_player(md_file, chapter_name)

    if not tasks:
        print("[*] All chapters are up-to-date.")
        return

    print(f"[*] Generating narration for {len(tasks)} chapters in parallel...")
    
    max_workers = min(3, os.cpu_count() or 1)
    print(f"[*] Running with max_workers={max_workers} for fast parallel generation.")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(task, None) for task in tasks]
        list(executor.map(process_chapter_wrapper, args_list))
        
    print("[*] All narrations generated successfully!")

if __name__ == "__main__":
    main()
