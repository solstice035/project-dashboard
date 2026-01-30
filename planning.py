"""
Planning module for Project Dashboard.
Handles planning session business logic.
"""

import logging
from typing import Any

import database as db

logger = logging.getLogger(__name__)


def start_planning_session(context_fetcher: callable) -> dict:
    """
    Start a new planning session.

    Args:
        context_fetcher: A callable that returns the initial context dict
                         (tasks, kanban state, etc.)

    Returns:
        dict with status, session_id, started_at, and context on success,
        or error info on failure.
    """
    try:
        context = context_fetcher()
        result = db.create_planning_session(context)

        if result:
            return {
                'status': 'ok',
                'session_id': result['id'],
                'started_at': result['started_at'].isoformat(),
                'context': context
            }
        else:
            return {'status': 'error', 'error': 'Failed to create session'}

    except Exception as e:
        logger.error(f"Error starting planning session: {e}")
        return {'status': 'error', 'error': str(e)}


def end_planning_session(session_id: int, final_state: dict = None) -> dict:
    """
    End a planning session.

    Args:
        session_id: The session ID to end
        final_state: Optional final state dict to store

    Returns:
        dict with status and session stats on success, or error info on failure.
    """
    if not session_id:
        return {'status': 'error', 'error': 'session_id required'}

    try:
        result = db.end_planning_session(session_id, final_state or {})

        if result:
            return {
                'status': 'ok',
                'session_id': result['id'],
                'duration_seconds': result['duration_seconds'],
                'messages_count': result['messages_count'],
                'actions_count': result['actions_count']
            }
        else:
            return {'status': 'error', 'error': 'Session not found'}

    except Exception as e:
        logger.error(f"Error ending planning session: {e}")
        return {'status': 'error', 'error': str(e)}


def log_action(session_id: int, action_type: str, target_type: str = None,
               target_id: str = None, target_title: str = None,
               details: dict = None) -> dict:
    """
    Log a planning action (task change).

    Returns:
        dict with status and action_id on success, or error info on failure.
    """
    try:
        action_id = db.insert_planning_action(
            session_id=session_id,
            action_type=action_type,
            target_type=target_type,
            target_id=target_id,
            target_title=target_title,
            details=details
        )

        if action_id is not None:
            return {'status': 'ok', 'action_id': action_id}
        else:
            return {'status': 'error', 'error': 'Failed to log action'}

    except Exception as e:
        logger.error(f"Error logging planning action: {e}")
        return {'status': 'error', 'error': str(e)}


def log_message(session_id: int, role: str, content: str,
                tokens_used: int = None) -> dict:
    """
    Log a chat message in the planning session.

    Returns:
        dict with status and message_id on success, or error info on failure.
    """
    try:
        msg_id = db.insert_planning_message(
            session_id=session_id,
            role=role,
            content=content,
            tokens_used=tokens_used
        )

        if msg_id is not None:
            return {'status': 'ok', 'message_id': msg_id}
        else:
            return {'status': 'error', 'error': 'Failed to log message'}

    except Exception as e:
        logger.error(f"Error logging planning message: {e}")
        return {'status': 'error', 'error': str(e)}


def get_analytics(days: int = 30) -> dict:
    """
    Get planning analytics and trends.

    Returns:
        dict with sessions, action_breakdown, and totals.
    """
    try:
        sessions = db.get_planning_sessions(days=days)
        action_breakdown = db.get_planning_action_breakdown(days=days)
        totals = db.get_planning_totals(days=days)

        return {
            'days': days,
            'sessions': sessions,
            'action_breakdown': action_breakdown,
            'totals': totals
        }

    except Exception as e:
        logger.error(f"Error getting planning analytics: {e}")
        return {
            'days': days,
            'sessions': [],
            'action_breakdown': [],
            'totals': {},
            'error': str(e)
        }
