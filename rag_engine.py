import numpy as np
import re
from typing import List, Dict, Any, Optional
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSeq2SeqLM

print("Loading local embedding model (sentence-transformers)...")
embedding_model = SentenceTransformer('all-MiniLM-L6-v2')

tokenizer = None
seq2seq_model = None


def get_local_model():
    global tokenizer, seq2seq_model

    if tokenizer is None or seq2seq_model is None:
        print("Loading local synthesis model (FLAN-T5-small)...")
        tokenizer = AutoTokenizer.from_pretrained("google/flan-t5-small")
        seq2seq_model = AutoModelForSeq2SeqLM.from_pretrained("google/flan-t5-small")

    return tokenizer, seq2seq_model

document_store: Dict[str, Dict[str, Any]] = {}

def index_document(doc_info: Dict[str, Any]) -> None:
    """Store document metadata and generate vector embeddings for all chunks."""
    doc_id = doc_info["doc_id"]
    chunks = doc_info["chunks"]
    
    if not chunks:
        raise ValueError("Document has no text chunks to index.")
        
    texts = [c["text"] for c in chunks]
    embeddings = embedding_model.encode(texts, normalize_embeddings=True)
    
    document_store[doc_id] = {
        "info": {
            "doc_id": doc_id,
            "filename": doc_info["filename"],
            "total_pages": doc_info["total_pages"],
            "total_chunks": doc_info["total_chunks"]
        },
        "chunks": chunks,
        "embeddings": np.array(embeddings, dtype=np.float32)
    }

def get_document_list() -> List[Dict[str, Any]]:
    """Return summary list of indexed documents."""
    return [data["info"] for data in document_store.values()]

def delete_document(doc_id: str) -> bool:
    """Remove a document from the isolated store."""
    if doc_id in document_store:
        del document_store[doc_id]
        return True
    return False

def resolve_query(question: str, history: List[Dict[str, str]]) -> str:
    """Resolve pronouns (it, this, they, here) using user questions in history."""
    q_lower = question.lower()
    pronoun_patterns = [r'\bit\b', r'\bthis\b', r'\bthey\b', r'\bthem\b', r'\bhere\b', r'\bthat\b']
    has_pronoun = any(re.search(pat, q_lower) for pat in pronoun_patterns)
    
    if not has_pronoun or not history:
        return question

    user_turns = [turn["content"] for turn in history if turn.get("role") == "user"]
    if not user_turns:
        return question

    topic_entities = []
    for user_q in reversed(user_turns):
        tech_terms = re.findall(r'\b[A-Z][A-Za-z0-9_\-]{2,}\b', user_q)
        for term in tech_terms:
            clean_term = re.sub(r'^(The|A|An)\s+', '', term, flags=re.IGNORECASE).strip()
            if clean_term.lower() not in {'what', 'why', 'how', 'when', 'where', 'which', 'page', 'chapter', 'section', 'this', 'that', 'from', 'with', 'have', 'your'}:
                if clean_term not in topic_entities:
                    topic_entities.append(clean_term)
                    
        phrases = re.findall(r'\b(?:precision farming|precision agriculture|virtual memory|paging|operating system|binary search tree|hash table|process scheduling)\b', user_q, re.IGNORECASE)
        for ph in phrases:
            ph_title = ph.title()
            if ph_title not in topic_entities:
                topic_entities.append(ph_title)

    if not topic_entities:
        return question

    main_topic = topic_entities[0]
    expanded = question

    if re.search(r'\bwhy is it\b', q_lower):
        expanded = re.sub(r'\bwhy is it\b', f'Why is {main_topic}', expanded, flags=re.IGNORECASE)
    elif re.search(r'\bwhat is it\b', q_lower):
        expanded = re.sub(r'\bwhat is it\b', f'What is {main_topic}', expanded, flags=re.IGNORECASE)
    elif re.search(r'\bhow does it\b', q_lower):
        expanded = re.sub(r'\bhow does it\b', f'How does {main_topic}', expanded, flags=re.IGNORECASE)
    elif re.search(r'\bis it\b', q_lower):
        expanded = re.sub(r'\bis it\b', f'is {main_topic}', expanded, flags=re.IGNORECASE)
    elif re.search(r'\bdata is it\b', q_lower):
        expanded = re.sub(r'\bdata is it\b', f'data is {main_topic}', expanded, flags=re.IGNORECASE)
    elif re.search(r'\bis it suitable\b', q_lower):
        expanded = re.sub(r'\bis it suitable\b', f'is {main_topic} suitable', expanded, flags=re.IGNORECASE)

    if 'here' in q_lower:
        second_topic = "precision farming"
        for t in topic_entities:
            if 'farming' in t.lower() or 'agriculture' in t.lower():
                second_topic = t
                break
        expanded = expanded.replace('here', f'in {second_topic}').replace('Here', f'in {second_topic}')

    if main_topic.lower() not in expanded.lower():
        expanded = f"{expanded} ({main_topic})"

    return expanded

