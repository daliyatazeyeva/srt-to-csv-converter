import streamlit as st
import pysrt
import csv
import io
import pandas as pd
import re

def format_timestamp(srt_time):
    """Converts pysrt time object to seconds.milliseconds format (0.000)"""
    total_seconds = (srt_time.hours * 3600 + 
                     srt_time.minutes * 60 + 
                     srt_time.seconds + 
                     srt_time.milliseconds / 1000.0)
    return f"{total_seconds:.3f}"

def clean_text(text):
    if not text: return ""
    # Remove HTML tags and fix line breaks
    cleaned = re.sub(r'<[^>]*>', '', text)
    cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
    return cleaned.strip()

def get_full_english_sentences(subs):
    """
    Groups English SRT blocks into full sentences.
    Ensures a split ONLY happens at . ! ? or …
    """
    sentences = []
    current_items = []
    
    for sub in subs:
        current_items.append(sub)
        text = sub.text.strip()
        # Only split if the text ends with sentence-ending punctuation
        if re.search(r'[.!?…]$', text):
            sentences.append({
                'text': " ".join([clean_text(s.text) for s in current_items]),
                'start': current_items[0].start,
                'end': current_items[-1].end
            })
            current_items = []
            
    # Add remaining text if file doesn't end with punctuation
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
    
    # 1. Reconstruct English into full sentences (Timestamps from English are preserved)
    eng_sentences = get_full_english_sentences(subs_orig)
    
    # 2. Prepare a container for Russian text mapped to English indices
    # mapping = { 0: ["Rus text 1", "Rus text 2"], 1: ["Rus text 3"] ... }
    mapped_translation = {i: [] for i in range(len(eng_sentences))}
    
    # 3. Best-Fit Logic: Assign each Russian segment to exactly ONE English sentence
    for sub_t in subs_trans:
        t_start = sub_t.start.ordinal
        t_end = sub_t.end.ordinal
        t_mid = (t_start + t_end) / 2
        
        best_index = -1
        max_overlap = -1
        min_distance = float('inf')
        closest_index = -1

        for i, eng_s in enumerate(eng_sentences):
            e_start = eng_s['start'].ordinal
            e_end = eng_s['end'].ordinal
            e_mid = (e_start + e_end) / 2
            
            # Calculate actual overlap
            overlap = min(e_end, t_end) - max(e_start, t_start)
            
            if overlap > max_overlap:
                max_overlap = overlap
                best_index = i
            
            # Keep track of the closest sentence just in case timestamps are way off (no overlap)
            distance = abs(t_mid - e_mid)
            if distance < min_distance:
                min_distance = distance
                closest_index = i
        
        # If there is an overlap, use the best overlapping sentence
        # Otherwise, if timing is "incorrect" and there's no overlap, use the closest sentence
        target_index = best_index if max_overlap > 0 else closest_index
        
        if target_index != -1:
            mapped_translation[target_index].append(clean_text(sub_t.text))

    # 4. Construct the Final CSV Data
    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    for i, eng_s in enumerate(eng_sentences):
        full_translation = " ".join(mapped_translation[i])
        full_translation = re.sub(r'\s+', ' ', full_translation).strip()
        
        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': eng_s['text'],
            'translation': full_translation,
            'start_time': format_timestamp(eng_s['start']),
            'end_time': format_timestamp(eng_s['end'])
        })
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_headers, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), len(eng_sentences)

# --- Streamlit UI ---
st.set_page_config(page_title="AI Dubbing Aligner", layout="wide")

st.title("🎙️ AI Dubbing Aligner (Sentence Integrity Mode)")
st.markdown("""
Download from smartcat both eng and translated SRTs and upload here to get CSV for 11labs
""")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. English SRT", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Translated SRT", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate Final AI-Ready CSV"):
        try:
            csv_result, final_row_count = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Successfully aligned into {final_row_count} full sentence blocks.")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download Merged CSV",
                data=csv_result.encode('utf-8-sig'),
                file_name="ai_dubbing_final.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
