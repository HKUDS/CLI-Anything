from __future__ import annotations

from typing import Any

from .types import JsonDict


def normalize_state(raw_state: JsonDict) -> JsonDict:
    state_type = str(raw_state.get("state_type") or "unknown")
    run = _copy_dict(raw_state.get("run"))
    context = {
        "act": run.get("act"),
        "floor": run.get("floor"),
        "ascension": run.get("ascension"),
    }

    if state_type in {"monster", "elite", "boss"}:
        return _normalize_combat(raw_state, state_type, context)
    if state_type == "hand_select":
        return _normalize_hand_select(raw_state, context)
    if state_type == "card_reward":
        return _normalize_card_reward(raw_state, context)
    if state_type == "combat_rewards":
        return _normalize_combat_rewards(raw_state, context)
    if state_type == "map":
        return _normalize_map(raw_state, context)
    if state_type == "event":
        return _normalize_event(raw_state, context)
    if state_type == "rest_site":
        return _normalize_rest_site(raw_state, context)
    if state_type == "shop":
        return _normalize_shop(raw_state, context)
    if state_type == "card_select":
        return _normalize_card_select(raw_state, context)
    if state_type == "relic_select":
        return _normalize_relic_select(raw_state, context)
    if state_type == "treasure":
        return _normalize_treasure(raw_state, context)
    if state_type == "game_over":
        return _normalize_game_over(raw_state, context)
    if state_type == "menu":
        menu = _copy_dict(raw_state.get("menu"))
        return {
            "type": "status",
            "decision": "menu",
            "context": context,
            "run": run,
            "message": raw_state.get("message"),
            "screen": menu.get("screen"),
            "can_continue_game": menu.get("can_continue_game", False),
            "can_start_new_game": menu.get("can_start_new_game", False),
            "can_abandon_game": menu.get("can_abandon_game", False),
            "characters": _copy_list(menu.get("characters")),
            "ascension": menu.get("ascension"),
            "menu": menu,
        }
    if state_type == "overlay":
        return {
            "type": "status",
            "decision": "overlay",
            "context": context,
            "run": run,
            "overlay": _copy_dict(raw_state.get("overlay")),
        }
    return {
        "type": "status",
        "decision": "unknown",
        "context": context,
        "run": run,
        "raw_state_type": state_type,
        "message": raw_state.get("message"),
        "raw": raw_state,
    }


def _normalize_combat(raw_state: JsonDict, state_type: str, context: JsonDict) -> JsonDict:
    battle = _copy_dict(raw_state.get("battle"))
    player = _copy_dict(battle.get("player"))
    return {
        "type": "decision",
        "decision": "combat_play",
        "room_type": state_type,
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "round": battle.get("round"),
        "turn": battle.get("turn"),
        "is_play_phase": battle.get("is_play_phase"),
        "energy": player.get("energy", 0),
        "max_energy": player.get("max_energy", 0),
        "hand": _copy_list(player.get("hand")),
        "enemies": _copy_list(battle.get("enemies")),
        "player": player,
        "draw_pile_count": player.get("draw_pile_count", 0),
        "discard_pile_count": player.get("discard_pile_count", 0),
        "exhaust_pile_count": player.get("exhaust_pile_count", 0),
        "battle": battle,
    }


