import os
from fastapi import FastAPI, UploadFile, File, HTTPException, Form
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from typing import Optional, List, Dict

from document_processor import process_document
from rag_engine import index_document, get_document_list, delete_document, ask_question

app = FastAPI(title="AI Tutor - Textbook & Document Q&A", version="1.0.0")

class QARequest(BaseModel):
    doc_id: str
    question: str
    history: Optional[List[Dict[str, str]]] = []

# Ensure static directory exists
static_dir = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(static_dir, exist_ok=True)

@app.post("/api/upload")
async def upload_document(file: UploadFile = File(...)):
    """Upload a document (PDF, DOCX, TXT), process text, and index for QA."""
    if not file.filename:
        raise HTTPException(status_code=400, detail="No file filename provided.")
        
    ext = file.filename.split('.')[-1].lower()
    if ext not in ['pdf', 'docx', 'doc', 'txt', 'md']:
        raise HTTPException(status_code=400, detail=f"Unsupported file type .{ext}. Supported formats: PDF, DOCX, TXT.")

    try:
        content = await file.read()
        doc_info = process_document(file.filename, content)
        index_document(doc_info)
        return {
            "status": "success",
            "message": f"Successfully processed and indexed '{file.filename}'",
            "document": {
                "doc_id": doc_info["doc_id"],
                "filename": doc_info["filename"],
                "total_pages": doc_info["total_pages"],
                "total_chunks": doc_info["total_chunks"]
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error processing document: {str(e)}")

@app.get("/api/documents")
async def list_documents():
    """Retrieve list of indexed documents."""
    return {"documents": get_document_list()}

@app.delete("/api/documents/{doc_id}")
async def remove_document(doc_id: str):
    """Delete a document from isolated store."""
    success = delete_document(doc_id)
    if not success:
        raise HTTPException(status_code=404, detail="Document not found.")
    return {"status": "success", "message": "Document removed successfully."}

@app.post("/api/qa")
async def process_qa(request: QARequest):
    """Answer student question grounded in the selected document with history context."""
    if not request.doc_id or not request.question.strip():
        raise HTTPException(status_code=400, detail="Missing doc_id or question.")
        
    result = ask_question(request.doc_id, request.question.strip(), history=request.history or [])
    return result

# Serve static frontend assets
app.mount("/static", StaticFiles(directory=static_dir), name="static")

@app.get("/")
async def read_root():
    """Serve index.html at root route."""
    index_path = os.path.join(static_dir, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path)
    return JSONResponse({"status": "AI Tutor API is running. Frontend static/index.html loading..."})
