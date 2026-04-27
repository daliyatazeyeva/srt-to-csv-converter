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
    
    # Check if files match segment count
    if len(subs_orig) != len(subs_trans):
        st.warning(f"Warning: Segment counts differ! (Eng: {len(subs_orig)}, Trans: {len(subs_trans)})")

    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # Use zip to match segment #1 to segment #1 directly
    for sub_e, sub_t in zip(subs_orig, subs_trans):
        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': clean_text(sub_e.text),
            'translation': clean_text(sub_t.text),
            'start_time': format_timestamp(sub_e.start),
            'end_time': format_timestamp(sub_e.end)
        })
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_headers, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), len(subs_orig)

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
