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
        raise ValueError("One of the SRT files is empty or invalid.")

    # matched_mapping stores the English SubRipItems for each Russian segment index
    matched_mapping = {i: [] for i in range(len(subs_trans))}
    
    # NEW LOGIC: Maximum Overlap Assignment
    for sub_o in subs_orig:
        o_start = sub_o.start.ordinal
        o_end = sub_o.end.ordinal
        o_center = o_start + (sub_o.duration.ordinal / 2)
        
        best_match_idx = 0
        max_overlap = -1
        
        # 1. Try to find the segment with the most timing overlap
        for i, sub_t in enumerate(subs_trans):
            t_start = sub_t.start.ordinal
            t_end = sub_t.end.ordinal
            
            # Calculate intersection/overlap in milliseconds
            overlap = min(o_end, t_end) - max(o_start, t_start)
            
            if overlap > max_overlap:
                max_overlap = overlap
                best_match_idx = i
        
        # 2. If no physical overlap (it's in a silence gap), 
        # assign to the segment whose center is mathematically closest
        if max_overlap <= 0:
            min_dist = float('inf')
            for i, sub_t in enumerate(subs_trans):
                t_center = sub_t.start.ordinal + (sub_t.duration.ordinal / 2)
                dist = abs(o_center - t_center)
                if dist < min_dist:
                    min_dist = dist
                    best_match_idx = i
        
        clean_o = sub_o.text_without_tags.replace('\n', ' ').strip()
        if clean_o:
            matched_mapping[best_match_idx].append(sub_o)

    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    # Construct final rows based on the Russian "Sense" segments
    for i, sub_t in enumerate(subs_trans):
        assigned_english = matched_mapping[i]
        
        if assigned_english:
            # Combine all English snippets for this segment
            transcription = " ".join([s.text_without_tags.replace('\n', ' ').strip() for s in assigned_english])
            # Use the absolute beginning and end of the English speech in this bucket
            start_val = format_timestamp(assigned_english[0].start)
            end_val = format_timestamp(assigned_english[-1].end)
        else:
            # Fallback if no English was found for this Russian block
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

st.title("🎙️ AI Dubbing Aligner (Overlap-Priority)")
st.info("Logic: Matches English snippets to the Russian segment they share the most time with. High precision for SmartCat files.")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. English SRT (Original Speech)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Russian SRT (Translation Segments)", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate Final Aligned CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Merged {count_o} snippets into {count_t} rows.")
            
            st.write("### Review Alignment")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download AI Dubbing CSV",
                data=csv_result.encode('utf-8'),
                file_name="ai_dubbing_final.csv",
                mime="text/csv"
            )
            
        except Exception as e:
            st.error(f"Error: {str(e)}")
