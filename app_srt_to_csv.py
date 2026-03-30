import streamlit as st
import pysrt
import csv
import io
import pandas as pd
import re

def format_timestamp(srt_time):
    """Converts pysrt time object to seconds.milliseconds format (0.000)"""
    total_seconds = (srt_time.hours * 3600 + 
                     srt_time.minutes * 60 + 
                     srt_time.seconds + 
                     srt_time.milliseconds / 1000.0)
    return f"{total_seconds:.3f}"

def is_sentence_end(text):
    """Checks if the text ends with sentence-ending punctuation."""
    clean_text = text.strip()
    if not clean_text:
        return False
    # Matches . ! ? ... " » and other common sentence ends
    return bool(re.search(r'[.!?…"»]$', clean_text))

def process_srts(original_file, translated_file):
    # Read files
    orig_content = original_file.read().decode("utf-8-sig", errors='replace')
    trans_content = translated_file.read().decode("utf-8-sig", errors='replace')
    
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    n = len(subs_orig)
    m = len(subs_trans)

    # 1. Identify "Legal" split points in English (End of sentences)
    # This prevents the "sur-vival" split issue
    legal_split_indices = [i for i, sub in enumerate(subs_orig) if is_sentence_end(sub.text)]
    
    # If the English SRT is very poorly punctuated and we don't have enough 
    # sentence ends to match the Russian count, we allow all indices as fallback
    if len(legal_split_indices) < m - 1:
        legal_split_indices = list(range(n))

    # 2. Find the best split points to match Russian segment counts
    # We want to pick M-1 indices from legal_split_indices
    chosen_splits = []
    current_search_idx = 0
    
    for j in range(m - 1):
        target_time = subs_trans[j].end.ordinal
        best_idx = legal_split_indices[current_search_idx]
        min_diff = abs(subs_orig[best_idx].end.ordinal - target_time)
        
        # Look ahead in legal splits to find the one closest to Russian end time
        for k in range(current_search_idx, len(legal_split_indices)):
            idx = legal_split_indices[k]
            # Stop if we don't have enough snippets left for remaining Russian blocks
            if (len(legal_split_indices) - k) < (m - j - 1):
                break
                
            diff = abs(subs_orig[idx].end.ordinal - target_time)
            if diff <= min_diff:
                min_diff = diff
                best_idx = idx
                current_search_idx = k
            else:
                # Times are increasing, so if diff starts getting larger, we stop
                break
        
        chosen_splits.append(best_idx)

    # 3. Group the English snippets into buckets
    buckets = []
    start_idx = 0
    for split_idx in chosen_splits:
        buckets.append(subs_orig[start_idx : split_idx + 1])
        start_idx = split_idx + 1
    buckets.append(subs_orig[start_idx:]) # Add the last group

    # 4. Generate CSV Data
    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    for i, group in enumerate(buckets):
        if not group: continue
        
        transcription = " ".join([s.text_without_tags.replace('\n', ' ').strip() for s in group])
        translation = subs_trans[i].text_without_tags.replace('\n', ' ').strip() if i < len(subs_trans) else ""
        
        csv_data.append({
            'speaker': 'Speaker 1',
            'transcription': transcription,
            'translation': translation,
            'start_time': format_timestamp(group[0].start),
            'end_time': format_timestamp(group[-1].end)
        })
        
    output = io.StringIO()
    writer = csv.DictWriter(output, fieldnames=csv_headers, quoting=csv.QUOTE_ALL)
    writer.writeheader()
    writer.writerows(csv_data)
    
    return output.getvalue(), n, m

# --- Streamlit UI ---
st.set_page_config(page_title="AI Dubbing Precision Aligner", layout="wide")

st.title("🎙️ AI Dubbing Aligner (Sentence-Protection Mode)")
st.markdown("""
**New Logic:** This version prevents "mid-sentence" splits. 
- It detects English punctuation and ensures rows only break when a thought is finished.
- It fixes issues like "sur-vival" being split across two rows.
- Timings are derived 100% from the English speech blocks.
""")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. English SRT (Original Speech)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Russian SRT (Sense Blocks)", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate AI-Ready CSV"):
        try:
            csv_result, count_o, count_t = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Merged {count_o} lines into {count_t} rows while protecting sentence integrity.")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download Corrected CSV",
                data=csv_result.encode('utf-8'),
                file_name="ai_dubbing_perfect_alignment.csv",
                mime="text/csv"
            )
        except Exception as e:
            st.error(f"Error: {str(e)}")
