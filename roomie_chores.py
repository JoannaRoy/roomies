#!/usr/bin/env python3
"""
Notion Chores Automation Script
Creates weekly chore tasks for each room in the Notion chores database.
"""

import os
import sys
from datetime import datetime, timedelta
from typing import List, Dict, Any, Tuple
from notion_client import Client
from dotenv import load_dotenv

load_dotenv()

NOTION_TOKEN = os.getenv("NOTION_TOKEN")
CHORES_DATABASE_ID = os.getenv("CHORES_DATABASE_ID")
ROOMIES_DATABASE_ID = os.getenv("ROOMIES_DATABASE_ID")
TODOS_DATABASE_ID = os.getenv("TODOS_DATABASE_ID")
START_DATE = "2025-12-21"  # when the chores rotation begins, can rlly be any week


# notion props
ID = "id"
DATABASE_ID = "database_id"
TITLE = "title"
CONTENT = "content"
TYPE = "type"
DATE = "date"
PAGE = "page"
EMOJI = "emoji"
RELATION = "relation"
PROPERTIES = "properties"
TEXT = "text"
ICON = "icon"
ASSIGNED = "assigned_person"

# notion columns
DUE_DATE = "do by"
CHORE = "chore"
RESPONSIBLE = "responsible roomie"
NAME = "name"
EVERY_X_WEEKS = "every X weeks"
NUMBER = "number"

missing_vars = []
if not NOTION_TOKEN:
    missing_vars.append("NOTION_TOKEN")
if not CHORES_DATABASE_ID:
    missing_vars.append("CHORES_DATABASE_ID")
if not ROOMIES_DATABASE_ID:
    missing_vars.append("ROOMIES_DATABASE_ID")
if not TODOS_DATABASE_ID:
    missing_vars.append("TODOS_DATABASE_ID")

if missing_vars:
    print(
        f"Error: The following environment variables are not set: {', '.join(missing_vars)}"
    )
    print("In GitHub Actions, make sure these are set as secrets in the workflow.")
    sys.exit(1)

notion = Client(auth=NOTION_TOKEN)


def get_roomies() -> List[Dict[str, Any]]:
    """Fetch all roomies from the chores database."""
    roomies = []

    try:
        response = notion.databases.query(database_id=ROOMIES_DATABASE_ID)

        for page in response.get("results", []):
            roomie_id, roomie_name, roomie_emoji = get_page_properties(page)

            roomies.append({ID: roomie_id, NAME: roomie_name, EMOJI: roomie_emoji})

    except Exception as e:
        print(f"Error fetching roomies from database: {e}")
        sys.exit(1)

    return roomies


def get_every_x_weeks(page: Dict[str, Any]) -> int:
    """Extract the 'every X weeks' value from a task page. Defaults to 1 (every week)."""
    properties = page.get(PROPERTIES, {})
    every_x_weeks_prop = properties.get(EVERY_X_WEEKS, {})
    value = every_x_weeks_prop.get(NUMBER)
    return value if value and value > 0 else 1


def get_tasks() -> List[Dict[str, Any]]:
    """Fetch all task pages from the chores database."""
    tasks = []

    response = notion.databases.query(database_id=CHORES_DATABASE_ID)

    for page in response.get("results", []):
        task_id, task_name, emoji = get_page_properties(page)

        if task_name:
            tasks.append(
                {
                    ID: task_id,
                    NAME: task_name,
                    EMOJI: emoji,
                    CONTENT: get_page_content(task_id),
                    EVERY_X_WEEKS: get_every_x_weeks(page),
                }
            )

    while response.get("has_more"):
        response = notion.databases.query(
            database_id=CHORES_DATABASE_ID, start_cursor=response["next_cursor"]
        )
        for page in response.get("results", []):
            task_id, task_name, emoji = get_page_properties(page)

            if task_name:
                tasks.append(
                    {
                        ID: task_id,
                        NAME: task_name,
                        EMOJI: emoji,
                        CONTENT: get_page_content(task_id),
                        EVERY_X_WEEKS: get_every_x_weeks(page),
                    }
                )

    return tasks


