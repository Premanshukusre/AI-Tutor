import io
import re
import uuid
from typing import List, Dict, Any, Tuple
import pypdf
import docx

def extract_pages_from_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Extract pages from a PDF file with page numbers."""
    pages = []
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    for idx, page in enumerate(reader.pages):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append({
                "page_num": idx + 1,
                "section": f"Page {idx + 1}",
                "text": text
            })
    return pages

def extract_sections_from_docx(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Extract paragraphs/sections from a DOCX file."""
    doc = docx.Document(io.BytesIO(file_bytes))
    sections = []
    current_section = "General Section"
    current_text = []
    
    page_approx = 1
    para_count = 0
    
    for para in doc.paragraphs:
        txt = para.text.strip()
        if not txt:
            continue
        
        # Check if heading
        if para.style and para.style.name.startswith("Heading"):
            if current_text:
                sections.append({
                    "page_num": page_approx,
                    "section": current_section,
                    "text": "\n".join(current_text)
                })
                current_text = []
            current_section = txt
        else:
            current_text.append(txt)
            para_count += 1
            if para_count >= 15:  # Approx page split
                page_approx += 1
                para_count = 0
                
    if current_text:
        sections.append({
            "page_num": page_approx,
            "section": current_section,
            "text": "\n".join(current_text)
        })
        
    return sections if sections else [{"page_num": 1, "section": "Document Content", "text": doc.text.strip() if hasattr(doc, 'text') else ""}]

def extract_pages_from_txt(file_bytes: bytes) -> List[Dict[str, Any]]:
    """Extract pages/blocks from a TXT file."""
    try:
        content = file_bytes.decode('utf-8')
    except UnicodeDecodeError:
        content = file_bytes.decode('latin-1', errors='replace')
        
    lines = content.splitlines()
    pages = []
    current_lines = []
    page_num = 1
    
    for line in lines:
        current_lines.append(line)
        if len(current_lines) >= 40:  # Roughly 1 page per 40 lines
            pages.append({
                "page_num": page_num,
                "section": f"Section {page_num}",
                "text": "\n".join(current_lines).strip()
            })
            current_lines = []
            page_num += 1
            
    if current_lines:
        pages.append({
            "page_num": page_num,
            "section": f"Section {page_num}",
            "text": "\n".join(current_lines).strip()
        })
        
    return pages

def split_text_into_chunks(text: str, max_chars: int = 500, overlap: int = 100) -> List[str]:
    """Split text into sentence-aware overlapping chunks."""
    if len(text) <= max_chars:
        return [text]
        
    sentences = re.split(r'(?<=[.!?])\s+', text)
    chunks = []
    current_chunk = []
    current_len = 0
    
    for s in sentences:
        s_len = len(s)
        if current_len + s_len > max_chars and current_chunk:
            chunk_str = " ".join(current_chunk).strip()
            if chunk_str:
                chunks.append(chunk_str)
            # Overlap: keep last sentence if possible
            if len(current_chunk) > 1 and len(current_chunk[-1]) < overlap:
                current_chunk = [current_chunk[-1], s]
                current_len = len(current_chunk[0]) + s_len + 1
            else:
                current_chunk = [s]
                current_len = s_len
        else:
            current_chunk.append(s)
            current_len += s_len + 1
            
    if current_chunk:
        chunk_str = " ".join(current_chunk).strip()
        if chunk_str:
            chunks.append(chunk_str)
            
    return chunks

def process_document(filename: str, file_bytes: bytes) -> Dict[str, Any]:
    """Process uploaded document, extract content, and produce structured chunks."""
    ext = filename.split('.')[-1].lower()
    
    if ext == 'pdf':
        parsed_pages = extract_pages_from_pdf(file_bytes)
    elif ext in ['docx', 'doc']:
        parsed_pages = extract_sections_from_docx(file_bytes)
    elif ext in ['txt', 'md']:
        parsed_pages = extract_pages_from_txt(file_bytes)
    else:
        raise ValueError(f"Unsupported file format: .{ext}")

    if not parsed_pages:
        raise ValueError("Could not extract any text from the document.")

    doc_id = str(uuid.uuid4())[:8]
    chunks = []
    chunk_index = 0
    full_text_blocks = []

    for item in parsed_pages:
        page_num = item["page_num"]
        section = item["section"]
        page_text = item["text"]
        
        if not page_text:
            continue
            
        full_text_blocks.append(page_text)
        sub_chunks = split_text_into_chunks(page_text, max_chars=450, overlap=80)
        
        for sc in sub_chunks:
            chunks.append({
                "chunk_id": f"{doc_id}_c{chunk_index}",
                "doc_id": doc_id,
                "page_num": page_num,
                "section": section,
                "text": sc
            })
            chunk_index += 1

    return {
        "doc_id": doc_id,
        "filename": filename,
        "total_pages": max([p["page_num"] for p in parsed_pages], default=1),
        "total_chunks": len(chunks),
        "full_text": "\n\n".join(full_text_blocks),
        "chunks": chunks
    }
