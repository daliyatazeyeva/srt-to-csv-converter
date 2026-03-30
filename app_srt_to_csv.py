import streamlit as st
import pysrt
import csv
import io

def format_timestamp(srt_time):
    """Converts pysrt time object to seconds.milliseconds format (0.000)"""
    total_seconds = (srt_time.hours * 3600 + 
                     srt_time.minutes * 60 + 
                     srt_time.seconds + 
                     srt_time.milliseconds / 1000.0)
    return f"{total_seconds:.3f}"

def find_matching_translation(orig_start, trans_subs, threshold=0.1):
    """Finds a translation block that starts at the same time as the original."""
    for sub in trans_subs:
        # Convert times to total milliseconds for easy comparison
        diff = abs(sub.start.ordinal - orig_start.ordinal)
        if diff <= 100: # 100ms tolerance for slight timing shifts
            return sub
    return None

def process_srts(original_file, translated_file):
    orig_content = original_file.read().decode("utf-8-sig")
    trans_content = translated_file.read().decode("utf-8-sig")
    
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # We iterate through the ORIGINAL subtitles as the master list
    for sub_o in subs_orig:
        # Look for a translation block that matches this timing
        sub_t = find_matching_translation(sub_o.start, subs_trans)
        
        transcription = sub_o.text_without_tags.replace('\n', ' ').strip()
        translation = sub_t.text_without_tags.replace('\n', ' ').strip() if sub_t else ""
        
        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': transcription,
            'translation': translation,
            'start_time': format_timestamp(sub_o.start),
            'end_time': format_timestamp(sub_o.end)
        })
        
    # Generate CSV string
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_headers)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), len(subs_orig), len(subs_trans)

# --- Streamlit UI ---
st.set_page_config(page_title="SRT Smart Merger", layout="centered")

st.title("🎬 Smart SRT Merger")
st.info("This version aligns text by **Timestamps**, fixing SmartCat export issues.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. Original SRT", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Translated SRT", type=['srt'])

if orig_file and trans_file:
    if st.button("Merge and Generate CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            
            st.success(f"Processed {count_o} original lines.")
            if count_o != count_t:
                st.warning(f"Note: Original has {count_o} blocks, Translation has {count_t}. We aligned them by time.")

            # Preview
            st.write("### Preview (First 5 rows)")
            preview_lines = csv_result.splitlines()[:6]
            st.table([line.split(',') for line in preview_lines])

            # Download
            st.download_button(
                label="📥 Download Merged CSV",
                data=csv_result.encode('utf-8'),
                file_name="time_aligned_subtitles.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