def _normalize_hand_select(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    hand_select = _copy_dict(raw_state.get("hand_select"))
    battle = _copy_dict(raw_state.get("battle"))
    player = _copy_dict(battle.get("player"))
    return {
        "type": "decision",
        "decision": "hand_select",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "mode": hand_select.get("mode"),
        "prompt": hand_select.get("prompt"),
        "cards": _copy_list(hand_select.get("cards")),
        "selected_cards": _copy_list(hand_select.get("selected_cards")),
        "can_confirm": hand_select.get("can_confirm", False),
        "player": player,
        "battle": battle,
        "hand_select": hand_select,
    }


def _normalize_card_reward(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    reward = _copy_dict(raw_state.get("card_reward"))
    return {
        "type": "decision",
        "decision": "card_reward",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "cards": _copy_list(reward.get("cards")),
        "can_skip": reward.get("can_skip", False),
        "player": _copy_dict(reward.get("player")),
        "card_reward": reward,
    }


def _normalize_combat_rewards(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    rewards = _copy_dict(raw_state.get("rewards"))
    return {
        "type": "decision",
        "decision": "combat_rewards",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "items": _copy_list(rewards.get("items")),
        "can_proceed": rewards.get("can_proceed", False),
        "player": _copy_dict(rewards.get("player")),
        "rewards": rewards,
    }


def _normalize_map(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    map_state = _copy_dict(raw_state.get("map"))
    return {
        "type": "decision",
        "decision": "map_select",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "choices": _copy_list(map_state.get("next_options")),
        "player": _copy_dict(map_state.get("player")),
        "current_position": _copy_dict(map_state.get("current_position")),
        "visited": _copy_list(map_state.get("visited")),
        "nodes": _copy_list(map_state.get("nodes")),
        "boss": _copy_dict(map_state.get("boss")),
        "map": map_state,
    }


def _normalize_event(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    event = _copy_dict(raw_state.get("event"))
    return {
        "type": "decision",
        "decision": "event_choice",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "event_name": event.get("event_name"),
        "event_id": event.get("event_id"),
        "description": event.get("body"),
        "options": _copy_list(event.get("options")),
        "player": _copy_dict(event.get("player")),
        "in_dialogue": event.get("in_dialogue", False),
        "is_ancient": event.get("is_ancient", False),
        "event": event,
    }


def _normalize_rest_site(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    rest = _copy_dict(raw_state.get("rest_site"))
    return {
        "type": "decision",
        "decision": "rest_site",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "options": _copy_list(rest.get("options")),
        "player": _copy_dict(rest.get("player")),
        "can_proceed": rest.get("can_proceed", False),
        "rest_site": rest,
    }


def _normalize_shop(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    shop = _copy_dict(raw_state.get("shop"))
    items = _copy_list(shop.get("items"))
    return {
        "type": "decision",
        "decision": "shop",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "items": items,
        "cards": [item for item in items if item.get("category") == "card"],
        "relics": [item for item in items if item.get("category") == "relic"],
        "potions": [item for item in items if item.get("category") == "potion"],
        "card_removal": next((item for item in items if item.get("category") == "card_removal"), None),
        "player": _copy_dict(shop.get("player")),
        "can_proceed": shop.get("can_proceed", False),
        "shop": shop,
    }


def _normalize_card_select(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    card_select = _copy_dict(raw_state.get("card_select"))
    return {
        "type": "decision",
        "decision": "card_select",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "screen_type": card_select.get("screen_type"),
        "prompt": card_select.get("prompt"),
        "cards": _copy_list(card_select.get("cards")),
        "player": _copy_dict(card_select.get("player")),
        "preview_showing": card_select.get("preview_showing", False),
        "can_skip": card_select.get("can_skip", False),
        "can_confirm": card_select.get("can_confirm", False),
        "can_cancel": card_select.get("can_cancel", False),
        "card_select": card_select,
    }


def _normalize_relic_select(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    relic_select = _copy_dict(raw_state.get("relic_select"))
    return {
        "type": "decision",
        "decision": "relic_select",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "prompt": relic_select.get("prompt"),
        "relics": _copy_list(relic_select.get("relics")),
        "player": _copy_dict(relic_select.get("player")),
        "can_skip": relic_select.get("can_skip", False),
        "relic_select": relic_select,
    }


def _normalize_treasure(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    treasure = _copy_dict(raw_state.get("treasure"))
    return {
        "type": "decision",
        "decision": "treasure",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "relics": _copy_list(treasure.get("relics")),
        "player": _copy_dict(treasure.get("player")),
        "can_proceed": treasure.get("can_proceed", False),
        "message": treasure.get("message"),
        "treasure": treasure,
    }


def _normalize_game_over(raw_state: JsonDict, context: JsonDict) -> JsonDict:
    game_over = _copy_dict(raw_state.get("game_over"))
    return {
        "type": "decision",
        "decision": "game_over",
        "context": context,
        "run": _copy_dict(raw_state.get("run")),
        "player": _copy_dict(game_over.get("player")),
        "screen_type": game_over.get("screen_type"),
        "can_return_to_main_menu": game_over.get("can_return_to_main_menu", False),
        "can_continue": game_over.get("can_continue", False),
        "can_view_run": game_over.get("can_view_run", False),
        "options": _copy_list(game_over.get("options")),
        "game_over": game_over,
    }


def _copy_dict(value: Any) -> JsonDict:
    return dict(value) if isinstance(value, dict) else {}


def _copy_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, list) else []
