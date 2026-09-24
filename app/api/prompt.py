# Prompt API 路由。
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from app.core.database import get_db
from app.schemas.prompt import PromptCreate, PromptUpdate, PromptOut
from app.services.prompt_service import PromptService

router = APIRouter(prefix="/prompts", tags=["Prompts"])
service = PromptService()

@router.post("", response_model=PromptOut)
def create_prompt(data: PromptCreate, db: Session = Depends(get_db)):
    return service.create(db, data)

@router.get("", response_model=list[PromptOut])
def list_prompts(db: Session = Depends(get_db)):
    return service.list(db)

@router.put("/{prompt_id}", response_model=PromptOut)
def update_prompt(prompt_id: int, data: PromptUpdate, db: Session = Depends(get_db)):
    prompt = service.update(db, prompt_id, data)
    if not prompt:
        raise HTTPException(status_code=404, detail="Prompt not found")
    return prompt

@router.delete("/{prompt_id}")
def delete_prompt(prompt_id: int, db: Session = Depends(get_db)):
    if not service.delete(db, prompt_id):
        raise HTTPException(status_code=404, detail="Prompt not found")
    return {"success": True}