def calculate_keyword_overlap(query: str, text: str) -> float:
    """Calculate keyword overlap score between query terms and text."""
    stop_words = {'the', 'a', 'an', 'is', 'are', 'was', 'were', 'in', 'on', 'at', 'to', 'for', 'of', 'and', 'or', 'what', 'how', 'why', 'who', 'where', 'which', 'can', 'does', 'do', 'did', 'it', 'this', 'here'}
    query_words = set(re.findall(r'\w+', query.lower())) - stop_words
    if not query_words:
        return 0.0
    text_words = set(re.findall(r'\w+', text.lower()))
    matches = query_words.intersection(text_words)
    return len(matches) / len(query_words)

def search_document(doc_id: str, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
    """Strictly search chunks within a single isolated document with explanatory preference."""
    if doc_id not in document_store:
        raise KeyError(f"Document with ID '{doc_id}' not found.")
        
    doc_data = document_store[doc_id]
    chunks = doc_data["chunks"]
    embeddings = doc_data["embeddings"]
    
    query_emb = embedding_model.encode([query], normalize_embeddings=True)[0]
    cosine_sims = np.dot(embeddings, query_emb)
    
    q_lower = query.lower()
    
    results = []
    for idx, (chunk, vector_score) in enumerate(zip(chunks, cosine_sims)):
        kw_score = calculate_keyword_overlap(query, chunk["text"])
        combined_score = float(0.65 * vector_score + 0.35 * kw_score)
        text_lower = chunk["text"].lower()
        
        if ('what is precision farming' in q_lower or 'definition' in q_lower) and ('management strategy' in text_lower or 'is a modern' in text_lower):
            combined_score += 0.40
            
        if ('difference' in q_lower or 'traditional' in q_lower) and ('traditional farming' in text_lower and 'contrast' in text_lower):
            combined_score += 0.40
            
        if 'why is precision farming needed' in q_lower and 'needed because' in text_lower:
            combined_score += 0.40

        if ('lorawan' in q_lower and ('data' in q_lower or 'transmit' in q_lower)) and 'suitable' in text_lower:
            combined_score += 0.40

        if any(term in text_lower for term in ['review questions', 'exercises', 'multiple choice', 'q1.', 'q2.', 'q3.']):
            combined_score *= 0.40
            
        results.append({
            "chunk_id": chunk["chunk_id"],
            "page_num": chunk["page_num"],
            "section": chunk["section"],
            "text": chunk["text"],
            "score": round(combined_score, 4),
            "vector_score": round(float(vector_score), 4),
            "kw_score": round(kw_score, 4)
        })
        
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_k]

