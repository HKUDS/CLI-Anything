from __future__ import annotations

from .types import JsonDict


def play_card(card_index: int, target: str | None = None) -> JsonDict:
    payload: JsonDict = {"action": "play_card", "card_index": card_index}
    if target is not None:
        payload["target"] = target
    return payload


def use_potion(slot: int, target: str | None = None) -> JsonDict:
    payload: JsonDict = {"action": "use_potion", "slot": slot}
    if target is not None:
        payload["target"] = target
    return payload


def end_turn() -> JsonDict:
    return {"action": "end_turn"}


def choose_map_node(index: int) -> JsonDict:
    return {"action": "choose_map_node", "index": index}


def choose_event_option(index: int) -> JsonDict:
    return {"action": "choose_event_option", "index": index}


def advance_dialogue() -> JsonDict:
    return {"action": "advance_dialogue"}


def choose_rest_option(index: int) -> JsonDict:
    return {"action": "choose_rest_option", "index": index}


def shop_purchase(index: int) -> JsonDict:
    return {"action": "shop_purchase", "index": index}


def claim_reward(index: int) -> JsonDict:
    return {"action": "claim_reward", "index": index}


def select_card_reward(card_index: int) -> JsonDict:
    return {"action": "select_card_reward", "card_index": card_index}


def skip_card_reward() -> JsonDict:
    return {"action": "skip_card_reward"}


def proceed() -> JsonDict:
    return {"action": "proceed"}


def select_card(index: int) -> JsonDict:
    return {"action": "select_card", "index": index}


def confirm_selection() -> JsonDict:
    return {"action": "confirm_selection"}


def cancel_selection() -> JsonDict:
    return {"action": "cancel_selection"}


def combat_select_card(card_index: int) -> JsonDict:
    return {"action": "combat_select_card", "card_index": card_index}


def combat_confirm_selection() -> JsonDict:
    return {"action": "combat_confirm_selection"}


def select_relic(index: int) -> JsonDict:
    return {"action": "select_relic", "index": index}


def skip_relic_selection() -> JsonDict:
    return {"action": "skip_relic_selection"}


def claim_treasure_relic(index: int) -> JsonDict:
    return {"action": "claim_treasure_relic", "index": index}


def continue_game() -> JsonDict:
    return {"action": "continue_game"}


def start_new_game(character: str = "IRONCLAD", ascension: int = 0) -> JsonDict:
    return {"action": "start_new_game", "character": character, "ascension": ascension}


def abandon_game() -> JsonDict:
    return {"action": "abandon_game"}


def return_to_main_menu() -> JsonDict:
    return {"action": "return_to_main_menu"}


def from_name(name: str, **kwargs: object) -> JsonDict:
    factories = {
        "play_card": play_card,
        "use_potion": use_potion,
        "end_turn": end_turn,
        "choose_map_node": choose_map_node,
        "choose_event_option": choose_event_option,
        "advance_dialogue": advance_dialogue,
        "choose_rest_option": choose_rest_option,
        "shop_purchase": shop_purchase,
        "claim_reward": claim_reward,
        "select_card_reward": select_card_reward,
        "skip_card_reward": skip_card_reward,
        "proceed": proceed,
        "select_card": select_card,
        "confirm_selection": confirm_selection,
        "cancel_selection": cancel_selection,
        "combat_select_card": combat_select_card,
        "combat_confirm_selection": combat_confirm_selection,
        "select_relic": select_relic,
        "skip_relic_selection": skip_relic_selection,
        "claim_treasure_relic": claim_treasure_relic,
        "continue_game": continue_game,
        "start_new_game": start_new_game,
        "abandon_game": abandon_game,
        "return_to_main_menu": return_to_main_menu,
    }
    try:
        factory = factories[name]
    except KeyError as exc:
        raise ValueError(f"Unknown action name: {name}") from exc
    return factory(**kwargs)
