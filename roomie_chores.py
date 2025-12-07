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
START_DATE = "2025-12-07"  # when the chores rotation begins, can rlly be any week


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

if not NOTION_TOKEN or not CHORES_DATABASE_ID:
    print("Error: NOTION_TOKEN and CHORES_DATABASE_ID must be set")
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


def get_rooms() -> List[Dict[str, Any]]:
    """Fetch all room pages from the chores database."""
    rooms = []

    try:
        response = notion.databases.query(database_id=CHORES_DATABASE_ID)

        for page in response.get("results", []):
            room_id, room_name, emoji = get_page_properties(page)

            if room_name:
                rooms.append(
                    {
                        ID: room_id,
                        NAME: room_name,
                        EMOJI: emoji,
                    }
                )

        while response.get("has_more"):
            response = notion.databases.query(
                database_id=CHORES_DATABASE_ID, start_cursor=response["next_cursor"]
            )
            for page in response.get("results", []):
                room_id, room_name, emoji = get_page_properties(page)

                if room_name:
                    rooms.append({ID: room_id, NAME: room_name, EMOJI: emoji})

    except Exception as e:
        print(f"Error fetching rooms from database: {e}")
        sys.exit(1)

    return rooms


def get_page_properties(page: Dict[str, Any]) -> Tuple[str, str, str]:
    """Extract the page ID, title, and emoji from a Notion page."""
    page_id = page.get(ID, "")
    properties = page.get(PROPERTIES, {})

    room_name = ""
    for prop_data in properties.values():
        prop_type = prop_data.get(TYPE)
        if prop_type == TITLE:
            title_array = prop_data.get(TITLE, [])
            if title_array:
                room_name = title_array[0].get(TEXT, "")
                break

    emoji = ""
    icon = page.get(ICON)
    if icon and icon.get(TYPE) == EMOJI:
        emoji = icon.get(EMOJI, "")

    return page_id, room_name, emoji


def assign_roomies(
    rooms: List[Dict[str, Any]], roomies: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """Assign roomies to rooms based on rotation schedule."""
    weeks_from_start = (
        datetime.now() - datetime.strptime(START_DATE, "%Y-%m-%d")
    ).days // 7

    for room_idx, room in enumerate(rooms):
        idx = (room_idx + weeks_from_start) % len(roomies)
        room[ASSIGNED] = roomies[idx]

    return rooms


def create_weekly_task(room: Dict[str, Any], due_date_str: str) -> bool:
    """Create a new weekly task for a room."""
    properties = {
        NAME: {
            TITLE: [
                {
                    TEXT: {
                        "content": f"🧹 {room[ASSIGNED][NAME][CONTENT]}'s chore for {due_date_str}"
                    }
                }
            ]
        }
    }

    properties[DUE_DATE] = {DATE: {"start": due_date_str}}
    properties[RESPONSIBLE] = {RELATION: [{ID: room[ASSIGNED][ID]}]}
    properties[CHORE] = {RELATION: [{ID: room[ID]}]}

    icon = None
    if room.get(EMOJI):
        icon = {TYPE: EMOJI, EMOJI: room[EMOJI]}

    try:
        notion.pages.create(
            parent={DATABASE_ID: TODOS_DATABASE_ID},
            properties=properties,
            icon=icon,
        )
        print(
            f"✓ Created task in {room[NAME]} for {room[ASSIGNED][NAME]} (due {due_date_str})"
        )
        return True
    except Exception as e:
        print(f"✗ Error creating task for {room[NAME]}: {e}")
        return False


def main():
    """Main function to create weekly tasks for all rooms."""
    print("Starting chores automation...")

    rooms = get_rooms()
    if not rooms:
        print("No rooms found in the database.")
        return

    roomies = get_roomies()
    if not roomies:
        print("No roomies found in the database.")
        return

    print(f"Found {len(rooms)} room(s) and {len(roomies)} roomie(s)")

    due_date_str = (datetime.now() + timedelta(days=7)).strftime("%Y-%m-%d")

    success_count = 0
    rooms_assigned = assign_roomies(rooms, roomies)
    for room in rooms_assigned:
        if create_weekly_task(room, due_date_str):
            success_count += 1

    print(f"\nCompleted: {success_count}/{len(rooms)} tasks created successfully")


if __name__ == "__main__":
    main()