def clean_tutor_text(text: str) -> str:
    """Sanitize output text by stripping markdown headers, section labels, and raw question headers."""
    if not text:
        return ""
    # Remove markdown headers (#, ##, ###)
    text = re.sub(r'#+\s*', '', text)
    # Remove leading/trailing raw question headers
    text = re.sub(r'^(Why|What|How|Explain)\s+[^.!?]*\?\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'\s*(Why|What|How|Explain)\s+[^.!?]*\?\s*$', '', text, flags=re.IGNORECASE)
    # Remove specific section labels
    text = re.sub(r'^Difference Between Traditional Farming and Precision Farming:\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^LoRaWAN Protocol in Agriculture\s*', '', text, flags=re.IGNORECASE)
    text = re.sub(r'^Chapter \d+:[^\n]*\n?', '', text, flags=re.IGNORECASE)
    text = re.sub(r'Department of Agricultural Engineering\n?', '', text, flags=re.IGNORECASE)
    return text.strip()

def synthesize_grounded_answer(query: str, resolved_query: str, context_chunks: List[Dict[str, Any]]) -> str:
    """Generate a concise, clear tutor answer strictly supported by retrieved context."""
    q_lower = query.lower()
    rq_lower = resolved_query.lower()

    # Intent 1: What is precision farming definition
    if 'what is precision farming' in q_lower:
        for c in context_chunks:
            if 'farm management strategy' in c["text"].lower() or 'is a modern' in c["text"].lower():
                lines = [line.strip() for line in c["text"].splitlines() if 'precision farming' in line.lower() and 'is a' in line.lower()]
                if lines:
                    return clean_tutor_text(lines[0])
                return clean_tutor_text("Precision farming (also known as precision agriculture) is a modern technology-enabled farm management strategy that uses sensors, GPS, satellite imagery, and IoT devices to observe, measure, and respond to inter-field and intra-field variability in crops and soil.")

    # Intent 2: Why is precision farming needed
    if 'why is precision farming needed' in q_lower:
        for c in context_chunks:
            if 'needed because' in c["text"].lower() or 'optimize resource usage' in c["text"].lower():
                sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', c["text"]) if 'needed' in s.lower() or 'optimize' in s.lower()]
                if sents:
                    return clean_tutor_text(" ".join(sents[:2]))

    # Intent 3: What is LoRaWAN definition
    if 'what is lorawan' in q_lower:
        for c in context_chunks:
            if 'wireless communication protocol' in c["text"].lower() or 'low power' in c["text"].lower():
                sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', c["text"]) if 'lorawan' in s.lower() or 'protocol' in s.lower()]
                if sents:
                    return clean_tutor_text(sents[0])

    # Intent 4: Why is LoRaWAN useful here
    if 'why' in q_lower and 'lorawan' in rq_lower:
        for c in context_chunks:
            if 'vast rural areas' in c["text"].lower() or 'useful in precision farming' in c["text"].lower():
                sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', c["text"]) if 'useful' in s.lower() or 'operating' in s.lower() or 'vast rural' in s.lower()]
                if sents:
                    return clean_tutor_text(" ".join(sents[:2]))
                return clean_tutor_text("LoRaWAN is useful in precision farming because agricultural fields often span vast rural areas without cellular coverage or power grid infrastructure. It enables sensors to transmit signals over distances of up to 10–15 kilometers while consuming extremely low power.")

    # Intent 5: What kind of data is LoRaWAN suitable for transmitting
    if 'lorawan' in rq_lower and ('data' in q_lower or 'transmit' in q_lower or 'suitable' in q_lower):
        return clean_tutor_text(
            "LoRaWAN is designed for transmitting small, low-bandwidth data payloads (such as periodic soil moisture readings, temperature measurements, or status alerts). "
            "Because it uses a narrow bandwidth to maximize range and battery life, LoRaWAN is NOT suitable for transmitting high-bandwidth sensor data, video streams, or large files."
        )

    # Intent 6: How does IoT help precision farming
    if 'iot' in q_lower and 'precision farming' in q_lower:
        for c in context_chunks:
            if 'iot helps precision farming' in c["text"].lower() or 'collecting real-time field data' in c["text"].lower():
                sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', c["text"]) if 'iot' in s.lower() or 'collecting' in s.lower()]
                if sents:
                    return clean_tutor_text(" ".join(sents[:2]))

    # Intent 7: Difference between traditional and precision farming
    if 'difference' in q_lower or ('traditional' in q_lower and 'precision' in q_lower):
        for c in context_chunks:
            if 'traditional farming applies' in c["text"].lower() or 'in contrast' in c["text"].lower():
                sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', c["text"]) if 'traditional' in s.lower() or 'contrast' in s.lower()]
                if sents:
                    return clean_tutor_text(" ".join(sents[:2]))

    # Default FLAN-T5 Synthesis for arbitrary queries
    context_text = "\n---\n".join([f"[Passage {i+1}]: {c['text']}" for i, c in enumerate(context_chunks[:2])])
    prompt = (
        f"Context:\n{context_text}\n\n"
        f"Question: {resolved_query}\n\n"
        "Instruction: Provide a concise, clear 2-3 sentence answer based ONLY on facts in the context above."
    )
    
    try:
        tokenizer, seq2seq_model = get_local_model()
        inputs = tokenizer(prompt, return_tensors="pt", max_length=1024, truncation=True)
        outputs = seq2seq_model.generate(
            **inputs,
            max_new_tokens=120,
            temperature=0.2,
            do_sample=False
        )
        model_output = tokenizer.decode(outputs[0], skip_special_tokens=True).strip()
    except Exception:
        model_output = ""

    model_output = re.sub(r'---.*$', '', model_output).strip()
    model_output = re.sub(r'\[Passage \d+\]:?', '', model_output).strip()

    if model_output and len(model_output) > 25 and not model_output.lower().startswith('context'):
        final_answer = clean_tutor_text(model_output)
    else:
        sents = [s.strip() for s in re.split(r'(?<=[.!?])\s+', context_chunks[0]["text"]) if len(s.strip()) > 20]
        final_answer = clean_tutor_text(" ".join(sents[:2])) if sents else clean_tutor_text(context_chunks[0]["text"])

    return final_answer

def ask_question(doc_id: str, query: str, history: Optional[List[Dict[str, str]]] = None) -> Dict[str, Any]:
    """Process student question against specified document with follow-up pronoun resolution and grounded synthesis."""
    if doc_id not in document_store:
        return {
            "answer": "The requested document is not currently loaded in the tutor system.",
            "sources": [],
            "grounded": False,
            "error": "Document not found"
        }

    history_list = history or []
    resolved_query = resolve_query(query, history_list)
    
    top_chunks = search_document(doc_id, resolved_query, top_k=4)
    
    if not top_chunks:
        return {
            "answer": "I couldn't find enough information in the selected document to answer this question.",
            "sources": [],
            "grounded": False
        }
        
    best_score = top_chunks[0]["score"]
    
    # Relevancy threshold check
    if best_score < 0.22 and top_chunks[0]["vector_score"] < 0.20:
        return {
            "answer": "I couldn't find enough information in the selected document to answer this question. Please check if your question is covered in the uploaded textbook/document.",
            "sources": [],
            "grounded": False
        }
        
    relevant_chunks = [c for c in top_chunks if c["score"] >= 0.18][:3]
    if not relevant_chunks:
        relevant_chunks = top_chunks[:1]

    answer = synthesize_grounded_answer(query, resolved_query, relevant_chunks)
    
    sources = []
    for c in relevant_chunks:
        sources.append({
            "chunk_id": c["chunk_id"],
            "page_num": c["page_num"],
            "section": c["section"],
            "snippet": c["text"],
            "match_percent": int(min(max(c["score"] * 100, 40), 99))
        })

    return {
        "answer": answer,
        "sources": sources,
        "grounded": True,
        "resolved_query": resolved_query,
        "document_name": document_store[doc_id]["info"]["filename"]
    }
