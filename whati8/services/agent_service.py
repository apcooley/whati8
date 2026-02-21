"""Agent service for conversational AI interface.

Handles conversation management, tool calling, and integration with Claude API.
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Any

from anthropic import Anthropic
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from whati8.config import settings
from whati8.constants import (
    AGENT_CONVERSATION_EXPIRATION_MINUTES,
    AGENT_MAX_HISTORY_LENGTH,
    AI_INPUT_MAX_LENGTH,
)
from whati8.models import Food, FoodLog, User
from whati8.services.food_resolver import FoodResolverService

logger = logging.getLogger(__name__)


# Tool definitions for Claude API
AGENT_TOOLS = [
    {
        "name": "log_food",
        "description": "Create a food log entry for the user",
        "input_schema": {
            "type": "object",
            "properties": {
                "food_id": {"type": "integer", "description": "Database ID of the food"},
                "quantity": {"type": "number", "description": "Amount consumed in grams"},
                "meal_id": {
                    "type": "integer",
                    "description": "Meal ID (1=Breakfast, 2=Lunch, 3=Dinner, 4=Snack)",
                    "enum": [1, 2, 3, 4],
                },
                "logged_at": {
                    "type": "string",
                    "format": "date-time",
                    "description": "When the food was consumed (ISO format)",
                },
                "notes": {"type": "string", "description": "Optional notes about the food"},
            },
            "required": ["food_id", "quantity", "logged_at"],
        },
    },
    {
        "name": "search_foods",
        "description": "Search for foods in the database by name",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "minLength": 2,
                    "description": "Search term for food name",
                },
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "minimum": 1,
                    "maximum": 50,
                    "description": "Maximum number of results",
                },
            },
            "required": ["query"],
        },
    },
    {
        "name": "resolve_foods_nl",
        "description": "Parse natural language food description to extract foods and quantities",
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": "Natural language food description (e.g., '2 eggs and toast')",
                },
                "meal_hint": {
                    "type": "string",
                    "description": "Optional hint about meal type",
                    "enum": ["breakfast", "lunch", "dinner", "snack"],
                },
            },
            "required": ["text"],
        },
    },
    {
        "name": "list_logs",
        "description": "List recent food log entries",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Date to filter logs (YYYY-MM-DD)",
                },
                "meal_id": {
                    "type": "integer",
                    "description": "Filter by meal type",
                    "enum": [1, 2, 3, 4],
                },
                "limit": {
                    "type": "integer",
                    "default": 20,
                    "minimum": 1,
                    "maximum": 100,
                },
            },
        },
    },
    {
        "name": "get_daily_summary",
        "description": "Get nutrition summary for a specific date",
        "input_schema": {
            "type": "object",
            "properties": {
                "date": {
                    "type": "string",
                    "format": "date",
                    "description": "Date for summary (YYYY-MM-DD)",
                }
            },
            "required": ["date"],
        },
    },
    {
        "name": "delete_log",
        "description": "Delete a food log entry",
        "input_schema": {
            "type": "object",
            "properties": {
                "log_id": {
                    "type": "integer",
                    "description": "ID of the food log to delete",
                }
            },
            "required": ["log_id"],
        },
    },
    {
        "name": "show_confirmation_form",
        "description": "Request user confirmation through a form",
        "input_schema": {
            "type": "object",
            "properties": {
                "form_type": {
                    "type": "string",
                    "enum": ["food_selection", "log_confirmation", "multi_food_confirmation"],
                    "description": "Type of form to display",
                },
                "data": {
                    "type": "object",
                    "description": "Form data to display",
                },
            },
            "required": ["form_type", "data"],
        },
    },
]


class ConversationManager:
    """Manages in-memory conversation storage with expiration."""

    def __init__(self):
        self._conversations: dict[str, dict[str, Any]] = {}

    def get_conversation(self, session_id: str) -> list[dict]:
        """Get conversation history for a session."""
        if session_id not in self._conversations:
            return []

        conversation = self._conversations[session_id]

        # Check expiration
        if datetime.utcnow() > conversation["expires_at"]:
            del self._conversations[session_id]
            return []

        return conversation["messages"]

    def add_message(
        self, session_id: str, message: dict, timezone: str = "UTC"
    ) -> None:
        """Add a message to conversation history."""
        if session_id not in self._conversations:
            self._conversations[session_id] = {
                "messages": [],
                "timezone": timezone,
                "expires_at": datetime.utcnow()
                + timedelta(minutes=AGENT_CONVERSATION_EXPIRATION_MINUTES),
            }

        conversation = self._conversations[session_id]
        conversation["messages"].append(message)

        # Update timezone if it changed
        conversation["timezone"] = timezone

        # Keep only last N messages
        if len(conversation["messages"]) > AGENT_MAX_HISTORY_LENGTH:
            conversation["messages"] = conversation["messages"][
                -AGENT_MAX_HISTORY_LENGTH:
            ]

        # Update expiration
        conversation["expires_at"] = datetime.utcnow() + timedelta(
            minutes=AGENT_CONVERSATION_EXPIRATION_MINUTES
        )

    def get_timezone(self, session_id: str) -> str:
        """Get timezone for a session."""
        if session_id in self._conversations:
            return self._conversations[session_id].get("timezone", "UTC")
        return "UTC"

    def clear_conversation(self, session_id: str) -> None:
        """Clear conversation history for a session."""
        if session_id in self._conversations:
            del self._conversations[session_id]


# Global conversation manager
conversation_manager = ConversationManager()


class AgentService:
    """Service for conversational AI agent."""

    @staticmethod
    def _deduplicate_foods(foods: list[dict]) -> list[dict]:
        """Deduplicate food list, preferring human-readable portions over 100g.

        Args:
            foods: List of food dicts with 'name' and 'serving_size' keys

        Returns:
            Deduplicated list of foods
        """
        seen_names = {}
        for food in foods:
            name = food.get("name")
            serving_size = food.get("serving_size", 100.0)

            if name not in seen_names:
                # First time seeing this name - add it
                seen_names[name] = food
            else:
                # Duplicate found - prefer non-100g portion (more likely to be "1 fruit" etc)
                existing_serving = seen_names[name].get("serving_size", 100.0)
                if existing_serving == 100.0 and serving_size != 100.0:
                    # Replace 100g with human-readable portion
                    seen_names[name] = food
                    logger.info(f"[Agent] Replaced 100g serving with {serving_size}g for '{name}'")

        return list(seen_names.values())

    @staticmethod
    def _build_system_prompt(user_timezone: str = "UTC", current_datetime: datetime | None = None) -> str:
        """Build system prompt for agent.

        Args:
            user_timezone: User's IANA timezone (e.g., 'America/Los_Angeles')
            current_datetime: Current datetime in UTC (defaults to now)
        """
        from zoneinfo import ZoneInfo

        if current_datetime is None:
            current_datetime = datetime.utcnow()

        # Convert to user's timezone for display
        try:
            user_tz = ZoneInfo(user_timezone)
            user_local_time = current_datetime.replace(tzinfo=ZoneInfo("UTC")).astimezone(user_tz)
            current_date_str = user_local_time.strftime("%Y-%m-%d")
            current_time_str = user_local_time.strftime("%I:%M %p %Z")
        except Exception:
            # Fallback to UTC if timezone conversion fails
            current_date_str = current_datetime.strftime("%Y-%m-%d")
            current_time_str = current_datetime.strftime("%H:%M:%S UTC")

        return f"""You are a helpful nutrition assistant for the whati8 food tracking app.

