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
    # We decode using utf-8-sig to handle files with BOM (common in SRTs)
    orig_content = original_file.read().decode("utf-8-sig")
    trans_content = translated_file.read().decode("utf-8-sig")
    
    # Parse SRT content
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # We use zip_longest to ensure we don't crash if file lengths differ
    # We use the timing from the ORIGINAL file as the master timing
    for sub_o, sub_t in zip_longest(subs_orig, subs_trans):
        # Fallback values if one file is shorter than the other
        transcription = sub_o.text if sub_o else ""
        translation = sub_t.text if sub_t else ""
        
        # Timing must come from original, if missing use translation timing, if both missing skip
        if sub_o:
            start = format_timestamp(sub_o.start)
            end = format_timestamp(sub_o.end)
        elif sub_t:
            start = format_timestamp(sub_t.start)
            end = format_timestamp(sub_t.end)
        else:
            continue

        # Clean HTML tags (like <i></i>) which are common in SRTs
        clean_transcription = pysrt.SubRipItem.text_without_tags(sub_o) if sub_o else ""
        clean_translation = pysrt.SubRipItem.text_without_tags(sub_t) if sub_t else ""

        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': clean_transcription.replace('\n', ' '),
            'translation': clean_translation.replace('\n', ' '),
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
st.write("Upload two SRT files. The timing will be taken from the Original file.")

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
                st.warning(f"⚠️ Note: File lengths differ. Original: {count_o} subs, Translated: {count_t} subs.")
            else:
                st.success(f"Successfully merged {count_o} subtitles!")

            # Preview
            st.write("### Preview (First 5 rows)")
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
            st.error(f"Error processing files: {e}")
            st.info("Ensure your files are valid .srt files and encoded in UTF-8.")

st.markdown("""
---
**Instructions:**
1. Upload the original language SRT.
2. Upload the translated language SRT.
3. The tool will match them by index (Subtitle 1 with Subtitle 1).
4. Download the final CSV for your workflow.
""")