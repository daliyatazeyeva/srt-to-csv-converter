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

def group_into_full_sentences(subs):
    """
    Groups raw SRT blocks into full sentences based on punctuation.
    Returns a list of dictionaries with merged text and timing.
    """
    sentences = []
    current_text = []
    start_time = None
    
    for sub in subs:
        if start_time is None:
            start_time = sub.start
            
        text = sub.text_without_tags.replace('\n', ' ').strip()
        current_text.append(text)
        
        # Check if this block ends a sentence
        # Looks for . ! ? or ... at the end of the string
        if re.search(r'[.!?…]$', text):
            sentences.append({
                'text': " ".join(current_text),
                'start': start_time,
                'end': sub.end
            })
            current_text = []
            start_time = None
            
    # Catch any leftover text if the file didn't end with a period
    if current_text:
        sentences.append({
            'text': " ".join(current_text),
            'start': start_time,
            'end': subs[-1].end
        })
        
    return sentences

def process_srts(original_file, translated_file):
    orig_content = original_file.read().decode("utf-8-sig", errors='replace')
    trans_content = translated_file.read().decode("utf-8-sig", errors='replace')
    
    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)
    
    # 1. Reconstruct English into FULL PROPER SENTENCES
    eng_sentences = group_into_full_sentences(subs_orig)
    
    # 2. Map these full sentences to Russian "Sense Blocks"
    # We use the midpoint of the silence between Russian blocks as boundaries
    boundaries = []
    for i in range(len(subs_trans) - 1):
        midpoint = (subs_trans[i].end.ordinal + subs_trans[i+1].start.ordinal) / 2
        boundaries.append(midpoint)
    
    # Buckets for English sentences
    buckets = {i: [] for i in range(len(subs_trans))}
    
    for eng_s in eng_sentences:
        # Use the start time of the sentence to determine its bucket
        s_start = eng_s['start'].ordinal
        
        target_idx = 0
        for i, b in enumerate(boundaries):
            if s_start > b:
                target_idx = i + 1
            else:
                break
        buckets[target_idx].append(eng_s)

    # 3. Create the CSV rows
    csv_data = []
    csv_headers = ['speaker', 'transcription', 'translation', 'start_time', 'end_time']
    
    for i in range(len(subs_trans)):
        assigned_eng = buckets[i]
        sub_t = subs_trans[i]
        
        if assigned_eng:
            # Merged text of all sentences in this bucket
            transcription = " ".join([s['text'] for s in assigned_eng])
            # Timing priority: TRUE English Start and End
            start_val = format_timestamp(assigned_eng[0]['start'])
            end_val = format_timestamp(assigned_eng[-1]['end'])
        else:
            # If no English sentence started in this Russian window
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
    
    return output.getvalue(), len(eng_sentences), len(subs_trans)

# --- Streamlit UI ---
st.set_page_config(page_title="Proper Sentence Aligner", layout="wide")

st.title("🎙️ AI Dubbing Aligner (Full Sentence Mode)")
st.markdown("""
**New Logic:**
1. **English Reconstruction:** All fragmented English lines are glued back together into **full proper sentences** based on punctuation.
2. **Zero Splitting:** An English sentence will **never** be cut in half.
3. **Timing Priority:** Every row uses the exact English start and end timestamps.
""")

col1, col2 = st.columns(2)

with col1:
    orig_file = st.file_uploader("1. English SRT (Master Timing)", type=['srt'])

with col2:
    trans_file = st.file_uploader("2. Russian SRT (Sense Segments)", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate Final CSV"):
        try:
            csv_result, eng_count, rus_count = process_srts(orig_file, trans_file)
            df = pd.read_csv(io.StringIO(csv_result))
            
            st.success(f"Aligned {eng_count} English sentences into {rus_count} Russian segments.")
            st.dataframe(df, use_container_width=True)

            st.download_button(
                label="📥 Download Aligned CSV",
                data=csv_result.encode('utf-8'),
                file_name="final_sentence_aligned.csv",
                mime="text/csv"
            )
        except Exception as e:
            st.error(f"Error: {str(e)}")
