"""Response shaping, including the privacy boundary for PRIVATE goals.

A PRIVATE goal still counts towards its owner's progress — that is the whole
point of the accountability model — but teammates must never see its title,
description, targets or values. Every cross-user response goes through
`goal_tree` with `viewer_is_owner=False` so there is a single place where that
can be got wrong.
"""

import uuid

from app.models.domain import ChallengeParticipant, Goal, GoalVisibility, TeamMember
from app.services.goals import participant_is_locked
from app.services.progress import calculate_goal_progress


def goal_detail(goal: Goal) -> dict:
    """Full goal, for the owner only."""
    return {
        "id": goal.id,
        "parent_goal_id": goal.parent_goal_id,
        "category": goal.category,
        "title": goal.title,
        "description": goal.description,
        "tracking_type": goal.tracking_type,
        "baseline_value": goal.baseline_value,
        "target_value": goal.target_value,
        "current_value": goal.current_value,
        "unit": goal.unit,
        "target_direction": goal.target_direction,
        "manual_progress_percentage": goal.manual_progress_percentage,
        "visibility": goal.visibility,
        "required": goal.required,
        "sort_order": goal.sort_order,
        "locked_at": goal.locked_at,
        "completed_at": goal.completed_at,
        "progress_percentage": round(calculate_goal_progress(goal), 1),
        "private": False,
        "children": [goal_detail(child) for child in sorted_children(goal)],
    }


def sorted_children(goal: Goal) -> list[Goal]:
    return sorted(goal.children, key=lambda child: (child.sort_order, child.created_at))


def is_private(goal: Goal) -> bool:
    return goal.visibility == GoalVisibility.PRIVATE


def goal_tree(goals: list[Goal], *, viewer_is_owner: bool) -> dict:
    """Itemised goals the viewer may see, plus counts for the ones they may not.

    Returns `{"goals": [...], "private_committed": n, "private_completed": n}`.
    """
    if viewer_is_owner:
        return {
            "goals": [goal_detail(goal) for goal in goals],
            "private_committed": 0,
            "private_completed": 0,
        }

    visible: list[dict] = []
    private_committed = 0
    private_completed = 0
    for goal in goals:
        if is_private(goal):
            private_committed += 1
            private_completed += 1 if goal.completed_at else 0
            continue
        payload = goal_detail(goal)
        children = []
        for child in sorted_children(goal):
            if is_private(child):
                private_committed += 1
                private_completed += 1 if child.completed_at else 0
                continue
            children.append(goal_detail(child))
        payload["children"] = children
        visible.append(payload)
    return {
        "goals": visible,
        "private_committed": private_committed,
        "private_completed": private_completed,
    }


def category_progress(goals: list[Goal]) -> dict[str, float]:
    """Mean progress per category across all goals, private ones included.

    Aggregates are deliberately computed before redaction: a member's headline
    number must reflect everything they committed to.
    """
    buckets: dict[str, list[float]] = {}
    for goal in goals:
        buckets.setdefault(goal.category.value, []).append(
            calculate_goal_progress(goal)
        )
    return {
        category: round(sum(values) / len(values), 1)
        for category, values in buckets.items()
    }


def overall_progress(goals: list[Goal]) -> float:
    categories = category_progress(goals)
    if not categories:
        return 0.0
    return round(sum(categories.values()) / len(categories), 1)


def member_card(
    *,
    participant: ChallengeParticipant,
    goals: list[Goal],
    streak: int,
    viewer_id: uuid.UUID,
) -> dict:
    """Dashboard card. Safe for any teammate: no titles, only counts."""
    return {
        "user_id": participant.user_id,
        "display_name": participant.user.display_name,
        "avatar_url": participant.user.avatar_url,
        "is_self": participant.user_id == viewer_id,
        "overall_progress": overall_progress(goals),
        "categories": category_progress(goals),
        "streak": streak,
        "goals_locked": participant_is_locked(participant),
        "goals_submitted": bool(goals),
        "goals_committed": len(goals),
        "goals_completed": sum(1 for goal in goals if goal.completed_at),
        "participant_status": participant.status,
    }


def member_row(member: TeamMember) -> dict:
    return {
        "id": member.user.id,
        "display_name": member.user.display_name,
        "avatar_url": member.user.avatar_url,
        "email": member.user.email,
        "role": member.role,
        "joined_at": member.joined_at,
    }


def member_public(member: TeamMember) -> dict:
    """Roster identity without email — what an LLM is allowed to see."""
    row = member_row(member)
    row.pop("email", None)
    return row


def notification_row(row) -> dict:
    return {
        "id": row.id,
        "type": row.type,
        "title": row.title,
        "body": row.body,
        "link_path": row.link_path,
        "read_at": row.read_at,
        "created_at": row.created_at,
    }


def progress_entry(entry) -> dict:
    return {
        "id": entry.id,
        "entry_date": entry.entry_date,
        "numeric_value": entry.numeric_value,
        "numeric_delta": entry.numeric_delta,
        "manual_percentage": entry.manual_percentage,
        "completed": entry.completed,
        "note": entry.note,
        "evidence_url": entry.evidence_url,
        "created_at": entry.created_at,
    }


def audit_row(row) -> dict:
    return {
        "id": row.id,
        "actor_user_id": row.actor_user_id,
        "actor": row.actor.display_name,
        "action": row.action,
        "entity_type": row.entity_type,
        "entity_id": row.entity_id,
        "metadata": row.metadata_json,
        "created_at": row.created_at,
    }
