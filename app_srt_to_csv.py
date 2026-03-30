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
        raise ValueError("SRT files are empty or invalid.")

    # mapping: key = Russian index, value = list of English sub objects
    matched_mapping = {i: [] for i in range(len(subs_trans))}
    
    current_rus_idx = 0
    
    # SEQUENTIAL MONOTONIC OVERLAP LOGIC
    # This ensures English text stays in the order of the speech
    for sub_o in subs_orig:
        o_start = sub_o.start.ordinal
        o_end = sub_o.end.ordinal
        
        best_overlap = -1
        best_idx = current_rus_idx
        
        # We only look at the current Russian segment and the next few 
        # to find where this English snippet belongs
        search_limit = min(current_rus_idx + 3, len(subs_trans))
        
        for i in range(current_rus_idx, search_limit):
            sub_t = subs_trans[i]
            t_start = sub_t.start.ordinal
            t_end = sub_t.end.ordinal
            
            # Calculate intersection
            overlap = min(o_end, t_end) - max(o_start, t_start)
            
            if overlap > best_overlap:
                best_overlap = overlap
                best_idx = i
        
        # If no overlap found (gap), stay with the current index
        if best_overlap <= 0:
            best_idx = current_rus_idx
            
        # Add English snippet to the chosen Russian bucket
        matched_mapping[best_idx].append(sub_o)
        
        # Ensure we never go backwards in the timeline
        current_rus_idx = best_idx

    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # CONSTRUCT FINAL CSV (Always 42 rows if Russian has 42 blocks)
    for i in range(len(subs_trans)):
        sub_t = subs_trans[i]
        assigned_english = matched_mapping[i]
        
        if assigned_english:
            # Join all English text for this segment
            transcription = " ".join([s.text_without_tags.replace('\n', ' ').strip() for s in assigned_english])
            # ABSOLUTE TIMINGS: First English start to Last English end
            start_val = format_timestamp(assigned_english[0].start)
            end_val = format_timestamp(assigned_english[-1].end)
        else:
            # Fallback for empty buckets
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
st.set_page_config(page_title="SmartCat Aligner", layout="wide")

st.title("🎙️ AI Dubbing Aligner (SmartCat Exact)")
st.info("Logic: English snippets are assigned sequentially to the Russian blocks they overlap with most. This mirrors the SmartCat segmentation.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. English SRT (Speech Source)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Russian SRT (SmartCat Export)", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate AI-Ready CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Merged {count_o} English lines into {count_t} Russian segments.")
            
            st.write("### Preview (Aligned by SmartCat Segments)")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download Aligned CSV",
                data=csv_result.encode('utf-8'),
                file_name="smartcat_aligned_dubbing.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
