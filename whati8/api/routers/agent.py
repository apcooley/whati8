"""Agent router for conversational AI interface."""

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from whati8.api.deps import get_current_user, get_db
from whati8.api.limiter import limiter
from whati8.config import settings
from whati8.models import User
from whati8.schemas.agent import AgentChatRequest, AgentChatResponse
from whati8.services.agent_service import AgentService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/chat", response_model=AgentChatResponse)
@limiter.limit(f"{settings.rate_limit_ai_per_minute}/minute")
async def chat(
    request: Request,
    chat_request: AgentChatRequest,
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Send message to conversational agent.

    The agent can help with:
    - Logging foods naturally (e.g., "I had 2 eggs for breakfast")
    - Searching for foods in the database
    - Viewing eating history
    - Getting nutrition summaries
    - Understanding dietary intake

    Requires authentication. Rate limited to 5 requests per minute.
    """
    logger.info(
        f"Agent chat request from user {current_user.id}, "
        f"session {chat_request.session_id}, message: {chat_request.message[:50]}..."
    )

    try:
        response_data = await AgentService.process_message(
            db=db,
            user=current_user,
            message=chat_request.message,
            session_id=chat_request.session_id,
            user_timezone=chat_request.user_timezone,
            conversation_history=chat_request.conversation_history,
        )

        return AgentChatResponse(
            message=response_data["message_content"],
            session_id=chat_request.session_id,
            requires_form=response_data.get("requires_form", False),
            form_data=response_data.get("form_data"),
            tool_results=response_data.get("tool_results"),
        )

    except ValueError as e:
        logger.warning(f"Validation error in agent chat: {e}")
        raise
    except Exception as e:
        logger.error(f"Error processing agent chat: {e}")
        raise