**Current Date/Time:** {current_date_str} {current_time_str}
**User's Timezone:** {user_timezone}

Your role is to help users:
- Log foods they've eaten
- Search for foods in the database
- View their eating history
- Get nutrition summaries
- Understand their dietary intake
- Delete food log entries

Guidelines:
- Be conversational and friendly
- Parse natural language food descriptions accurately
- **IMPORTANT: When using tools, do NOT include any text in your initial response. Use tools silently.**
- After tool execution, you will see the results and can then formulate a comprehensive response
- **CRITICAL: You MUST always provide a text response after seeing tool results, even if there were errors**
- **CRITICAL: After seeing tool results, you may ONLY call show_confirmation_form if needed for user selection. Do NOT call search_foods, resolve_foods_nl, or any other tools again. All the data you need is in the tool results.**
- Provide helpful nutrition information when appropriate
- Keep responses concise and mobile-friendly

Meal types:
- 1 = Breakfast
- 2 = Lunch
- 3 = Dinner
- 4 = Snack

When a user asks to log food:
1. Use resolve_foods_nl tool to parse their description (WITHOUT any text commentary)
2. Wait for the tool results
3. Review the parsed foods and matched items
4. **If the tool returns an error**: Explain the error in friendly terms and ask the user to try again with different wording
5. **If exactly ONE food matched with high confidence**:
   - Present that food with details
   - Ask for quantity confirmation if not specified
   - DO NOT log yet - wait for user confirmation
