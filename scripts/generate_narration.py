import os
import sys

# Exit early if running in GitHub Actions CI to avoid dependency issues & overhead
if os.environ.get("GITHUB_ACTIONS") == "true":
    print("[*] Running in GitHub Actions CI. Skipping narration generation since audio files are pre-rendered and committed.")
    sys.exit(0)


# Crucial: Pre-load the correct onnxruntime DLL from the local virtual environment
# to override any older system-wide onnxruntime.dll loaded from C:\Windows\System32.
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
VOICE_SPEED = 1.0

def download_model():
    """Download and extract the Kokoro TTS model if not present."""
    if os.path.exists(MODEL_DIR):
        print(f"[*] Model directory '{MODEL_DIR}' already exists.")
        return

    tar_path = "kokoro-multi-lang-v1_0.tar.bz2"
    print(f"[*] Downloading Kokoro model from {MODEL_URL}...")
    
    # Download with progress logging
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
    """
    Applies pronunciation corrections for special terms:
    - Reiko / r31-k0 / r31k0 -> Rayko
    - Taz / T@z / t@z -> Taz / taz
    - SINner / SINners -> sinner / sinners
    - nuyen / nuyens -> new yen / new yens
    - r3sP@wn -> respawn
    """
    # Replace r31k0 / r31-k0 / Reiko with Rayko (case-insensitive)
    text = re.sub(r'\br31-?k0\b', 'Rayko', text, flags=re.IGNORECASE)
    text = re.sub(r'\breiko\b', 'Rayko', text, flags=re.IGNORECASE)
    
    # Replace T@z with Taz
    text = text.replace('T@z', 'Taz').replace('t@z', 'taz')
    
    # Replace SINner with sinner
    text = text.replace('SINner', 'sinner').replace('SINners', 'sinners')
    
    # Replace nuyens/nuyen with new yens/new yen
    text = re.sub(r'\bnuyens\b', 'new yens', text, flags=re.IGNORECASE)
    text = re.sub(r'\bnuyen\b', 'new yen', text, flags=re.IGNORECASE)
    
    # Replace r3sP@wn with respawn
    text = re.sub(r'\br3sP@wn\b', 'respawn', text, flags=re.IGNORECASE)
    text = re.sub(r'\br3sp@wn\b', 'respawn', text, flags=re.IGNORECASE)
    
    # Strip backslashes used as markdown escapes so TTS doesn't read them out
    text = text.replace('\\', '')
    
    return text

def split_into_sentences(text):
    """Split a paragraph into sentences on standard punctuation."""
    sentence_endings = re.compile(r'(?<=[.!?])\s+')
    sentences = sentence_endings.split(text)
    return [s.strip() for s in sentences if s.strip()]

def process_chapter(file_path, tts):
    """Parse chapter markdown, clean pronunciation, split to sentences, synthesize with af_heart."""
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
            
        # Treat headers as title narration
        if para.startswith('#'):
            header_text = para.replace('#', '').strip()
            header_text = header_text.replace('*', '').replace('_', '')
            header_text = clean_pronunciation(header_text)
            audio = tts.generate(text=header_text, sid=VOICE_SID, speed=VOICE_SPEED)
            if audio.samples is not None:
                audio_segments.append(audio.samples)
                # Longer pause after headers
                audio_segments.append(np.zeros(int(sample_rate * 1.2), dtype=np.float32))
            continue

        # Clean formatting marks
        cleaned_para = para.replace('*', '').replace('_', '').replace('“', '"').replace('”', '"')
        # Correct pronunciations
        cleaned_para = clean_pronunciation(cleaned_para)
        
        # Split into sentences to avoid length constraints
        sentences = split_into_sentences(cleaned_para)
        for sentence in sentences:
            if not sentence.strip():
                continue
            audio = tts.generate(text=sentence, sid=VOICE_SID, speed=VOICE_SPEED)
            if audio.samples is not None:
                audio_segments.append(audio.samples)
                # Pause between sentences
                audio_segments.append(np.zeros(int(sample_rate * 0.4), dtype=np.float32))
                
        # Pause between paragraphs
        audio_segments.append(np.zeros(int(sample_rate * 0.8), dtype=np.float32))

    if not audio_segments:
        print(f"[!] No audio generated for {chapter_name}")
        return

    # Concatenate all generated audio segments
    full_audio = np.concatenate(audio_segments)
    
    # Convert float32 [-1.0, 1.0] samples to 16-bit signed PCM
    pcm_ints = np.clip(full_audio, -1.0, 1.0) * 32767
    pcm_ints = pcm_ints.astype(np.int16)
    pcm_bytes = pcm_ints.tobytes()
    
    # Compress raw PCM to MP3 using lameenc
    encoder = lameenc.Encoder()
    encoder.set_bit_rate(128)
    encoder.set_in_sample_rate(sample_rate)
    encoder.set_channels(1) # Mono
    encoder.set_quality(2)
    encoder.silence()
    
    mp3_data = encoder.encode(pcm_bytes)
    mp3_data += encoder.flush()
    
    # Inject audio player into the source markdown file first
    # (keeps MP3 file modification time newer than the MD file)
    inject_audio_player(file_path, chapter_name)

    # Save output MP3
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
            print(f"    [!] Permission denied writing to {mp3_path}. Retrying in 0.5s (attempt {attempt + 1}/5)...")
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
    # 1. Prepare Model (download first, single-process)
    download_model()
    
    # 2. Get all markdown chapter files
    chapters_dir = "chapters"
    md_files = [
        os.path.join(chapters_dir, f) 
        for f in os.listdir(chapters_dir) 
        if f.endswith('.md') and f[0].isdigit()
    ]
    md_files.sort()
    
    print(f"[*] Found {len(md_files)} story chapters.")
    
    # 3. Check modifications and select files to process
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
    
    # Use ProcessPoolExecutor with a limited number of workers (max 2)
    # to avoid pinning all CPU cores and causing system instability or thermal shutdown.
    max_workers = min(2, os.cpu_count() or 1)
    print(f"[*] Running with max_workers={max_workers} to maintain system stability.")
    
    with concurrent.futures.ProcessPoolExecutor(max_workers=max_workers) as executor:
        args_list = [(task, None) for task in tasks]
        # Wait for all processes to complete
        list(executor.map(process_chapter_wrapper, args_list))
        
    print("[*] All narrations generated successfully!")

if __name__ == "__main__":
    main()
