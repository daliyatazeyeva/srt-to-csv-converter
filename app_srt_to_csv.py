import streamlit as st
import pysrt
import csv
import io
import pandas as pd
import re

def format_timestamp(srt_time):
    """Converts pysrt time object to total seconds as a string."""
    total_seconds = (srt_time.hours * 3600 + 
                     srt_time.minutes * 60 + 
                     srt_time.seconds + 
                     srt_time.milliseconds / 1000.0)
    return f"{total_seconds:.3f}"

def clean_text(text):
    if not text: return ""
    cleaned = re.sub(r'<[^>]*>', '', text)
    cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
    return cleaned.strip()

def get_full_english_sentences(subs):
    """Groups English SRT fragments into whole sentences based on punctuation."""
    sentences = []
    current_items = []
    
    for sub in subs:
        current_items.append(sub)
        text = sub.text.strip()
        if re.search(r'[.!?…]$', text):
            sentences.append({
                'text': " ".join([clean_text(s.text) for s in current_items]),
                'start': current_items[0].start,
                'end': current_items[-1].end
            })
            current_items = []
            
    if current_items:
        sentences.append({
            'text': " ".join([clean_text(s.text) for s in current_items]),
            'start': current_items[0].start,
            'end': current_items[-1].end
        })
    return sentences

def process_srts(original_file, translated_file):
    orig_content = original_file.read().decode("utf-8-sig", errors='replace')
    trans_content = translated_file.read().decode("utf-8-sig", errors='replace')
    
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    # 1. Reconstruct English into full sentences
    eng_sentences = get_full_english_sentences(subs_orig)
    
    # 2. Map Russian to English
    # If timings are broken, we fallback to a ratio-based sequential mapping
    mapped_translation = {i: [] for i in range(len(eng_sentences))}
    
    for j, sub_t in enumerate(subs_trans):
        t_start = sub_t.start.ordinal
        t_end = sub_t.end.ordinal
        t_mid = (t_start + t_end) / 2
        
        best_index = -1
        max_overlap = -1
        
        # Try to find overlap first
        for i, eng_s in enumerate(eng_sentences):
            e_start = eng_s['start'].ordinal
            e_end = eng_s['end'].ordinal
            
            overlap = min(e_end, t_end) - max(e_start, t_start)
            if overlap > max_overlap:
                max_overlap = overlap
                best_index = i
        
        # FALLBACK: If timings are totally wrong (no overlap), 
        # map by sequential order (Russian segment 5 maps to roughly sentence 5)
        if max_overlap <= 0:
            # Estimate position based on index ratio
            ratio = j / len(subs_trans)
            best_index = int(ratio * len(eng_sentences))
            
        if best_index != -1:
            mapped_translation[best_index].append(clean_text(sub_t.text))

    # 3. Create CSV Data
    csv_data = []
    for i, eng_s in enumerate(eng_sentences):
        trans_text = " ".join(mapped_translation[i])
        trans_text = re.sub(r'\s+', ' ', trans_text).strip()
        
        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': eng_s['text'],
            'translation': trans_text if trans_text else "[MISSING TRANSLATION]",
            'start_time': format_timestamp(eng_s['start']),
            'end_time': format_timestamp(eng_s['end'])
        })
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=['speaker', 'transcription', 'translation', 'start_time', 'end_time'], quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), len(eng_sentences)

# --- Streamlit UI ---
st.set_page_config(page_title="AI Dubbing Aligner", layout="wide")
st.title("🎙️ AI Dubbing Aligner (Robust Timing Mode)")

col1, col2 = st.columns(2)
with col1:
    orig_file = st.file_uploader("1. English SRT", type=['srt'])
with col2:
    trans_file = st.file_uploader("2. Translated SRT", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate Final CSV"):
        csv_result, count = process_srts(orig_file, trans_file)
        df = pd.read_csv(io.StringIO(csv_result))
        
        # IMPORTANT: Don't sort the dataframe here, keep natural order
        st.success(f"Aligned {count} segments.")
        st.dataframe(df)

        st.download_button("📥 Download CSV", data=csv_result.encode('utf-8-sig'), file_name="final_align.csv")