6. **If MULTIPLE foods matched (2 or more)**:
   - **CRITICAL**: You MUST use show_confirmation_form tool immediately
   - **DO NOT** call search_foods again - you already have the matches from resolve_foods_nl
   - **DO NOT** present options as text - use the form tool
   - Format: {{"form_type": "food_selection", "data": {{"foods": [{{"id": 707, "name": "Kiwifruit, green, raw", "serving_size": 100, "unit": "g", "calories": 58}}]}}}}
   - Include ALL matched foods from the resolve_foods_nl result
   - The user will see a modal and click their choice

When user confirms food to log:
1. If you used show_confirmation_form, the user's response will contain the selected food_id
2. Use log_food tool with the EXACT food_id from their selection
3. After logging, CHECK the tool result for success
4. **CRITICAL**: Only claim success if tool result shows {{"success": true}}
5. State the EXACT food name that was logged, not what you intended
6. Include the log_id from the tool result if available

When searching for foods:
1. Use search_foods tool (WITHOUT any text commentary)
2. Wait for results
3. **If the tool returns an error**: Explain what went wrong
4. **If successful**: Present the matching foods in a clear format

When user asks to delete/remove a food log:
1. First use list_logs to show their recent entries if they haven't specified which one
2. Once you know the log_id (from list_logs or they mentioned it), use delete_log tool
3. Wait for the tool result
4. **If successful**: Confirm which food was deleted
5. **If failed**: Explain what went wrong (e.g., "That entry wasn't found" or "That entry belongs to another day")

**Date/Time Handling:**
- When logging food without a specific time, use the CURRENT date/time shown above
- When user says "I had X", assume they mean recently (within the last hour)
- When user specifies a time like "for breakfast" or "this morning", estimate the appropriate time in their timezone
- Always include logged_at in ISO format when calling log_food
- When displaying times to users, show them in a friendly format like "Feb 8 at 10:30 AM"

**Error Handling:**
- If you see `{{"error": "..."}}` in tool results, YOU MUST respond with a helpful error message
- Never return empty responses
- Always acknowledge what you tried to do and what went wrong
- Suggest alternatives or ask for clarification

**Verification Rules:**
- NEVER claim you logged food unless the log_food tool returned success
- NEVER guess which food was logged - read it from the tool result
- If tool result says food_id=123, look up what food 123 actually is before confirming

Your responses should be comprehensive summaries AFTER seeing tool results, not play-by-play commentary of what you're about to do.

