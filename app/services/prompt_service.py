# Prompt 业务逻辑，包括新增、查询、修改、删除。
from sqlalchemy.orm import Session
from app.models.prompt import Prompt
from app.schemas.prompt import PromptCreate, PromptUpdate

class PromptService:
    def create(self, db: Session, data: PromptCreate) -> Prompt:
        prompt = Prompt(**data.model_dump())
        db.add(prompt); db.commit(); db.refresh(prompt)
        return prompt

    def list(self, db: Session):
        return db.query(Prompt).order_by(Prompt.id.desc()).all()

    def get(self, db: Session, prompt_id: int) -> Prompt | None:
        return db.query(Prompt).filter(Prompt.id == prompt_id).first()

    def update(self, db: Session, prompt_id: int, data: PromptUpdate) -> Prompt | None:
        prompt = self.get(db, prompt_id)
        if not prompt:
            return None
        for key, value in data.model_dump(exclude_unset=True).items():
            setattr(prompt, key, value)
        db.commit(); db.refresh(prompt)
        return prompt

    def delete(self, db: Session, prompt_id: int) -> bool:
        prompt = self.get(db, prompt_id)
        if not prompt:
            return False
        db.delete(prompt); db.commit()
        return True