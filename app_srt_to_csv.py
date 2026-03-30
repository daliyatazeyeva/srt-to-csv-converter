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
    # Read files
    orig_content = original_file.read().decode("utf-8-sig", errors='replace')
    trans_content = translated_file.read().decode("utf-8-sig", errors='replace')
    
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    if not subs_orig or not subs_trans:
        raise ValueError("One of the SRT files is empty.")

    # matched_mapping stores the English SubRipItems for each Russian segment index
    matched_mapping = {i: [] for i in range(len(subs_trans))}
    
    last_assigned_idx = 0

    # PRECISION SEQUENTIAL ALIGNMENT
    for sub_o in subs_orig:
        o_start = sub_o.start.ordinal
        o_end = sub_o.end.ordinal
        o_center = o_start + (sub_o.duration.ordinal / 2)
        
        best_idx = last_assigned_idx
        max_overlap = -1
        
        # Look at the current Russian segment and the next few to find the best home
        # We search a small window to ensure we don't 'skip' segments
        search_window = range(last_assigned_idx, min(last_assigned_idx + 4, len(subs_trans)))
        
        for i in search_window:
            sub_t = subs_trans[i]
            t_start = sub_t.start.ordinal
            t_end = sub_t.end.ordinal
            
            # Calculate how much this English snippet 'lives' in this Russian block
            overlap = min(o_end, t_end) - max(o_start, t_start)
            
            if overlap > max_overlap:
                max_overlap = overlap
                best_idx = i
        
        # If there's no overlap (it's in a gap), assign to the closest segment 
        # but NEVER go backwards in time
        if max_overlap <= 0:
            min_dist = float('inf')
            for i in search_window:
                t_center = subs_trans[i].start.ordinal + (subs_trans[i].duration.ordinal / 2)
                dist = abs(o_center - t_center)
                if dist < min_dist:
                    min_dist = dist
                    best_idx = i
        
        matched_mapping[best_idx].append(sub_o)
        last_assigned_idx = best_idx

    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    for i, sub_t in enumerate(subs_trans):
        assigned_english = matched_mapping[i]
        
        if assigned_english:
            # COMBINE TEXT
            transcription = " ".join([s.text_without_tags.replace('\n', ' ').strip() for s in assigned_english])
            
            # TRUE ENGLISH TIMINGS (Priority)
            # Take the absolute start of the first assigned English snippet
            # and the absolute end of the last assigned English snippet
            start_val = format_timestamp(assigned_english[0].start)
            end_val = format_timestamp(assigned_english[-1].end)
        else:
            # If a Russian block has no English (empty segment in SmartCat)
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
st.set_page_config(page_title="AI Dubbing Aligner Pro", layout="wide")

st.title("🎙️ AI Dubbing Aligner (Precision Mode)")
st.markdown("""
**Correcting Rows 18 & 35:** This version uses 'Sequential Overlap' logic. 
It ensures English snippets never jump into the wrong 'sense' block, even if timing shifts occur.
""")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. English SRT (Original Speech)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Russian SRT (SmartCat Export)", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate Final AI-Ready CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Successfully aligned {count_o} English lines into {count_t} Russian segments.")
            
            st.write("### Review Final Alignment")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download Final CSV",
                data=csv_result.encode('utf-8'),
                file_name="ai_dubbing_precision.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
