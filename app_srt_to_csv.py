import streamlit as st
import pysrt
import csv
import io
import pandas as pd
import re
import difflib
from deep_translator import GoogleTranslator

def format_timestamp(srt_time):
    """Converts pysrt time object to total seconds as a string."""
    total_seconds = (srt_time.hours * 3600 + 
                     srt_time.minutes * 60 + 
                     srt_time.seconds + 
                     srt_time.milliseconds / 1000.0)
    return f"{total_seconds:.3f}"

def clean_text(text):
    if not text: return ""
    cleaned = re.sub(r'<[^>]*>', '', text)
    cleaned = re.sub(r'[\r\n]+', ' ', cleaned)
    return cleaned.strip()

def get_full_english_sentences(subs):
    """Groups English SRT fragments into whole sentences based on punctuation."""
    sentences = []
    current_items = []
    
    for sub in subs:
        current_items.append(sub)
        text = sub.text.strip()
        if re.search(r'[.!?…]$', text):
            sentences.append({
                'text': " ".join([clean_text(s.text) for s in current_items]),
                'start': current_items[0].start,
                'end': current_items[-1].end
            })
            current_items = []
            
    if current_items:
        sentences.append({
            'text': " ".join([clean_text(s.text) for s in current_items]),
            'start': current_items[0].start,
            'end': current_items[-1].end
        })
    return sentences

def get_full_sentences_generic(subs):
    """Groups SRT blocks into full sentences based on punctuation."""
    sentences_text = []
    current_sentence = []

    for sub in subs:
        text = clean_text(sub.text)
        current_sentence.append(text)
        if re.search(r"[.!?…]$", text.strip()):
            sentences_text.append(" ".join(current_sentence))
            current_sentence = []

    if current_sentence:
        sentences_text.append(" ".join(current_sentence))

    return sentences_text


def find_best_russian_match(translated_eng, rus_sentences, search_start_idx):
    """Finds the Russian sentence that is most similar to the translated English sentence."""
    best_score = 0
    best_idx = search_start_idx

    # We search in a window of 5 sentences forward to keep things in order
    search_window = 5
    end_idx = min(search_start_idx + search_window, len(rus_sentences))

    for i in range(search_start_idx, end_idx):
        rus_s = rus_sentences[i]
        # Calculate text similarity ratio (0.0 to 1.0)
        score = difflib.SequenceMatcher(None, translated_eng, rus_s).ratio()

        if score > best_score:
            best_score = score
            best_idx = i

    # If even the best match is terrible (below 15% similarity), return original index to avoid jumping
    if best_score < 0.15:
        return search_start_idx

    return best_idx


def process_srts(original_file, translated_file):
    orig_content = original_file.read().decode("utf-8-sig", errors="replace")
    trans_content = translated_file.read().decode("utf-8-sig", errors="replace")

    subs_orig = pysrt.from_string(orig_content)
    subs_trans = pysrt.from_string(trans_content)

    # 1. Reconstruct English into sentences AND keep their original timings
    eng_sentences = get_full_english_sentences(subs_orig)

    # 2. Reconstruct Russian into full sentences
    rus_sentences = get_full_sentences_generic(subs_trans)

    csv_data = []
    csv_headers = [
        "speaker",
        "transcription",
        "translation",
        "start_time",
        "end_time",
    ]

    current_rus_idx = 0
    translator = GoogleTranslator(source="en", target="ru")

    st.info(
        "🧠 Semantic Alignment in progress. This may take a minute as it translates English sentences to map them..."
    )

    for i, eng_s in enumerate(eng_sentences):
        eng_text = eng_s["text"]

        try:
            # A. Translate the target English sentence to Russian
            ai_translated_eng = translator.translate(eng_text)

            # B. Find which real Russian sentence from the file matches it best
            matched_rus_idx = find_best_russian_match(
                ai_translated_eng, rus_sentences, current_rus_idx
            )

            # C. Assign text
            if matched_rus_idx < len(rus_sentences):
                full_translation = rus_sentences[matched_rus_idx]
                # Advance the search window so we don't look backwards
                current_rus_idx = matched_rus_idx + 1
            else:
                full_translation = "[TRANSLATION MISSING]"

        except Exception as e:
            # Fallback to pure index matching if internet/translation fails
            if i < len(rus_sentences):
                full_translation = rus_sentences[i]
            else:
                full_translation = "[TRANSLATION MISSING]"

        full_translation = re.sub(r"\s+", " ", full_translation).strip()

        csv_data.append(
            {
                "speaker": "Speaker 1",
                "transcription": eng_text,
                "translation": full_translation,
                "start_time": format_timestamp(eng_s["start"]),
                "end_time": format_timestamp(eng_s["end"]),
            }
        )

    output = io.StringIO()
    writer = csv.DictWriter(
        output, fieldnames=csv_headers, quoting=csv.QUOTE_ALL
    )
    writer.writeheader()
    writer.writerows(csv_data)

    return output.getvalue(), len(eng_sentences)

# --- Streamlit UI ---
st.set_page_config(page_title="AI Dubbing Aligner", layout="wide")
st.title("🎙️ AI Dubbing Aligner (Robust Timing Mode)")

col1, col2 = st.columns(2)
with col1:
    orig_file = st.file_uploader("1. English SRT", type=['srt'])
with col2:
    trans_file = st.file_uploader("2. Translated SRT", type=['srt'])

if orig_file and trans_file:
    if st.button("Generate Final CSV"):
        csv_result, count = process_srts(orig_file, trans_file)
        df = pd.read_csv(io.StringIO(csv_result))
        
        # IMPORTANT: Don't sort the dataframe here, keep natural order
        st.success(f"Aligned {count} segments.")
        st.dataframe(df)

        st.download_button("📥 Download CSV", data=csv_result.encode('utf-8-sig'), file_name="final_align.csv")