Example BAD response: "I'll help you log that! Let me parse it for you..."
Example GOOD response (success): "I found 'Kiwi fruit, raw' in the database (61 calories per 100g). Would you like to log this for your snack?"
Example GOOD response (error): "I tried to parse 'xyz123' but couldn't identify it as a food. Could you describe what you ate in different words? For example: 'apple', 'chicken breast', or 'brown rice'."
"""

    @staticmethod
    async def process_message(
        db: AsyncSession,
        user: User,
        message: str,
        session_id: str,
        user_timezone: str = "UTC",
        conversation_history: list[dict] | None = None,
    ) -> dict:
        """Process a user message and return agent response.

        Args:
            db: Database session
            user: Current user
            message: User's message
            session_id: Conversation session ID
            user_timezone: User's IANA timezone
            conversation_history: Optional conversation history from client

        Returns:
            Dict with agent response and metadata
        """
        # Sanitize input
        message = message.strip()
        if not message:
            raise ValueError("Message cannot be empty")
        if len(message) > AI_INPUT_MAX_LENGTH:
            raise ValueError(f"Message too long (max {AI_INPUT_MAX_LENGTH} characters)")

        # Prevent prompt injection
        if any(
            keyword in message.lower()
            for keyword in ["ignore previous", "disregard", "system:", "assistant:"]
        ):
            logger.warning(f"Potential prompt injection detected: {message[:100]}")
            message = message.replace("ignore previous", "").replace(
                "disregard", ""
            )

        # Get conversation history
        history = conversation_manager.get_conversation(session_id)

        # Add user message to history
        user_message = {"role": "user", "content": message}
        conversation_manager.add_message(session_id, user_message, timezone=user_timezone)

        # Build messages for Claude
        messages = history + [user_message]

        # Get current datetime
        current_datetime = datetime.utcnow()

        try:
            logger.info(f"[Agent] Processing message for user {user.id}, session {session_id}, timezone {user_timezone}")
            logger.debug(f"[Agent] Message history length: {len(messages)}")

            # Initial call to Claude
            logger.info("[Agent] Calling Claude API (initial request)...")
            claude_response = await asyncio.to_thread(
                AgentService._call_claude_sync,
                messages,
                user_timezone,
                current_datetime,
            )
            logger.info(f"[Agent] Claude responded with {len(claude_response.content)} content blocks")

            # Check if Claude wants to use tools
            tool_uses = [block for block in claude_response.content if block.type == "tool_use"]
            text_blocks = [block for block in claude_response.content if block.type == "text"]

            logger.info(f"[Agent] Found {len(tool_uses)} tool uses, {len(text_blocks)} text blocks")
            if text_blocks:
                logger.debug(f"[Agent] Initial text: {text_blocks[0].text[:100]}...")

            if tool_uses:
                logger.info(f"[Agent] Executing {len(tool_uses)} tools...")
                # Execute all tools
                tool_results_for_claude = []
                tool_results_for_response = []
                requires_form = False
                form_data = None

                for idx, tool_use in enumerate(tool_uses):
                    logger.info(f"[Agent] Executing tool {idx+1}/{len(tool_uses)}: {tool_use.name}")
                    logger.debug(f"[Agent] Tool input: {tool_use.input}")

                    # Execute tool asynchronously
                    tool_result = await AgentService._execute_tool(
                        db=db,
                        user_id=user.id,
                        tool_name=tool_use.name,
                        tool_input=tool_use.input,
                    )

                    logger.info(f"[Agent] Tool {tool_use.name} completed")
                    logger.debug(f"[Agent] Tool result: {str(tool_result)[:200]}...")

                    # Debug: log full structure for resolve_foods_nl
                    if tool_use.name == "resolve_foods_nl":
                        logger.info(f"[Agent] resolve_foods_nl result structure: {tool_result}")

                    # Store for response
                    tool_results_for_response.append(
                        {"tool": tool_use.name, "input": tool_use.input, "result": tool_result}
                    )

                    # Check if form is required
                    if tool_use.name == "show_confirmation_form":
                        requires_form = True
                        form_data = tool_use.input
                        logger.info("[Agent] Confirmation form required")

                    # Auto-trigger multi-food confirmation form for resolve_foods_nl
                    if tool_use.name == "resolve_foods_nl" and tool_result.get("success"):
                        # Always trigger the multi-food confirmation UI
                        multi_food_data = tool_result.get("multi_food_confirmation", {})
                        if multi_food_data:
                            requires_form = True
                            form_data = {
                                "form_type": "multi_food_confirmation",
                                "data": multi_food_data
                            }
                            num_items = len(multi_food_data.get("food_items", []))
                            logger.info(f"[Agent] Auto-triggered multi-food confirmation form with {num_items} food item(s)")

                    # Format for Claude API
                    tool_results_for_claude.append({
                        "type": "tool_result",
                        "tool_use_id": tool_use.id,
                        "content": str(tool_result),
                    })

                logger.info("[Agent] All tools executed, sending results back to Claude...")

                # Add assistant's tool use to messages
                messages.append({
                    "role": "assistant",
                    "content": claude_response.content,
                })

                # Add tool results to messages
                messages.append({
                    "role": "user",
                    "content": tool_results_for_claude,
                })

                logger.info(f"[Agent] Message history now has {len(messages)} messages")

                # Get Claude's final response after seeing tool results
                logger.info("[Agent] Calling Claude API (final response with tool results)...")
                final_response = await asyncio.to_thread(
                    AgentService._call_claude_sync,
                    messages,
                    user_timezone,
                    current_datetime,
                )

                logger.info(f"[Agent] Claude final response has {len(final_response.content)} blocks")

                # Check if Claude wants to use more tools in final response (like show_confirmation_form)
                final_tool_uses = [block for block in final_response.content if block.type == "tool_use"]

                if final_tool_uses:
                    logger.info(f"[Agent] Claude returned {len(final_tool_uses)} tool calls in final response")
                    # Handle show_confirmation_form in final response
                    for tool_use in final_tool_uses:
                        logger.info(f"[Agent] Tool in final response: {tool_use.name}")
                        if tool_use.name == "show_confirmation_form":
                            # Don't let Claude override auto-triggered multi_food_confirmation form
                            if requires_form and form_data and form_data.get("form_type") == "multi_food_confirmation":
                                logger.info("[Agent] Ignoring Claude's show_confirmation_form - already have auto-triggered multi_food_confirmation")
                                continue
                            
                            requires_form = True
                            form_data = tool_use.input

                            # Apply deduplication to food selection forms from Claude
                            if form_data.get("form_type") == "food_selection":
                                foods = form_data.get("data", {}).get("foods", [])
                                if foods:
                                    original_count = len(foods)
                                    deduplicated_foods = AgentService._deduplicate_foods(foods)
                                    form_data["data"]["foods"] = deduplicated_foods
                                    logger.info(f"[Agent] Deduplicated Claude's food form: {original_count} → {len(deduplicated_foods)} options")

                            logger.info(f"[Agent] Form request in final response: {tool_use.input.get('form_type')}")
                        else:
                            logger.warning(f"[Agent] Claude tried to call non-form tool '{tool_use.name}' in final response - this will be ignored")

                # Extract final message content
                message_content = ""
                for block in final_response.content:
                    if block.type == "text":
                        message_content += block.text

                logger.info(f"[Agent] Final message length: {len(message_content)} chars")

                # Show "Searching database..." when showing multi-food confirmation form
                # The form itself is the UI - no need for explanatory text beyond search indicator
                if requires_form and form_data and form_data.get("form_type") == "multi_food_confirmation":
                    logger.info("[Agent] Showing search indicator for multi-food form")
                    message_content = "Searching database..."

                # Fallback if Claude returns empty response (shouldn't happen but be safe)
                if not message_content.strip():
                    logger.warning("[Agent] Claude returned empty response, checking context")

                    # If there's a form request, provide helpful message
                    if requires_form and form_data:
                        form_type = form_data.get("form_type", "unknown")
                        if form_type == "food_selection":
                            num_foods = len(form_data.get("data", {}).get("foods", []))
                            message_content = f"I found {num_foods} matching foods. Please select one:"
                            logger.info("[Agent] Generated form intro message")
                        else:
                            message_content = "Please review and confirm:"
                    # Check if any tools had errors
                    elif any("error" in tr.get("result", {}) for tr in tool_results_for_response):
                        errors = [tr for tr in tool_results_for_response if "error" in tr.get("result", {})]
                        error_details = errors[0]["result"]["error"]
                        message_content = f"I encountered an issue: {error_details}. Could you try rephrasing?"
                        logger.warning("[Agent] Generated fallback error message")
                    else:
                        message_content = "I processed your request but didn't generate a response. Could you try again?"
                        logger.error("[Agent] No tool errors or forms found but response was empty")

                logger.debug(f"[Agent] Final message: {message_content[:200]}...")

                response_data = {
                    "message_content": message_content,
                    "tool_results": tool_results_for_response,
                    "requires_form": requires_form,
                    "form_data": form_data,
                }

            else:
                # No tools used, just return the text response
                logger.info("[Agent] No tools requested, returning direct response")
                message_content = ""
                for block in claude_response.content:
                    if block.type == "text":
                        message_content += block.text

                logger.info(f"[Agent] Direct response length: {len(message_content)} chars")
                logger.debug(f"[Agent] Direct response: {message_content[:200]}...")

                response_data = {
                    "message_content": message_content,
                    "tool_results": None,
                    "requires_form": False,
                    "form_data": None,
                }

            # Add assistant response to history
            logger.info("[Agent] Adding response to conversation history")
            assistant_message = {
                "role": "assistant",
                "content": response_data["message_content"],
            }
            conversation_manager.add_message(session_id, assistant_message)

            logger.info(f"[Agent] Request complete. Message: {len(response_data['message_content'])} chars, "
                       f"Tools: {len(response_data['tool_results']) if response_data['tool_results'] else 0}, "
                       f"Form required: {response_data['requires_form']}")

            return response_data

        except Exception as e:
            logger.error(f"[Agent] Error processing message: {e}", exc_info=True)
            raise

    @staticmethod
    def _call_claude_sync(
        messages: list[dict],
        user_timezone: str = "UTC",
        current_datetime: datetime | None = None,
    ):
        """Call Claude API synchronously (runs in thread pool).

        Args:
            messages: Conversation messages
            user_timezone: User's IANA timezone
            current_datetime: Current datetime in UTC

        Returns:
            Claude API response object
        """
        client = Anthropic(api_key=settings.anthropic_api_key)

        response = client.messages.create(
            model=settings.anthropic_model,
            max_tokens=2048,
            system=AgentService._build_system_prompt(
                user_timezone=user_timezone, current_datetime=current_datetime
            ),
            messages=messages,
            tools=AGENT_TOOLS,
        )

        return response

    @staticmethod
    async def _execute_tool(
        db: AsyncSession, user_id: int, tool_name: str, tool_input: dict
    ) -> dict:
        """Execute a tool and return results.

        Args:
            db: Database session
            user_id: User ID
            tool_name: Name of tool to execute
            tool_input: Tool input parameters

        Returns:
            Tool execution result
        """
        try:
            if tool_name == "log_food":
                return await AgentService._tool_log_food(db, user_id, tool_input)
            elif tool_name == "search_foods":
                return await AgentService._tool_search_foods(db, tool_input)
            elif tool_name == "resolve_foods_nl":
                return await AgentService._tool_resolve_foods_nl(db, tool_input)
            elif tool_name == "list_logs":
                return await AgentService._tool_list_logs(db, user_id, tool_input)
            elif tool_name == "delete_log":
                return await AgentService._tool_delete_log(db, user_id, tool_input)
            elif tool_name == "get_daily_summary":
                return await AgentService._tool_get_daily_summary(
                    db, user_id, tool_input
                )
            elif tool_name == "show_confirmation_form":
                return {"success": True, "message": "Form displayed"}
            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as e:
            logger.error(f"Error executing tool {tool_name}: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _tool_log_food(
        db: AsyncSession, user_id: int, params: dict
    ) -> dict:
        """Create a food log entry."""
        try:
            # Parse logged_at timestamp and convert to naive UTC
            # Database uses TIMESTAMP WITHOUT TIME ZONE
            logged_at_str = params["logged_at"].replace("Z", "+00:00")
            logged_at = datetime.fromisoformat(logged_at_str)

            # Convert to naive datetime (remove timezone info)
            if logged_at.tzinfo is not None:
                logged_at = logged_at.replace(tzinfo=None)

            # Create food log
            food_log = FoodLog(
                user_id=user_id,
                food_id=params["food_id"],
                quantity=params["quantity"],
                meal_id=params.get("meal_id"),
                logged_at=logged_at,
                notes=params.get("notes"),
            )
            db.add(food_log)
            await db.commit()
            await db.refresh(food_log)

            return {
                "success": True,
                "log_id": food_log.id,
                "message": "Food logged successfully",
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"Error logging food: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _tool_search_foods(db: AsyncSession, params: dict) -> dict:
        """Search for foods in database."""
        from sqlalchemy import func

        try:
            query = params["query"]
            limit = params.get("limit", 10)

            # Fuzzy search using pg_trgm
            result = await db.execute(
                select(Food)
                .where(func.similarity(Food.name, query) > 0.3)
                .order_by(func.similarity(Food.name, query).desc())
                .limit(limit)
            )
            foods = result.scalars().all()

            return {
                "success": True,
                "count": len(foods),
                "foods": [
                    {
                        "id": food.id,
                        "name": food.name,
                        "brand": food.brand,
                    }
                    for food in foods
                ],
            }

        except Exception as e:
            logger.error(f"Error searching foods: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _tool_resolve_foods_nl(db: AsyncSession, params: dict) -> dict:
        """Parse natural language food description."""
        try:
            # Delegate to existing FoodResolverService
            result = await FoodResolverService.resolve_foods(db, params["text"])

            # Convert to multi-food confirmation format
            multi_food_response = FoodResolverService.convert_to_multi_food_confirmation(result)

            # Return flattened response for multi-food confirmation UI
            return {
                "success": True,
                "multi_food_confirmation": multi_food_response.model_dump(),
            }

        except Exception as e:
            logger.error(f"Error resolving foods: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _tool_list_logs(
        db: AsyncSession, user_id: int, params: dict
    ) -> dict:
        """List food log entries."""
        try:
            query = select(FoodLog).where(FoodLog.user_id == user_id)

            # Apply filters
            if "date" in params:
                date_str = params["date"]
                date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()
                query = query.where(
                    func.date(FoodLog.logged_at) == date_obj
                )

            if "meal_id" in params:
                query = query.where(FoodLog.meal_id == params["meal_id"])

            # Order by most recent
            query = query.order_by(FoodLog.logged_at.desc())
            query = query.limit(params.get("limit", 20))

            # Execute with food relationship
            query = query.options(selectinload(FoodLog.food))
            result = await db.execute(query)
            logs = result.scalars().all()

            return {
                "success": True,
                "count": len(logs),
                "logs": [
                    {
                        "id": log.id,
                        "food_name": log.food.name,
                        "quantity": float(log.quantity),
                        "meal_id": log.meal_id,
                        "logged_at": log.logged_at.isoformat(),
                        "notes": log.notes,
                    }
                    for log in logs
                ],
            }

        except Exception as e:
            logger.error(f"Error listing logs: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _tool_delete_log(
        db: AsyncSession, user_id: int, params: dict
    ) -> dict:
        """Delete a food log entry."""
        try:
            log_id = params["log_id"]

            # Fetch the log and check ownership
            result = await db.execute(
                select(FoodLog)
                .options(selectinload(FoodLog.food))
                .where(FoodLog.id == log_id)
                .where(FoodLog.user_id == user_id)
            )
            log = result.scalar_one_or_none()

            if not log:
                return {"error": "Food log not found or you don't have permission to delete it"}

            # Store food name for response
            food_name = log.food.name
            logged_at = log.logged_at.isoformat()

            # Delete the log
            await db.delete(log)
            await db.commit()

            return {
                "success": True,
                "message": f"Deleted {food_name} logged at {logged_at}",
                "food_name": food_name,
                "logged_at": logged_at,
            }

        except Exception as e:
            await db.rollback()
            logger.error(f"Error deleting log: {e}")
            return {"error": str(e)}

    @staticmethod
    async def _tool_get_daily_summary(
        db: AsyncSession, user_id: int, params: dict
    ) -> dict:
        """Get nutrition summary for a date."""
        try:
            date_str = params["date"]
            date_obj = datetime.strptime(date_str, "%Y-%m-%d").date()

            # Get all logs for the date
            from sqlalchemy import func

            result = await db.execute(
                select(FoodLog)
                .options(
                    selectinload(FoodLog.food).selectinload(Food.food_nutrients)
                )
                .where(FoodLog.user_id == user_id)
                .where(func.date(FoodLog.logged_at) == date_obj)
            )
            logs = result.scalars().all()

            # Calculate totals (simplified - should aggregate nutrients properly)
            total_logs = len(logs)
            total_quantity = sum(float(log.quantity) for log in logs)

            return {
                "success": True,
                "date": date_str,
                "total_logs": total_logs,
                "total_quantity": total_quantity,
                "message": f"Found {total_logs} food entries totaling {total_quantity}g",
            }

        except Exception as e:
            logger.error(f"Error getting daily summary: {e}")
            return {"error": str(e)}
