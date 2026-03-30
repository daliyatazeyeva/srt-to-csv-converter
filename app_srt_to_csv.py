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
    """
    Ensures all lines of text are captured, removing extra newlines 
    and ensuring no part of the translation is lost.
    """
    if not text:
        return ""
    # Replace all variations of newlines (including multiple ones) with a single space
    cleaned = re.sub(r'[\r\n]+', ' ', text)
    # Remove any tags like <i> or <b>
    cleaned = re.sub(r'<[^>]*>', '', cleaned)
    return cleaned.strip()

def process_srts(original_file, translated_file):
    # Read files with robust encoding support
    orig_content = original_file.read().decode("utf-8-sig", errors='replace')
    trans_content = translated_file.read().decode("utf-8-sig", errors='replace')
    
    # Parse SRT content
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    # mapping: Russian index -> list of English SubRipItems
    matched_mapping = {i: [] for i in range(len(subs_trans))}
    
    # ALIGNMENT: Assign every English snippet to its Russian container based on time
    for sub_o in subs_orig:
        o_center = sub_o.start.ordinal + (sub_o.duration.ordinal / 2)
        
        best_match_idx = 0
        min_dist = float('inf')
        
        for i, sub_t in enumerate(subs_trans):
            # Check if English center falls within Russian block time
            if sub_t.start.ordinal <= o_center <= sub_t.end.ordinal:
                best_match_idx = i
                break
            
            # Distance check for gaps
            dist = min(abs(sub_t.start.ordinal - o_center), abs(sub_t.end.ordinal - o_center))
            if dist < min_dist:
                min_dist = dist
                best_match_idx = i
        
        matched_mapping[best_match_idx].append(sub_o)

    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    for i, sub_t in enumerate(subs_trans):
        assigned_english = matched_mapping[i]
        
        # Merge Transcription (English)
        if assigned_english:
            transcription = " ".join([clean_text(s.text) for s in assigned_english])
            # Use English timings for speech-priority
            start_val = format_timestamp(assigned_english[0].start)
            end_val = format_timestamp(assigned_english[-1].end)
        else:
            transcription = ""
            start_val = format_timestamp(sub_t.start)
            end_val = format_timestamp(sub_t.end)

        # CAPTURE FULL TRANSLATION (Russian)
        # We use the raw text and apply our robust cleaner to catch all lines
        translation = clean_text(sub_t.text)
        
        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': transcription,
            'translation': translation,
            'start_time': start_val,
            'end_time': end_val
        })
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_headers, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), len(subs_orig), len(subs_trans)

# --- Streamlit UI ---
st.set_page_config(page_title="Pro AI Dubbing Aligner", layout="wide")

st.title("🎙️ AI Dubbing Aligner (Multi-Line Fix)")
st.info("Updated: Now captures all lines of text from Russian SRT blocks, even if they contain empty lines.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. English SRT (Speech Timings)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Russian SRT (Full Translation)", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate Final CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Processed {count_o} English lines into {count_t} Russian segments.")
            
            st.write("### Preview (Check rows to ensure all text is present)")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download Corrected CSV",
                data=csv_result.encode('utf-8-sig'), # Added BOM for better Excel support
                file_name="dubbing_ready_full_text.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
