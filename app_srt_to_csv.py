import streamlit as st
import pysrt
import csv
import io
import pandas as pd

def format_timestamp(srt_time):
    total_seconds = (srt_time.hours * 3600 + 
                     srt_time.minutes * 60 + 
                     srt_time.seconds + 
                     srt_time.milliseconds / 1000.0)
    return f"{total_seconds:.3f}"

def get_combined_english(trans_sub, orig_subs):
    """Finds all English blocks that overlap with a Russian block's time."""
    overlapping_text = []
    # Convert Russian start/end to milliseconds for comparison
    t_start = trans_sub.start.ordinal
    t_end = trans_sub.end.ordinal
    
    for sub_o in orig_subs:
        o_start = sub_o.start.ordinal
        o_end = sub_o.end.ordinal
        
        # Check if the English block overlaps with the Russian block time
        # Logic: (StartA <= EndB) and (EndA >= StartB)
        if (o_start <= t_end + 100) and (o_end >= t_start - 100):
            clean_text = sub_o.text_without_tags.replace('\n', ' ').strip()
            overlapping_text.append(clean_text)
            
    return " ".join(overlapping_text)

def process_srts(original_file, translated_file):
    orig_content = original_file.read().decode("utf-8-sig")
    trans_content = translated_file.read().decode("utf-8-sig")
    
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # We iterate through the TRANSLATION as the master list
    # because that represents the final "segments" as seen in SmartCat
    for sub_t in subs_trans:
        # Combine all English snippets that belong to this Russian segment
        transcription = get_combined_english(sub_t, subs_orig)
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
st.set_page_config(page_title="SRT Smart Merger", layout="wide")

st.title("🎬 Smart SRT Merger (SmartCat Optimized)")
st.info("This version merges English segments to match the Russian segment structure.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. Original SRT", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Translated SRT", type=['srt'])

if orig_file and trans_file:
    if st.button("Merge and Generate CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Merged {count_o} English lines into {count_t} Russian segments.")
            
            st.write("### Preview")
            st.dataframe(df.head(15), use_container_width=True)

            st.download_button(
                label="📥 Download Corrected CSV",
                data=csv_result.encode('utf-8'),
                file_name="smartcat_aligned.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
