"""Question management system for interactive workflows.

Allows orchestrator to ask users questions and wait for answers via WebSocket.
"""

import asyncio
import time
from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Any
from pydantic import BaseModel, Field

from events import get_event_bus, WorkflowEvent, EventType


class QuestionType(str, Enum):
    """Types of questions that can be asked."""
    MULTIPLE_CHOICE = "multiple_choice"
    TEXT = "text"
    YES_NO = "yes_no"
    NUMBER = "number"


class Question(BaseModel):
    """Question to ask user during workflow."""
    question_id: str
    workflow_id: str
    stage: str
    question: str
    question_type: QuestionType
    options: Optional[List[str]] = None
    default: Optional[Any] = None
    timeout: int = 300  # 5 minutes default
    required: bool = True
    context: Optional[str] = None
    asked_at: datetime = Field(default_factory=datetime.utcnow)


class Answer(BaseModel):
    """Answer to a question."""
    question_id: str
    workflow_id: str
    answer: Any
    answered_at: datetime = Field(default_factory=datetime.utcnow)


class QuestionManager:
    """Manages questions and answers for interactive workflows."""
    
    def __init__(self):
        """Initialize question manager."""
        # Pending questions: question_id -> Question
        self._pending_questions: Dict[str, Question] = {}
        
        # Answers: question_id -> Answer
        self._answers: Dict[str, Answer] = {}
        
        # Events for waiting: question_id -> asyncio.Event
        self._answer_events: Dict[str, asyncio.Event] = {}
        
        # Question counter for unique IDs
        self._question_counter = 0
    
    async def ask_question(
        self,
        workflow_id: str,
        stage: str,
        question: str,
        question_type: QuestionType = QuestionType.TEXT,
        options: Optional[List[str]] = None,
        default: Any = None,
        timeout: int = 300,
        required: bool = True,
        context: Optional[str] = None
    ) -> Any:
        """Ask a question and wait for answer.
        
        Args:
            workflow_id: Workflow ID
            stage: Current stage
            question: Question text
            question_type: Type of question
            options: Options for multiple choice
            default: Default answer if timeout
            timeout: Timeout in seconds
            required: Whether answer is required
            context: Additional context for the question
            
        Returns:
            Answer value or default if timeout
            
        Raises:
            TimeoutError: If required question times out without answer
        """
        # Generate unique question ID
        self._question_counter += 1
        question_id = f"q_{workflow_id}_{stage}_{self._question_counter}_{int(time.time())}"
        
        # Create question
        q = Question(
            question_id=question_id,
            workflow_id=workflow_id,
            stage=stage,
            question=question,
            question_type=question_type,
            options=options,
            default=default,
            timeout=timeout,
            required=required,
            context=context
        )
        
        # Store question
        self._pending_questions[question_id] = q
        self._answer_events[question_id] = asyncio.Event()
        
        # Emit question event (will be sent to WebSocket clients)
        await get_event_bus().emit(WorkflowEvent(
            event_type=EventType.QUESTION_ASKED,
            workflow_id=workflow_id,
            stage=stage,
            data=q.model_dump(),
            message=f"Question: {question}"
        ))
        
        # Wait for answer with timeout
        try:
            await asyncio.wait_for(
                self._answer_events[question_id].wait(),
                timeout=timeout
            )
            
            # Get answer
            answer = self._answers.get(question_id)
            if answer:
                return answer.answer
            elif default is not None:
                return default
            elif required:
                raise TimeoutError(f"No answer received for required question: {question}")
            else:
                return None
                
        except asyncio.TimeoutError:
            # Timeout occurred
            if default is not None:
                # Use default
                await get_event_bus().emit(WorkflowEvent(
                    event_type=EventType.ANSWER_RECEIVED,
                    workflow_id=workflow_id,
                    stage=stage,
                    data={"question_id": question_id, "answer": default, "timeout": True},
                    message=f"Question timeout, using default: {default}"
                ))
                return default
            elif required:
                raise TimeoutError(f"Question timeout: {question}")
            else:
                return None
        finally:
            # Cleanup
            self._pending_questions.pop(question_id, None)
            self._answer_events.pop(question_id, None)
    
    def answer_question(self, question_id: str, answer: Any) -> bool:
        """Submit answer to a pending question.
        
        Args:
            question_id: Question ID
            answer: Answer value
            
        Returns:
            True if answer accepted, False if question not found
        """
        if question_id not in self._pending_questions:
            return False
        
        question = self._pending_questions[question_id]
        
        # Validate answer for multiple choice
        if question.question_type == QuestionType.MULTIPLE_CHOICE:
            if question.options and answer not in question.options:
                # Try to find case-insensitive match
                answer_lower = str(answer).lower()
                for option in question.options:
                    if option.lower() == answer_lower:
                        answer = option
                        break
        
        # Store answer
        self._answers[question_id] = Answer(
            question_id=question_id,
            workflow_id=question.workflow_id,
            answer=answer
        )
        
        # Signal that answer is ready
        if question_id in self._answer_events:
            self._answer_events[question_id].set()
        
        # Emit answer received event
        asyncio.create_task(get_event_bus().emit(WorkflowEvent(
            event_type=EventType.ANSWER_RECEIVED,
            workflow_id=question.workflow_id,
            stage=question.stage,
            data={"question_id": question_id, "answer": answer},
            message=f"Answer received: {answer}"
        )))
        
        return True
    
    def get_pending_questions(self, workflow_id: str) -> List[Question]:
        """Get all pending questions for a workflow.
        
        Args:
            workflow_id: Workflow ID
            
        Returns:
            List of pending questions
        """
        return [
            q for q in self._pending_questions.values()
            if q.workflow_id == workflow_id
        ]
    
    def get_question(self, question_id: str) -> Optional[Question]:
        """Get a specific question.
        
        Args:
            question_id: Question ID
            
        Returns:
            Question or None if not found
        """
        return self._pending_questions.get(question_id)
    
    def cancel_question(self, question_id: str) -> bool:
        """Cancel a pending question.
        
        Args:
            question_id: Question ID
            
        Returns:
            True if cancelled, False if not found
        """
        if question_id not in self._pending_questions:
            return False
        
        question = self._pending_questions[question_id]
        
        # Use default if available
        if question.default is not None:
            self.answer_question(question_id, question.default)
        else:
            # Just signal the event to unblock
            if question_id in self._answer_events:
                self._answer_events[question_id].set()
        
        return True
    
    def get_stats(self) -> Dict[str, Any]:
        """Get question manager statistics.
        
        Returns:
            Statistics dictionary
        """
        return {
            "pending_questions": len(self._pending_questions),
            "total_answers": len(self._answers),
        }


# Global singleton
_question_manager: Optional[QuestionManager] = None


def get_question_manager() -> QuestionManager:
    """Get global question manager singleton.
    
    Returns:
        QuestionManager instance
    """
    global _question_manager
    if _question_manager is None:
        _question_manager = QuestionManager()
    return _question_manager


def reset_question_manager() -> None:
    """Reset global question manager (for testing)."""
    global _question_manager
    _question_manager = None

# Made with Bob
