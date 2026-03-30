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
    # Read and parse with universal encoding support
    orig_content = original_file.read().decode("utf-8-sig", errors='replace')
    trans_content = translated_file.read().decode("utf-8-sig", errors='replace')
    
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    if not subs_orig or not subs_trans:
        raise ValueError("One of the SRT files appears to be empty or invalid.")

    # matched_mapping stores the English SubRipItems for each Translation segment index
    # This automatically adjusts to the number of rows in the Translation file
    matched_mapping = {i: [] for i in range(len(subs_trans))}
    
    # 1. CREATE BOUNDARIES between Translation segments
    # This logic adapts to any number of segments
    boundaries = []
    for i in range(len(subs_trans) - 1):
        # Boundary is halfway between end of block A and start of block B
        midpoint = (subs_trans[i].end.ordinal + subs_trans[i+1].start.ordinal) / 2
        boundaries.append(midpoint)
    
    # 2. ASSIGN Original subtitles to Buckets
    for sub_o in subs_orig:
        o_center = sub_o.start.ordinal + (sub_o.duration.ordinal / 2)
        
        target_idx = 0
        for i, boundary in enumerate(boundaries):
            if o_center > boundary:
                target_idx = i + 1
            else:
                break
        matched_mapping[target_idx].append(sub_o)

    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # 3. CONSTRUCT the merged blocks using Original Speech Timings
    for i, sub_t in enumerate(subs_trans):
        assigned_orig = matched_mapping[i]
        
        # If original speech was found for this segment
        if assigned_orig:
            transcription = " ".join([s.text_without_tags.replace('\n', ' ').strip() for s in assigned_orig])
            # Use the true start of the first speech snippet and end of the last speech snippet
            start_val = format_timestamp(assigned_orig[0].start)
            end_val = format_timestamp(assigned_orig[-1].end)
        else:
            # Fallback to translation timing if no speech was found in this window
            transcription = "[No matching speech]"
            start_val = format_timestamp(sub_t.start)
            end_val = format_timestamp(sub_t.end)

        translation = sub_t.text_without_tags.replace('\n', ' ').strip()
        
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
st.set_page_config(page_title="Universal AI Dubbing Aligner", layout="wide")

st.title("🎙️ Universal SRT Aligner for AI Dubbing")
st.markdown("""
**How this works for any video:**
1. Upload your original speech SRT and your translated SRT.
2. The tool creates 'buckets' based on your **Translation segments**.
3. It captures the **exact start and end** of the original speech for each bucket.
4. It outputs a CSV ready for AI Dubbing tools.
""")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. Original Speech SRT (Master Timings)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Translated SRT (Sense Segments)", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate AI-Ready CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Successfully processed! Original: {count_o} lines merged into {count_t} sense-blocks.")
            
            st.write("### Final Alignment Preview")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download AI-Ready CSV",
                data=csv_result.encode('utf-8'),
                file_name="ai_dubbing_aligned.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
            st.info("Ensure both files are valid .srt format.")
