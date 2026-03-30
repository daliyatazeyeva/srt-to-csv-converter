import streamlit as st
import pysrt
import csv
import io
import pandas as pd

def format_timestamp(srt_time):
    """Converts pysrt time object to seconds.milliseconds format (0.000)"""
    total_seconds = (srt_time.hours * 3600 + 
                     srt_time.minutes * 60 + 
                     srt_time.seconds + 
                     srt_time.milliseconds / 1000.0)
    return f"{total_seconds:.3f}"

def process_srts(original_file, translated_file):
    # Read files into memory
    orig_content = original_file.read().decode("utf-8-sig")
    trans_content = translated_file.read().decode("utf-8-sig")
    
    # Parse SRT content
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    # Dictionary to hold matched English text for each Russian segment index
    matched_mapping = {i: [] for i in range(len(subs_trans))}
    
    # For every English block, find which Russian block its CENTER POINT falls into
    for sub_o in subs_orig:
        # Calculate center point of the English subtitle in milliseconds
        o_center = sub_o.start.ordinal + (sub_o.duration.ordinal / 2)
        
        best_match_idx = None
        min_dist = float('inf')
        
        for i, sub_t in enumerate(subs_trans):
            # Check if center point falls within the Russian segment boundaries
            if sub_t.start.ordinal <= o_center <= sub_t.end.ordinal:
                best_match_idx = i
                break
            
            # Fallback: Find the Russian segment with the closest start time
            dist = abs(sub_t.start.ordinal - o_center)
            if dist < min_dist:
                min_dist = dist
                best_match_idx = i
        
        if best_match_idx is not None:
            clean_o = sub_o.text_without_tags.replace('\n', ' ').strip()
            matched_mapping[best_match_idx].append(clean_o)

    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # Construct final rows based on the Russian (Translation) segments
    for i, sub_t in enumerate(subs_trans):
        transcription = " ".join(matched_mapping[i])
        translation = sub_t.text_without_tags.replace('\n', ' ').strip()
        
        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': transcription,
            'translation': translation,
            'start_time': format_timestamp(sub_t.start),
            'end_time': format_timestamp(sub_t.end)
        })
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_headers, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), len(subs_orig), len(subs_trans)

# --- Streamlit UI ---
st.set_page_config(page_title="Smart SRT Aligner", layout="wide")

st.title("🎬 Smart SRT Merger (SmartCat Precision)")
st.info("Uses Center-Point alignment to prevent English text from spilling into the wrong rows.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. Original SRT (English)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Translated SRT (Russian)", type=['srt'])

if orig_file and trans_file:
    if st.button("Merge and Generate CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Successfully merged {count_o} English snippets into {count_t} Russian segments!")
            
            st.write("### Preview")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download Corrected CSV",
                data=csv_result.encode('utf-8'),
                file_name="precision_aligned.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
