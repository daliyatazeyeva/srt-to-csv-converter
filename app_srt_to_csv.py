import streamlit as st
import pysrt
import csv
import io
from itertools import zip_longest

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
    
    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    for sub_o, sub_t in zip_longest(subs_orig, subs_trans):
        # Skip if both are empty
        if not sub_o and not sub_t:
            continue
            
        # Get cleaned text (removing <i></i> tags etc.)
        # Note: .text_without_tags is a property, so no ()
        transcription = sub_o.text_without_tags if sub_o else ""
        translation = sub_t.text_without_tags if sub_t else ""
        
        # Timing comes from original, if missing use translation timing
        if sub_o:
            start = format_timestamp(sub_o.start)
            end = format_timestamp(sub_o.end)
        elif sub_t:
            start = format_timestamp(sub_t.start)
            end = format_timestamp(sub_t.end)
        else:
            start = "0.000"
            end = "0.000"

        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': transcription.replace('\n', ' ').strip(),
            'translation': translation.replace('\n', ' ').strip(),
            'start_time': start,
            'end_time': end
        })
        
    # Generate CSV string
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_headers)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), len(subs_orig), len(subs_trans)

# --- Streamlit UI ---
st.set_page_config(page_title="SRT to CSV Merger", layout="centered")

st.title("🎬 SRT Merger to CSV")
st.write("Upload two SRT files to merge them into a single CSV.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. Original SRT (Source)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Translated SRT (Target)", type=['srt'])

if orig_file and trans_file:
    if st.button("Merge and Generate CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            
            if count_o != count_t:
                st.warning(f"⚠️ Mismatch! Original: {count_o} lines, Translated: {count_t} lines.")
            else:
                st.success(f"Successfully merged {count_o} subtitles!")

            # Preview
            st.write("### Preview")
            preview_lines = csv_result.splitlines()[:6]
            st.text("\n".join(preview_lines))

            # Download
            st.download_button(
                label="📥 Download Merged CSV",
                data=csv_result.encode('utf-8'),
                file_name="merged_subtitles.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error processing files: {str(e)}")
            st.info("Check if files are valid SRT format.")
