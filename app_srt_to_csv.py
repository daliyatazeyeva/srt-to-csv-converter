import streamlit as st
import pysrt
import csv
import io
import pandas as pd # New tool to show tables correctly

def format_timestamp(srt_time):
    total_seconds = (srt_time.hours * 3600 + 
                     srt_time.minutes * 60 + 
                     srt_time.seconds + 
                     srt_time.milliseconds / 1000.0)
    return f"{total_seconds:.3f}"

def find_matching_translation(orig_start, trans_subs):
    for sub in trans_subs:
        diff = abs(sub.start.ordinal - orig_start.ordinal)
        if diff <= 150: # 150ms tolerance
            return sub
    return None

def process_srts(original_file, translated_file):
    orig_content = original_file.read().decode("utf-8-sig")
    trans_content = translated_file.read().decode("utf-8-sig")
    
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    for sub_o in subs_orig:
        sub_t = find_matching_translation(sub_o.start, subs_trans)
        
        # Clean text and remove line breaks
        transcription = sub_o.text_without_tags.replace('\n', ' ').strip()
        translation = sub_t.text_without_tags.replace('\n', ' ').strip() if sub_t else ""
        
        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': transcription,
            'translation': translation,
            'start_time': format_timestamp(sub_o.start),
            'end_time': format_timestamp(sub_o.end)
        })
        
    output = io.StringIO()
    # QUOTE_ALL ensures that even if there are commas in the text, the CSV stays organized
    writer = csv.DictWriter(output, fieldnames=csv_headers, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), len(subs_orig), len(subs_trans)

# --- Streamlit UI ---
st.set_page_config(page_title="SRT Smart Merger", layout="wide")

st.title("🎬 Smart SRT Merger")
st.info("Fixed: Commas in text will no longer break columns.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. Original SRT", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Translated SRT", type=['srt'])

if orig_file and trans_file:
    if st.button("Merge and Generate CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            
            # Use Pandas to read the CSV result correctly for the preview
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Processed {count_o} lines.")
            
            st.write("### Preview")
            # This will now look perfect and aligned
            st.dataframe(df.head(10), use_container_width=True)

            st.download_button(
                label="📥 Download Merged CSV",
                data=csv_result.encode('utf-8'),
                file_name="aligned_subtitles.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