def get_page_properties(page: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extract the page ID, title, and emoji from a Notion page."""
    page_id = page.get(ID, "")
    properties = page.get(PROPERTIES, {})

    task_name = ""
    for prop_data in properties.values():
        prop_type = prop_data.get(TYPE)
        if prop_type == TITLE:
            title_array = prop_data.get(TITLE, [])
            if title_array:
                task_name = title_array[0].get(TEXT, "")
                break

    emoji = ""
    icon = page.get(ICON)
    if icon and icon.get(TYPE) == EMOJI:
        emoji = icon.get(EMOJI, "")

    return page_id, task_name, emoji


def get_page_content(page_id: str) -> List[Dict[str, Any]]:
    """Fetch the content blocks from a Notion page."""
    blocks = []
    response = notion.blocks.children.list(block_id=page_id)

    for block in response.get("results", []):
        block_copy = {TYPE: block.get(TYPE)}
        block_type = block.get(TYPE)
        if block_type in block:
            block_copy[block_type] = block[block_type]
        blocks.append(block_copy)

    while response.get("has_more"):
        response = notion.blocks.children.list(
            block_id=page_id, start_cursor=response["next_cursor"]
        )
        for block in response.get("results", []):
            block_copy = {TYPE: block.get(TYPE)}
            block_type = block.get(TYPE)
            if block_type in block:
                block_copy[block_type] = block[block_type]
            blocks.append(block_copy)

    return blocks


def assign_roomies(
    tasks: List[Dict[str, Any]], roomies: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Assign roomies to tasks based on rotation schedule."""
    weeks_from_start = (
        datetime.now() - datetime.strptime(START_DATE, "%Y-%m-%d")
    ).days // 7

    for task_idx, task in enumerate(tasks):
        idx = (task_idx + weeks_from_start) % len(roomies)
        task[ASSIGNED] = roomies[idx]

    return tasks


def create_task(task: Dict[str, Any], due_date_str: str) -> bool:
    """Create a new weekly task for a roomie."""
    properties = {
        NAME: {
            TITLE: [
                {
                    TEXT: {
                        "content": f"🧹 {task[ASSIGNED][NAME][CONTENT]}'s chore for {due_date_str}"
                    }
                }
            ]
        }
    }

    properties[DUE_DATE] = {DATE: {"start": due_date_str}}
    properties[RESPONSIBLE] = {RELATION: [{ID: task[ASSIGNED][ID]}]}
    properties[CHORE] = {RELATION: [{ID: task[ID]}]}

    icon = None
    if task.get(EMOJI):
        icon = {TYPE: EMOJI, EMOJI: task[EMOJI]}

    children = task.get(CONTENT, [])

    try:
        notion.pages.create(
            parent={DATABASE_ID: TODOS_DATABASE_ID},
            properties=properties,
            icon=icon,
            children=children,
        )
        print(
            f"✓ Created task in {task[NAME]} for {task[ASSIGNED][NAME]} (due {due_date_str})"
        )
        return True
    except Exception as e:
        print(f"✗ Error creating task for {task[NAME]}: {e}")
        return False


def get_tasks_for_this_week(tasks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Filter tasks to only include those that should be assigned this week."""
    weeks_from_start = (
        datetime.now() - datetime.strptime(START_DATE, "%Y-%m-%d")
    ).days // 7

    return [task for task in tasks if weeks_from_start % task[EVERY_X_WEEKS] == 0]


def main():
    """Main function to create weekly tasks for all roomies."""
    print("Starting chores automation...")

    tasks = get_tasks()
    if not tasks:
        print("No tasks found in the database.")
        return

    roomies = get_roomies()
    if not roomies:
        print("No roomies found in the database.")
        return

    print(f"Found {len(tasks)} task(s) and {len(roomies)} roomie(s)")

    tasks_this_week = get_tasks_for_this_week(tasks)
    print(f"{len(tasks_this_week)} task(s) scheduled for this week")

    if not tasks_this_week:
        print("No tasks to assign this week.")
        return

    due_date_str = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    success_count = 0
    tasks_assigned = assign_roomies(tasks_this_week, roomies)
    for task in tasks_assigned:
        if create_task(task, due_date_str):
            success_count += 1

    print(
        f"\nCompleted: {success_count}/{len(tasks_this_week)} tasks created successfully"
    )


if __name__ == "__main__":
    main()
