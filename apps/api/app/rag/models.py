from pydantic import BaseModel


class ProcessResumeResponse(BaseModel):
    resume_id: str
    chunk_count: int
