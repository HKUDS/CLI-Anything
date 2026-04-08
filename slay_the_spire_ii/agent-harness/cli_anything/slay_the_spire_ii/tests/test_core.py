"""Unit tests for the Slay the Spire II CLI harness core modules."""

from __future__ import annotations

import unittest

from cli_anything.slay_the_spire_ii.core import action_adapter
from cli_anything.slay_the_spire_ii.core.state_adapter import normalize_state


class TestActionAdapter(unittest.TestCase):
    def test_play_card_without_target_omits_target_field(self) -> None:
        payload = action_adapter.play_card(2)
        self.assertEqual(payload, {"action": "play_card", "card_index": 2})

    def test_play_card_with_target_includes_target_field(self) -> None:
        payload = action_adapter.play_card(1, target="slime_0")
        self.assertEqual(
            payload,
            {"action": "play_card", "card_index": 1, "target": "slime_0"},
        )

    def test_start_new_game_preserves_parameters(self) -> None:
        payload = action_adapter.start_new_game("REGENT", 12)
        self.assertEqual(
            payload,
            {"action": "start_new_game", "character": "REGENT", "ascension": 12},
        )

    def test_from_name_dispatches_and_rejects_unknown_actions(self) -> None:
        payload = action_adapter.from_name("choose_rest_option", index=1)
        self.assertEqual(payload, {"action": "choose_rest_option", "index": 1})

        with self.assertRaisesRegex(ValueError, "Unknown action name"):
            action_adapter.from_name("missing_action")


class TestStateAdapter(unittest.TestCase):
    def test_normalize_combat_state(self) -> None:
        raw_state = {
            "state_type": "monster",
            "run": {"act": 1, "floor": 3, "ascension": 7},
            "battle": {
                "round": 2,
                "turn": 1,
                "is_play_phase": True,
                "player": {
                    "energy": 3,
                    "max_energy": 3,
                    "hand": [{"name": "Strike", "cost": 1}],
                    "draw_pile_count": 10,
                    "discard_pile_count": 2,
                    "exhaust_pile_count": 0,
                },
                "enemies": [{"id": "slime_0", "hp": 12}],
            },
        }

        normalized = normalize_state(raw_state)

        self.assertEqual(normalized["decision"], "combat_play")
        self.assertEqual(normalized["room_type"], "monster")
        self.assertEqual(normalized["context"], {"act": 1, "floor": 3, "ascension": 7})
        self.assertEqual(normalized["energy"], 3)
        self.assertEqual(normalized["hand"][0]["name"], "Strike")
        self.assertEqual(normalized["enemies"][0]["id"], "slime_0")

    def test_normalize_shop_state_groups_items(self) -> None:
        raw_state = {
            "state_type": "shop",
            "run": {"act": 2, "floor": 20, "ascension": 5},
            "shop": {
                "items": [
                    {"name": "Bash", "category": "card"},
                    {"name": "Anchor", "category": "relic"},
                    {"name": "Dexterity Potion", "category": "potion"},
                    {"name": "Remove a card", "category": "card_removal"},
                ],
                "player": {"gold": 222},
                "can_proceed": True,
            },
        }

        normalized = normalize_state(raw_state)

        self.assertEqual(normalized["decision"], "shop")
        self.assertEqual(len(normalized["cards"]), 1)
        self.assertEqual(len(normalized["relics"]), 1)
        self.assertEqual(len(normalized["potions"]), 1)
        self.assertEqual(normalized["card_removal"]["category"], "card_removal")
        self.assertTrue(normalized["can_proceed"])

    def test_normalize_menu_state(self) -> None:
        raw_state = {
            "state_type": "menu",
            "run": {"act": None, "floor": None, "ascension": None},
            "menu": {
                "screen": "main_menu",
                "can_continue_game": True,
                "can_start_new_game": True,
                "can_abandon_game": False,
                "characters": ["IRONCLAD", "SILENT"],
                "ascension": 10,
            },
        }

        normalized = normalize_state(raw_state)

        self.assertEqual(normalized["decision"], "menu")
        self.assertTrue(normalized["can_continue_game"])
        self.assertTrue(normalized["can_start_new_game"])
        self.assertEqual(normalized["characters"], ["IRONCLAD", "SILENT"])

    def test_normalize_overlay_state(self) -> None:
        raw_state = {
            "state_type": "overlay",
            "run": {"act": 1, "floor": 5, "ascension": 0},
            "overlay": {"screen_type": "confirm", "message": "Choose one"},
        }

        normalized = normalize_state(raw_state)

        self.assertEqual(normalized["decision"], "overlay")
        self.assertEqual(normalized["overlay"]["screen_type"], "confirm")

    def test_normalize_unknown_state_preserves_raw_payload(self) -> None:
        raw_state = {
            "state_type": "mystery_screen",
            "message": "Unexpected",
            "run": {"act": 3, "floor": 42, "ascension": 20},
        }

        normalized = normalize_state(raw_state)

        self.assertEqual(normalized["decision"], "unknown")
        self.assertEqual(normalized["raw_state_type"], "mystery_screen")
        self.assertEqual(normalized["message"], "Unexpected")
        self.assertEqual(normalized["raw"], raw_state)


if __name__ == "__main__":
    unittest.main()
