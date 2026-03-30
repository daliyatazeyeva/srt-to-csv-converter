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
    # Read and parse
    orig_content = original_file.read().decode("utf-8-sig", errors='replace')
    trans_content = translated_file.read().decode("utf-8-sig", errors='replace')
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    if not subs_orig or not subs_trans:
        raise ValueError("One of the SRT files is empty.")

    # 1. CREATE BOUNDARIES between Russian segments
    # This defines the "territory" for each row.
    boundaries = []
    for i in range(len(subs_trans) - 1):
        # Boundary is exactly halfway between one segment's end and the next's start
        midpoint = (subs_trans[i].end.ordinal + subs_trans[i+1].start.ordinal) / 2
        boundaries.append(midpoint)
    
    # matched_mapping stores the English SubRipItems for each Russian segment index
    matched_mapping = {i: [] for i in range(len(subs_trans))}
    
    # 2. ASSIGN English subtitles to the correct Russian territory
    for sub_o in subs_orig:
        # We use the Start Time of the speech to decide which bucket it belongs to
        o_start = sub_o.start.ordinal
        
        target_idx = 0
        for i, boundary in enumerate(boundaries):
            if o_start > boundary:
                target_idx = i + 1
            else:
                break
        
        clean_o = sub_o.text_without_tags.replace('\n', ' ').strip()
        if clean_o:
            matched_mapping[target_idx].append(sub_o)

    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # 3. CONSTRUCT final CSV rows
    for i, sub_t in enumerate(subs_trans):
        assigned_english = matched_mapping[i]
        
        if assigned_english:
            # Merge all English text assigned to this Russian row
            transcription = " ".join([s.text_without_tags.replace('\n', ' ').strip() for s in assigned_english])
            # Use the TRUE START of the first English word and TRUE END of the last English word
            start_val = format_timestamp(assigned_english[0].start)
            end_val = format_timestamp(assigned_english[-1].end)
        else:
            transcription = ""
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
st.set_page_config(page_title="AI Dubbing Aligner", layout="wide")

st.title("🎙️ AI Dubbing Aligner (Midpoint Logic)")
st.info("Reverted to Midpoint Boundary logic as it provides better row-to-row alignment for these files.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. English SRT (Speech)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Russian SRT (Translation)", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate Aligned CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Merged {count_o} snippets into {count_t} sense-blocks.")
            
            st.write("### Preview Alignment")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download Corrected CSV",
                data=csv_result.encode('utf-8'),
                file_name="dubbing_aligned.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
