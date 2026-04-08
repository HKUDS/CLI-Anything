using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Cards;
using MegaCrit.Sts2.Core.Entities.Creatures;
using MegaCrit.Sts2.Core.HoverTips;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Entities.Potions;
using MegaCrit.Sts2.Core.Models;
using MegaCrit.Sts2.Core.MonsterMoves.Intents;
using MegaCrit.Sts2.Core.MonsterMoves.MonsterMoveStateMachine;
using MegaCrit.Sts2.Core.Entities.Merchant;
using MegaCrit.Sts2.Core.Entities.RestSite;
using MegaCrit.Sts2.Core.Events;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Map;
using MegaCrit.Sts2.Core.Nodes.Cards;
using MegaCrit.Sts2.Core.Nodes.Cards.Holders;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.CommonUi;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Rewards;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.GameOverScreen;
using MegaCrit.Sts2.Core.Nodes.Relics;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic;
using MegaCrit.Sts2.Core.Nodes.Screens.MainMenu;
using MegaCrit.Sts2.Core.Nodes.Screens.CharacterSelect;
using MegaCrit.Sts2.Core.Rewards;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;

namespace STS2_Bridge;

public static partial class BridgeMod
{
    private static Dictionary<string, object?> BuildGameState()
    {
        var result = new Dictionary<string, object?>();

        if (!RunManager.Instance.IsInProgress)
        {
            result["state_type"] = "menu";
            result["message"] = "No run in progress. Player is in the main menu.";
            result["menu"] = BuildMenuState();
            return result;
        }

        var runState = RunManager.Instance.DebugOnlyGetState();
        if (runState == null)
        {
            result["state_type"] = "unknown";
            return result;
        }

        // Card selection overlays can appear on top of any room (events, rest sites, combat)
        var topOverlay = NOverlayStack.Instance?.Peek();
        var currentRoom = runState.CurrentRoom;
        if (topOverlay is NCardGridSelectionScreen cardSelectScreen)
        {
            result["state_type"] = "card_select";
            result["card_select"] = BuildCardSelectState(cardSelectScreen, runState);
        }
        else if (topOverlay is NChooseACardSelectionScreen chooseCardScreen)
        {
            result["state_type"] = "card_select";
            result["card_select"] = BuildChooseCardState(chooseCardScreen, runState);
        }
        else if (topOverlay is NChooseARelicSelection relicSelectScreen)
        {
            result["state_type"] = "relic_select";
            result["relic_select"] = BuildRelicSelectState(relicSelectScreen, runState);
        }
        else if (topOverlay is NGameOverScreen gameOverScreen)
        {
            result["state_type"] = "game_over";
            result["game_over"] = BuildGameOverState(gameOverScreen, runState);
        }
        else if (topOverlay is IOverlayScreen
                 && topOverlay is not NRewardsScreen
                 && topOverlay is not NCardRewardSelectionScreen)
        {
            // Catch-all for unhandled overlays — prevents soft-locks
            result["state_type"] = "overlay";
            result["overlay"] = new Dictionary<string, object?>
            {
                ["screen_type"] = topOverlay.GetType().Name,
                ["message"] = $"An overlay ({topOverlay.GetType().Name}) is active. It may require manual interaction in-game."
            };
        }
        else if (currentRoom is CombatRoom combatRoom)
        {
            if (CombatManager.Instance.IsInProgress)
            {
                // Check for in-combat hand card selection (e.g., "Select a card to exhaust")
                var playerHand = NPlayerHand.Instance;
                if (playerHand != null && playerHand.IsInCardSelection)
                {
                    result["state_type"] = "hand_select";
                    result["hand_select"] = BuildHandSelectState(playerHand, runState);
                    result["battle"] = BuildBattleState(runState, combatRoom);
                }
                else
                {
                    result["state_type"] = combatRoom.RoomType.ToString().ToLower(); // monster, elite, boss
                    result["battle"] = BuildBattleState(runState, combatRoom);
                }
            }
            else
            {
                // After combat ends, check: map open (post-rewards) > overlays > fallback
                if (NMapScreen.Instance is { IsOpen: true })
                {
                    result["state_type"] = "map";
                    result["map"] = BuildMapState(runState);
                }
                else
                {
                    var overlay = NOverlayStack.Instance?.Peek();
                    if (overlay is NCardRewardSelectionScreen cardScreen)
                    {
                        result["state_type"] = "card_reward";
                        result["card_reward"] = BuildCardRewardState(cardScreen);
                    }
                    else if (overlay is NRewardsScreen rewardsScreen)
                    {
                        result["state_type"] = "combat_rewards";
                        result["rewards"] = BuildRewardsState(rewardsScreen, runState);
                    }
                    else
                    {
                        result["state_type"] = combatRoom.RoomType.ToString().ToLower();
                        result["message"] = "Combat ended. Waiting for rewards...";
                    }
                }
            }
        }
        else if (currentRoom is EventRoom eventRoom)
        {
            if (NMapScreen.Instance is { IsOpen: true })
            {
                result["state_type"] = "map";
                result["map"] = BuildMapState(runState);
            }
            else
            {
                result["state_type"] = "event";
                result["event"] = BuildEventState(eventRoom, runState);
            }
        }
        else if (currentRoom is MapRoom)
        {
            result["state_type"] = "map";
            result["map"] = BuildMapState(runState);
        }
        else if (currentRoom is MerchantRoom merchantRoom)
        {
            if (NMapScreen.Instance is { IsOpen: true })
            {
                result["state_type"] = "map";
                result["map"] = BuildMapState(runState);
            }
            else
            {
                // Auto-open the shopkeeper's inventory if not already open
                var merchUI = NMerchantRoom.Instance;
                if (merchUI != null && !merchUI.Inventory.IsOpen)
                {
                    merchUI.OpenInventory();
                }
                result["state_type"] = "shop";
                result["shop"] = BuildShopState(merchantRoom, runState);
            }
        }
        else if (currentRoom is RestSiteRoom restSiteRoom)
        {
            if (NMapScreen.Instance is { IsOpen: true })
            {
                result["state_type"] = "map";
                result["map"] = BuildMapState(runState);
            }
            else
            {
                result["state_type"] = "rest_site";
                result["rest_site"] = BuildRestSiteState(restSiteRoom, runState);
            }
        }
        else if (currentRoom is TreasureRoom treasureRoom)
        {
            if (NMapScreen.Instance is { IsOpen: true })
            {
                result["state_type"] = "map";
                result["map"] = BuildMapState(runState);
            }
            else
            {
                result["state_type"] = "treasure";
                result["treasure"] = BuildTreasureState(treasureRoom, runState);
            }
        }
        else
        {
            result["state_type"] = "unknown";
            result["room_type"] = currentRoom?.GetType().Name;
        }

        // Common run info
        result["run"] = new Dictionary<string, object?>
        {
            ["act"] = runState.CurrentActIndex + 1,
            ["floor"] = runState.TotalFloor,
            ["ascension"] = runState.AscensionLevel
        };

        return result;
    }

    private static Dictionary<string, object?> BuildGameOverState(NGameOverScreen screen, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold,
            };
        }

        state["screen_type"] = nameof(NGameOverScreen);

        var returnButton = FindFirst<NReturnToMainMenuButton>(screen);
        var continueButton = FindFirst<NGameOverContinueButton>(screen);
        var viewRunButton = FindFirst<NViewRunButton>(screen);

        state["can_return_to_main_menu"] = returnButton?.IsVisibleInTree() == true && returnButton.IsEnabled;
        state["can_continue"] = continueButton?.IsVisibleInTree() == true && continueButton.IsEnabled;
        state["can_view_run"] = viewRunButton?.IsVisibleInTree() == true && viewRunButton.IsEnabled;

        var options = new List<Dictionary<string, object?>>();
        if (returnButton != null && returnButton.IsVisibleInTree())
        {
            options.Add(new Dictionary<string, object?>
            {
                ["id"] = "return_to_main_menu",
                ["title"] = "Return To Main Menu",
                ["is_enabled"] = returnButton.IsEnabled,
            });
        }
        if (continueButton != null && continueButton.IsVisibleInTree())
        {
            options.Add(new Dictionary<string, object?>
            {
                ["id"] = "continue",
                ["title"] = "Continue",
                ["is_enabled"] = continueButton.IsEnabled,
            });
        }
        if (viewRunButton != null && viewRunButton.IsVisibleInTree())
        {
            options.Add(new Dictionary<string, object?>
            {
                ["id"] = "view_run",
                ["title"] = "View Run",
                ["is_enabled"] = viewRunButton.IsEnabled,
            });
        }
        state["options"] = options;

        return state;
    }

    private static Dictionary<string, object?> BuildMenuState()
    {
        var state = new Dictionary<string, object?>();

        var root = ((Godot.SceneTree)Godot.Engine.GetMainLoop()).Root;
        var characterSelect = FindFirst<NCharacterSelectScreen>(root);
        if (characterSelect != null && characterSelect.IsVisibleInTree())
        {
            state["screen"] = "character_select";

            var characters = new List<Dictionary<string, object?>>();
            foreach (var button in FindAll<NCharacterSelectButton>(characterSelect))
            {
                var character = button.Character;
                if (character == null) continue;

                characters.Add(new Dictionary<string, object?>
                {
                    ["id"] = character.Id.Entry,
                    ["name"] = SafeGetText(() => character.Title),
                });
            }
            state["characters"] = characters;

            var ascensionPanel = FindFirst<NAscensionPanel>(characterSelect);
            if (ascensionPanel != null)
                state["ascension"] = ascensionPanel.Ascension;

            var embarkButton = FindAll<NConfirmButton>(characterSelect)
                .FirstOrDefault(button => button.IsVisibleInTree());
            state["can_start_new_game"] = embarkButton?.IsEnabled ?? false;
            state["can_continue_game"] = false;
            state["can_abandon_game"] = false;

            return state;
        }

        var mainMenu = FindFirst<NMainMenu>(root);
        if (mainMenu != null && mainMenu.IsVisibleInTree())
        {
            state["screen"] = "main_menu";

            var continueInfo = mainMenu.ContinueRunInfo;
            bool canContinue = continueInfo != null && continueInfo.IsVisibleInTree();

            state["can_continue_game"] = canContinue;
            state["can_abandon_game"] = canContinue;
            state["can_start_new_game"] = true;
            return state;
        }

        state["screen"] = "unknown";
        state["can_continue_game"] = false;
        state["can_abandon_game"] = false;
        state["can_start_new_game"] = false;
        return state;
    }

    private static Dictionary<string, object?> BuildBattleState(RunState runState, CombatRoom combatRoom)
    {
        var combatState = CombatManager.Instance.DebugOnlyGetState();
        var battle = new Dictionary<string, object?>();

        if (combatState == null)
        {
            battle["error"] = "Combat state unavailable";
            return battle;
        }

        battle["round"] = combatState.RoundNumber;
        battle["turn"] = combatState.CurrentSide.ToString().ToLower();
        battle["is_play_phase"] = CombatManager.Instance.IsPlayPhase;

        // Player state
        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            battle["player"] = BuildPlayerState(player);
        }

        // Enemies
        var enemies = new List<Dictionary<string, object?>>();
        var entityCounts = new Dictionary<string, int>();
        foreach (var creature in combatState.Enemies)
        {
            if (creature.IsAlive)
            {
                enemies.Add(BuildEnemyState(creature, entityCounts));
            }
        }
        battle["enemies"] = enemies;

        return battle;
    }

    private static Dictionary<string, object?> BuildPlayerState(Player player)
    {
        var state = new Dictionary<string, object?>();
        var creature = player.Creature;
        var combatState = player.PlayerCombatState;

        state["character"] = SafeGetText(() => player.Character.Title);
        state["hp"] = creature.CurrentHp;
        state["max_hp"] = creature.MaxHp;
        state["block"] = creature.Block;

        if (combatState != null)
        {
            state["energy"] = combatState.Energy;
            state["max_energy"] = combatState.MaxEnergy;

            // Stars (The Regent's resource, conditionally shown)
            if (player.Character.ShouldAlwaysShowStarCounter || combatState.Stars > 0)
            {
                state["stars"] = combatState.Stars;
            }

            // Hand
            var hand = new List<Dictionary<string, object?>>();
            int cardIndex = 0;
            foreach (var card in combatState.Hand.Cards)
            {
                hand.Add(BuildCardState(card, cardIndex));
                cardIndex++;
            }
            state["hand"] = hand;

            // Pile counts
            state["draw_pile_count"] = combatState.DrawPile.Cards.Count;
            state["discard_pile_count"] = combatState.DiscardPile.Cards.Count;
            state["exhaust_pile_count"] = combatState.ExhaustPile.Cards.Count;

            // Pile contents
            state["draw_pile"] = BuildPileCardList(combatState.DrawPile.Cards, PileType.Draw);
            state["discard_pile"] = BuildPileCardList(combatState.DiscardPile.Cards, PileType.Discard);
            state["exhaust_pile"] = BuildPileCardList(combatState.ExhaustPile.Cards, PileType.Exhaust);

            // Orbs
            if (combatState.OrbQueue.Capacity > 0)
            {
                var orbs = new List<Dictionary<string, object?>>();
                foreach (var orb in combatState.OrbQueue.Orbs)
                {
                    // Populate SmartDescription placeholders with Focus-modified values,
                    // mirroring OrbModel.HoverTips getter (OrbModel.cs:92-94)
                    string? description = SafeGetText(() =>
                    {
                        var desc = orb.SmartDescription;
                        desc.Add("energyPrefix", orb.Owner.Character.CardPool.Title);
                        desc.Add("Passive", orb.PassiveVal);
                        desc.Add("Evoke", orb.EvokeVal);
                        return desc;
                    });
                    orbs.Add(new Dictionary<string, object?>
                    {
                        ["id"] = orb.Id.Entry,
                        ["name"] = SafeGetText(() => orb.Title),
                        ["description"] = description,
                        ["passive_val"] = orb.PassiveVal,
                        ["evoke_val"] = orb.EvokeVal,
                        ["keywords"] = BuildHoverTips(orb.HoverTips)
                    });
                }
                state["orbs"] = orbs;
                state["orb_slots"] = combatState.OrbQueue.Capacity;
                state["orb_empty_slots"] = combatState.OrbQueue.Capacity - combatState.OrbQueue.Orbs.Count;
            }
        }

        state["gold"] = player.Gold;

        // Powers (status effects)
        state["status"] = BuildPowersState(creature);

        // Relics
        var relics = new List<Dictionary<string, object?>>();
        foreach (var relic in player.Relics)
        {
            relics.Add(new Dictionary<string, object?>
            {
                ["id"] = relic.Id.Entry,
                ["name"] = SafeGetText(() => relic.Title),
                ["description"] = SafeGetText(() => relic.DynamicDescription),
                ["counter"] = relic.ShowCounter ? relic.DisplayAmount : null,
                ["keywords"] = BuildHoverTips(relic.HoverTipsExcludingRelic)
            });
        }
        state["relics"] = relics;

        // Potions
        var potions = new List<Dictionary<string, object?>>();
        int slotIndex = 0;
        foreach (var potion in player.PotionSlots)
        {
            if (potion != null)
            {
                potions.Add(new Dictionary<string, object?>
                {
                    ["id"] = potion.Id.Entry,
                    ["name"] = SafeGetText(() => potion.Title),
                    ["description"] = SafeGetText(() => potion.DynamicDescription),
                    ["slot"] = slotIndex,
                    ["can_use_in_combat"] = potion.Usage == PotionUsage.CombatOnly || potion.Usage == PotionUsage.AnyTime,
                    ["target_type"] = potion.TargetType.ToString(),
                    ["keywords"] = BuildHoverTips(potion.ExtraHoverTips)
                });
            }
            slotIndex++;
        }
        state["potions"] = potions;

        return state;
    }

    private static Dictionary<string, object?> BuildCardState(CardModel card, int index)
    {
        string costDisplay;
        if (card.EnergyCost.CostsX)
            costDisplay = "X";
        else
        {
            int cost = card.EnergyCost.GetAmountToSpend();
            costDisplay = cost.ToString();
        }

        card.CanPlay(out var unplayableReason, out _);

        // Star cost (The Regent's cards; CanonicalStarCost >= 0 means card has a star cost)
        string? starCostDisplay = null;
        if (card.HasStarCostX)
            starCostDisplay = "X";
        else if (card.CurrentStarCost >= 0)
            starCostDisplay = card.GetStarCostWithModifiers().ToString();

        return new Dictionary<string, object?>
        {
            ["index"] = index,
            ["id"] = card.Id.Entry,
            ["name"] = card.Title,
            ["type"] = card.Type.ToString(),
            ["cost"] = costDisplay,
            ["star_cost"] = starCostDisplay,
            ["description"] = SafeGetCardDescription(card),
            ["target_type"] = card.TargetType.ToString(),
            ["can_play"] = unplayableReason == UnplayableReason.None,
            ["unplayable_reason"] = unplayableReason != UnplayableReason.None ? unplayableReason.ToString() : null,
            ["is_upgraded"] = card.IsUpgraded,
            ["keywords"] = BuildHoverTips(card.HoverTips)
        };
    }

    private static List<Dictionary<string, object?>> BuildPileCardList(IEnumerable<CardModel> cards, PileType pile)
    {
        var list = new List<Dictionary<string, object?>>();
        foreach (var card in cards)
        {
            list.Add(new Dictionary<string, object?>
            {
                ["name"] = SafeGetText(() => card.Title),
                ["description"] = SafeGetCardDescription(card, pile)
            });
        }
        return list;
    }

    private static Dictionary<string, object?> BuildEnemyState(Creature creature, Dictionary<string, int> entityCounts)
    {
        var monster = creature.Monster;
        string baseId = monster?.Id.Entry ?? "unknown";

        // Generate entity_id like "jaw_worm_0"
        if (!entityCounts.TryGetValue(baseId, out int count))
            count = 0;
        entityCounts[baseId] = count + 1;
        string entityId = $"{baseId}_{count}";

        var state = new Dictionary<string, object?>
        {
            ["entity_id"] = entityId,
            ["combat_id"] = creature.CombatId,
            ["name"] = SafeGetText(() => monster?.Title),
            ["hp"] = creature.CurrentHp,
            ["max_hp"] = creature.MaxHp,
            ["block"] = creature.Block,
            ["status"] = BuildPowersState(creature)
        };

        // Intents
        if (monster?.NextMove is MoveState moveState)
        {
            var intents = new List<Dictionary<string, object?>>();
            foreach (var intent in moveState.Intents)
            {
                var intentData = new Dictionary<string, object?>
                {
                    ["type"] = intent.IntentType.ToString()
                };
                try
                {
                    var targets = creature.CombatState?.PlayerCreatures;
                    if (targets != null)
                    {
                        string label = intent.GetIntentLabel(targets, creature).GetFormattedText();
                        intentData["label"] = StripRichTextTags(label);

                        var hoverTip = intent.GetHoverTip(targets, creature);
                        if (hoverTip.Title != null)
                            intentData["title"] = StripRichTextTags(hoverTip.Title);
                        if (hoverTip.Description != null)
                            intentData["description"] = StripRichTextTags(hoverTip.Description);
                    }
                }
                catch { /* intent label may fail for some types */ }
                intents.Add(intentData);
            }
            state["intents"] = intents;
        }

        return state;
    }

    private static Dictionary<string, object?> BuildEventState(EventRoom eventRoom, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold
            };
        }

        var eventModel = eventRoom.CanonicalEvent;
        bool isAncient = eventModel is AncientEventModel;
        state["event_id"] = eventModel.Id.Entry;
        state["event_name"] = SafeGetText(() => eventModel.Title);
        state["is_ancient"] = isAncient;

        // Check dialogue state for ancients
        bool inDialogue = false;
        var uiRoom = NEventRoom.Instance;
        if (isAncient && uiRoom != null)
        {
            var ancientLayout = FindFirst<NAncientEventLayout>(uiRoom);
            if (ancientLayout != null)
            {
                var hitbox = ancientLayout.GetNodeOrNull<NClickableControl>("%DialogueHitbox");
                inDialogue = hitbox != null && hitbox.Visible && hitbox.IsEnabled;
            }
        }
        state["in_dialogue"] = inDialogue;

        // Event body text
        state["body"] = SafeGetText(() => eventModel.Description);

        // Options from UI
        var options = new List<Dictionary<string, object?>>();
        if (uiRoom != null)
        {
            var buttons = FindAll<NEventOptionButton>(uiRoom);
            int index = 0;
            foreach (var button in buttons)
            {
                var opt = button.Option;
                var optData = new Dictionary<string, object?>
                {
                    ["index"] = index,
                    ["title"] = SafeGetText(() => opt.Title),
                    ["description"] = SafeGetText(() => opt.Description),
                    ["is_locked"] = opt.IsLocked,
                    ["is_proceed"] = opt.IsProceed,
                    ["was_chosen"] = opt.WasChosen
                };
                if (opt.Relic != null)
                {
                    optData["relic_name"] = SafeGetText(() => opt.Relic.Title);
                    optData["relic_description"] = SafeGetText(() => opt.Relic.DynamicDescription);
                }
                optData["keywords"] = BuildHoverTips(opt.HoverTips);
                options.Add(optData);
                index++;
            }
        }
        state["options"] = options;

        return state;
    }

    private static Dictionary<string, object?> BuildRestSiteState(RestSiteRoom restSiteRoom, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold
            };
        }

        var options = new List<Dictionary<string, object?>>();
        int index = 0;
        foreach (var opt in restSiteRoom.Options)
        {
            options.Add(new Dictionary<string, object?>
            {
                ["index"] = index,
                ["id"] = opt.OptionId,
                ["name"] = SafeGetText(() => opt.Title),
                ["description"] = SafeGetText(() => opt.Description),
                ["is_enabled"] = opt.IsEnabled
            });
            index++;
        }
        state["options"] = options;

        var proceedButton = NRestSiteRoom.Instance?.ProceedButton;
        state["can_proceed"] = proceedButton?.IsEnabled ?? false;

        return state;
    }

    private static Dictionary<string, object?> BuildShopState(MerchantRoom merchantRoom, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold,
                ["potion_slots"] = player.PotionSlots.Count,
                ["open_potion_slots"] = player.PotionSlots.Count(s => s == null)
            };
        }

        var inventory = merchantRoom.Inventory;
        var items = new List<Dictionary<string, object?>>();
        int index = 0;

        // Cards
        foreach (var entry in inventory.CardEntries)
        {
            var item = new Dictionary<string, object?>
            {
                ["index"] = index,
                ["category"] = "card",
                ["cost"] = entry.Cost,
                ["is_stocked"] = entry.IsStocked,
                ["can_afford"] = entry.EnoughGold,
                ["on_sale"] = entry.IsOnSale
            };
            if (entry.CreationResult?.Card is { } card)
            {
                item["card_id"] = card.Id.Entry;
                item["card_name"] = SafeGetText(() => card.Title);
                item["card_type"] = card.Type.ToString();
                item["card_rarity"] = card.Rarity.ToString();
                item["card_description"] = SafeGetCardDescription(card, PileType.None);
                item["keywords"] = BuildHoverTips(card.HoverTips);
            }
            items.Add(item);
            index++;
        }

        // Relics
        foreach (var entry in inventory.RelicEntries)
        {
            var item = new Dictionary<string, object?>
            {
                ["index"] = index,
                ["category"] = "relic",
                ["cost"] = entry.Cost,
                ["is_stocked"] = entry.IsStocked,
                ["can_afford"] = entry.EnoughGold
            };
            if (entry.Model is { } relic)
            {
                item["relic_id"] = relic.Id.Entry;
                item["relic_name"] = SafeGetText(() => relic.Title);
                item["relic_description"] = SafeGetText(() => relic.DynamicDescription);
                item["keywords"] = BuildHoverTips(relic.HoverTipsExcludingRelic);
            }
            items.Add(item);
            index++;
        }

        // Potions
        foreach (var entry in inventory.PotionEntries)
        {
            var item = new Dictionary<string, object?>
            {
                ["index"] = index,
                ["category"] = "potion",
                ["cost"] = entry.Cost,
                ["is_stocked"] = entry.IsStocked,
                ["can_afford"] = entry.EnoughGold
            };
            if (entry.Model is { } potion)
            {
                item["potion_id"] = potion.Id.Entry;
                item["potion_name"] = SafeGetText(() => potion.Title);
                item["potion_description"] = SafeGetText(() => potion.DynamicDescription);
                item["keywords"] = BuildHoverTips(potion.ExtraHoverTips);
            }
            items.Add(item);
            index++;
        }

        // Card removal
        if (inventory.CardRemovalEntry is { } removal)
        {
            items.Add(new Dictionary<string, object?>
            {
                ["index"] = index,
                ["category"] = "card_removal",
                ["cost"] = removal.Cost,
                ["is_stocked"] = removal.IsStocked,
                ["can_afford"] = removal.EnoughGold
            });
        }

        state["items"] = items;

        var proceedButton = NMerchantRoom.Instance?.ProceedButton;
        state["can_proceed"] = proceedButton?.IsEnabled ?? false;

        return state;
    }

    private static Dictionary<string, object?> BuildMapState(RunState runState)
    {
        var state = new Dictionary<string, object?>();

        // Player summary
        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            int totalSlots = player.PotionSlots.Count;
            int openSlots = player.PotionSlots.Count(s => s == null);
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold,
                ["potion_slots"] = totalSlots,
                ["open_potion_slots"] = openSlots
            };
        }

        var map = runState.Map;
        var visitedCoords = runState.VisitedMapCoords;

        // Current position
        if (visitedCoords.Count > 0)
        {
            var cur = visitedCoords[visitedCoords.Count - 1];
            state["current_position"] = new Dictionary<string, object?>
            {
                ["col"] = cur.col, ["row"] = cur.row,
                ["type"] = map.GetPoint(cur)?.PointType.ToString()
            };
        }

        // Visited path
        var visited = new List<Dictionary<string, object?>>();
        foreach (var coord in visitedCoords)
        {
            visited.Add(new Dictionary<string, object?>
            {
                ["col"] = coord.col, ["row"] = coord.row,
                ["type"] = map.GetPoint(coord)?.PointType.ToString()
            });
        }
        state["visited"] = visited;

        // Next options — read travelable state from UI nodes
        var nextOptions = new List<Dictionary<string, object?>>();
        var mapScreen = NMapScreen.Instance;
        if (mapScreen != null)
        {
            var travelable = FindAll<NMapPoint>(mapScreen)
                .Where(mp => mp.State == MapPointState.Travelable)
                .OrderBy(mp => mp.Point.coord.col)
                .ToList();

            int index = 0;
            foreach (var nmp in travelable)
            {
                var pt = nmp.Point;
                var option = new Dictionary<string, object?>
                {
                    ["index"] = index,
                    ["col"] = pt.coord.col,
                    ["row"] = pt.coord.row,
                    ["type"] = pt.PointType.ToString()
                };

                // 1-level lookahead
                var children = pt.Children
                    .OrderBy(c => c.coord.col)
                    .Select(c => new Dictionary<string, object?>
                    {
                        ["col"] = c.coord.col, ["row"] = c.coord.row,
                        ["type"] = c.PointType.ToString()
                    }).ToList();
                if (children.Count > 0)
                    option["leads_to"] = children;

                nextOptions.Add(option);
                index++;
            }
        }
        state["next_options"] = nextOptions;

        // Full map — all nodes organized for planning
        var nodes = new List<Dictionary<string, object?>>();

        // Starting point
        var start = map.StartingMapPoint;
        nodes.Add(BuildMapNode(start));

        // Grid nodes
        foreach (var pt in map.GetAllMapPoints())
            nodes.Add(BuildMapNode(pt));

        // Boss
        nodes.Add(BuildMapNode(map.BossMapPoint));
        if (map.SecondBossMapPoint != null)
            nodes.Add(BuildMapNode(map.SecondBossMapPoint));

        state["nodes"] = nodes;
        state["boss"] = new Dictionary<string, object?>
        {
            ["col"] = map.BossMapPoint.coord.col,
            ["row"] = map.BossMapPoint.coord.row
        };

        return state;
    }

    private static Dictionary<string, object?> BuildMapNode(MapPoint pt)
    {
        return new Dictionary<string, object?>
        {
            ["col"] = pt.coord.col,
            ["row"] = pt.coord.row,
            ["type"] = pt.PointType.ToString(),
            ["children"] = pt.Children
                .OrderBy(c => c.coord.col)
                .Select(c => new List<int> { c.coord.col, c.coord.row })
                .ToList()
        };
    }

    private static Dictionary<string, object?> BuildRewardsState(NRewardsScreen rewardsScreen, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        // Player summary for decision-making context
        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            int totalSlots = player.PotionSlots.Count;
            int openSlots = player.PotionSlots.Count(s => s == null);
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold,
                ["potion_slots"] = totalSlots,
                ["open_potion_slots"] = openSlots
            };
        }

        // Reward items
        var rewardButtons = FindAll<NRewardButton>(rewardsScreen);
        var items = new List<Dictionary<string, object?>>();
        int index = 0;
        foreach (var button in rewardButtons)
        {
            if (button.Reward == null || !button.IsEnabled) continue;
            var reward = button.Reward;

            var item = new Dictionary<string, object?>
            {
                ["index"] = index,
                ["type"] = GetRewardTypeName(reward),
                ["description"] = SafeGetText(() => reward.Description)
            };

            // Type-specific details
            if (reward is GoldReward goldReward)
                item["gold_amount"] = goldReward.Amount;
            else if (reward is PotionReward potionReward && potionReward.Potion != null)
            {
                item["potion_id"] = potionReward.Potion.Id.Entry;
                item["potion_name"] = SafeGetText(() => potionReward.Potion.Title);
            }

            items.Add(item);
            index++;
        }
        state["items"] = items;

        // Proceed button
        var proceedButton = FindFirst<NProceedButton>(rewardsScreen);
        state["can_proceed"] = proceedButton?.IsEnabled ?? false;

        return state;
    }

    private static Dictionary<string, object?> BuildCardRewardState(NCardRewardSelectionScreen cardScreen)
    {
        var state = new Dictionary<string, object?>();

        var cardHolders = FindAllSortedByPosition<NCardHolder>(cardScreen);
        var cards = new List<Dictionary<string, object?>>();
        int index = 0;
        foreach (var holder in cardHolders)
        {
            var card = holder.CardModel;
            if (card == null) continue;

            string costDisplay = card.EnergyCost.CostsX
                ? "X"
                : card.EnergyCost.GetAmountToSpend().ToString();

            string? starCostDisplay = null;
            if (card.HasStarCostX)
                starCostDisplay = "X";
            else if (card.CurrentStarCost >= 0)
                starCostDisplay = card.GetStarCostWithModifiers().ToString();

            cards.Add(new Dictionary<string, object?>
            {
                ["index"] = index,
                ["id"] = card.Id.Entry,
                ["name"] = SafeGetText(() => card.Title),
                ["type"] = card.Type.ToString(),
                ["cost"] = costDisplay,
                ["star_cost"] = starCostDisplay,
                ["description"] = SafeGetCardDescription(card, PileType.None),
                ["rarity"] = card.Rarity.ToString(),
                ["is_upgraded"] = card.IsUpgraded,
                ["keywords"] = BuildHoverTips(card.HoverTips)
            });
            index++;
        }
        state["cards"] = cards;

        var altButtons = FindAll<NCardRewardAlternativeButton>(cardScreen);
        state["can_skip"] = altButtons.Count > 0;

        return state;
    }

    private static Dictionary<string, object?> BuildCardSelectState(NCardGridSelectionScreen screen, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        // Screen type
        state["screen_type"] = screen switch
        {
            NDeckTransformSelectScreen => "transform",
            NDeckUpgradeSelectScreen => "upgrade",
            NDeckCardSelectScreen => "select",
            NSimpleCardSelectScreen => "simple_select",
            _ => screen.GetType().Name
        };

        // Player summary
        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold
            };
        }

        // Prompt text from UI label
        var bottomLabel = screen.GetNodeOrNull("%BottomLabel");
        if (bottomLabel != null)
        {
            var textVariant = bottomLabel.Get("text");
            string? prompt = textVariant.VariantType != Godot.Variant.Type.Nil ? StripRichTextTags(textVariant.AsString()) : null;
            state["prompt"] = prompt;
        }

        // Cards in the grid (sorted by visual position — MoveToFront can reorder children)
        var cardHolders = FindAllSortedByPosition<NGridCardHolder>(screen);
        var cards = new List<Dictionary<string, object?>>();
        int index = 0;
        foreach (var holder in cardHolders)
        {
            var card = holder.CardModel;
            if (card == null) continue;

            cards.Add(new Dictionary<string, object?>
            {
                ["index"] = index,
                ["id"] = card.Id.Entry,
                ["name"] = SafeGetText(() => card.Title),
                ["type"] = card.Type.ToString(),
                ["cost"] = card.EnergyCost.CostsX ? "X" : card.EnergyCost.GetAmountToSpend().ToString(),
                ["description"] = SafeGetCardDescription(card, PileType.None),
                ["rarity"] = card.Rarity.ToString(),
                ["is_upgraded"] = card.IsUpgraded,
                ["keywords"] = BuildHoverTips(card.HoverTips)
            });
            index++;
        }
        state["cards"] = cards;

        // Preview container showing? (selection complete, awaiting confirm)
        // Upgrade screens use UpgradeSinglePreviewContainer / UpgradeMultiPreviewContainer
        var previewSingle = screen.GetNodeOrNull<Godot.Control>("%UpgradeSinglePreviewContainer");
        var previewMulti = screen.GetNodeOrNull<Godot.Control>("%UpgradeMultiPreviewContainer");
        var previewGeneric = screen.GetNodeOrNull<Godot.Control>("%PreviewContainer");
        bool previewShowing = (previewSingle?.Visible ?? false)
                            || (previewMulti?.Visible ?? false)
                            || (previewGeneric?.Visible ?? false);
        state["preview_showing"] = previewShowing;

        // Button states
        var closeButton = screen.GetNodeOrNull<NBackButton>("%Close");
        state["can_cancel"] = closeButton?.IsEnabled ?? false;

        // Confirm button — search all preview containers and main screen
        bool canConfirm = false;
        foreach (var container in new[] { previewSingle, previewMulti, previewGeneric })
        {
            if (container?.Visible == true)
            {
                var confirm = container.GetNodeOrNull<NConfirmButton>("Confirm")
                              ?? container.GetNodeOrNull<NConfirmButton>("%PreviewConfirm");
                if (confirm?.IsEnabled == true) { canConfirm = true; break; }
            }
        }
        if (!canConfirm)
        {
            var mainConfirm = screen.GetNodeOrNull<NConfirmButton>("Confirm")
                              ?? screen.GetNodeOrNull<NConfirmButton>("%Confirm");
            if (mainConfirm?.IsEnabled == true) canConfirm = true;
        }
        // Fallback: search entire screen tree for any enabled confirm button
        // (covers subclasses like NDeckEnchantSelectScreen)
        if (!canConfirm)
        {
            canConfirm = FindAll<NConfirmButton>(screen).Any(b => b.IsEnabled && b.IsVisibleInTree());
        }
        state["can_confirm"] = canConfirm;

        return state;
    }

    private static Dictionary<string, object?> BuildChooseCardState(NChooseACardSelectionScreen screen, RunState runState)
    {
        var state = new Dictionary<string, object?>();
        state["screen_type"] = "choose";

        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold
            };
        }

        state["prompt"] = "Choose a card.";

        var cardHolders = FindAllSortedByPosition<NGridCardHolder>(screen);
        var cards = new List<Dictionary<string, object?>>();
        int index = 0;
        foreach (var holder in cardHolders)
        {
            var card = holder.CardModel;
            if (card == null) continue;

            cards.Add(new Dictionary<string, object?>
            {
                ["index"] = index,
                ["id"] = card.Id.Entry,
                ["name"] = SafeGetText(() => card.Title),
                ["type"] = card.Type.ToString(),
                ["cost"] = card.EnergyCost.CostsX ? "X" : card.EnergyCost.GetAmountToSpend().ToString(),
                ["description"] = SafeGetCardDescription(card, PileType.None),
                ["rarity"] = card.Rarity.ToString(),
                ["is_upgraded"] = card.IsUpgraded,
                ["keywords"] = BuildHoverTips(card.HoverTips)
            });
            index++;
        }
        state["cards"] = cards;

        var skipButton = screen.GetNodeOrNull<NClickableControl>("SkipButton");
        state["can_skip"] = skipButton?.IsEnabled == true && skipButton.Visible;
        state["preview_showing"] = false;
        state["can_confirm"] = false;
        state["can_cancel"] = state["can_skip"];

        return state;
    }

    private static Dictionary<string, object?> BuildHandSelectState(NPlayerHand hand, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        // Mode
        state["mode"] = hand.CurrentMode switch
        {
            NPlayerHand.Mode.SimpleSelect => "simple_select",
            NPlayerHand.Mode.UpgradeSelect => "upgrade_select",
            _ => hand.CurrentMode.ToString()
        };

        // Prompt text from %SelectionHeader
        var headerLabel = hand.GetNodeOrNull<Godot.Control>("%SelectionHeader");
        if (headerLabel != null)
        {
            var textVariant = headerLabel.Get("text");
            string? prompt = textVariant.VariantType != Godot.Variant.Type.Nil
                ? StripRichTextTags(textVariant.AsString())
                : null;
            state["prompt"] = prompt;
        }

        // Selectable cards (visible holders in the hand)
        var selectableCards = new List<Dictionary<string, object?>>();
        int index = 0;
        foreach (var holder in hand.ActiveHolders)
        {
            var card = holder.CardModel;
            if (card == null) continue;

            selectableCards.Add(new Dictionary<string, object?>
            {
                ["index"] = index,
                ["id"] = card.Id.Entry,
                ["name"] = SafeGetText(() => card.Title),
                ["type"] = card.Type.ToString(),
                ["cost"] = card.EnergyCost.CostsX ? "X" : card.EnergyCost.GetAmountToSpend().ToString(),
                ["description"] = SafeGetCardDescription(card),
                ["is_upgraded"] = card.IsUpgraded,
                ["keywords"] = BuildHoverTips(card.HoverTips)
            });
            index++;
        }
        state["cards"] = selectableCards;

        // Already-selected cards (in the SelectedHandCardContainer)
        var selectedContainer = hand.GetNodeOrNull<Godot.Control>("%SelectedHandCardContainer");
        if (selectedContainer != null)
        {
            var selectedCards = new List<Dictionary<string, object?>>();
            var selectedHolders = FindAll<NSelectedHandCardHolder>(selectedContainer);
            int selIdx = 0;
            foreach (var holder in selectedHolders)
            {
                var card = holder.CardModel;
                if (card == null) continue;
                selectedCards.Add(new Dictionary<string, object?>
                {
                    ["index"] = selIdx,
                    ["name"] = SafeGetText(() => card.Title)
                });
                selIdx++;
            }
            if (selectedCards.Count > 0)
                state["selected_cards"] = selectedCards;
        }

        // Confirm button state
        var confirmBtn = hand.GetNodeOrNull<NConfirmButton>("%SelectModeConfirmButton");
        state["can_confirm"] = confirmBtn?.IsEnabled ?? false;

        return state;
    }

    private static Dictionary<string, object?> BuildRelicSelectState(NChooseARelicSelection screen, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold
            };
        }

        state["prompt"] = "Choose a relic.";

        var relicHolders = FindAll<NRelicBasicHolder>(screen);
        var relics = new List<Dictionary<string, object?>>();
        int index = 0;
        foreach (var holder in relicHolders)
        {
            var relic = holder.Relic?.Model;
            if (relic == null) continue;

            relics.Add(new Dictionary<string, object?>
            {
                ["index"] = index,
                ["id"] = relic.Id.Entry,
                ["name"] = SafeGetText(() => relic.Title),
                ["description"] = SafeGetText(() => relic.DynamicDescription),
                ["keywords"] = BuildHoverTips(relic.HoverTipsExcludingRelic)
            });
            index++;
        }
        state["relics"] = relics;

        var skipButton = screen.GetNodeOrNull<NClickableControl>("SkipButton");
        state["can_skip"] = skipButton?.IsEnabled == true && skipButton.Visible;

        return state;
    }

    private static Dictionary<string, object?> BuildTreasureState(TreasureRoom treasureRoom, RunState runState)
    {
        var state = new Dictionary<string, object?>();

        var player = LocalContext.GetMe(runState);
        if (player != null)
        {
            state["player"] = new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold
            };
        }

        var treasureUI = FindFirst<NTreasureRoom>(
            ((Godot.SceneTree)Godot.Engine.GetMainLoop()).Root);

        if (treasureUI == null)
        {
            state["message"] = "Treasure room loading...";
            return state;
        }

        // Auto-open chest if not yet opened
        var chestButton = treasureUI.GetNodeOrNull<NClickableControl>("Chest");
        if (chestButton is { IsEnabled: true })
        {
            chestButton.ForceClick();
            state["message"] = "Opening chest...";
            return state;
        }

        // Show relics available for picking
        var relicCollection = treasureUI.GetNodeOrNull<NTreasureRoomRelicCollection>("%RelicCollection");
        if (relicCollection?.Visible == true)
        {
            var holders = FindAll<NTreasureRoomRelicHolder>(relicCollection)
                .Where(h => h.IsEnabled && h.Visible)
                .ToList();

            var relics = new List<Dictionary<string, object?>>();
            int index = 0;
            foreach (var holder in holders)
            {
                var relic = holder.Relic?.Model;
                if (relic == null) continue;
                relics.Add(new Dictionary<string, object?>
                {
                    ["index"] = index,
                    ["id"] = relic.Id.Entry,
                    ["name"] = SafeGetText(() => relic.Title),
                    ["description"] = SafeGetText(() => relic.DynamicDescription),
                    ["rarity"] = relic.Rarity.ToString(),
                    ["keywords"] = BuildHoverTips(relic.HoverTipsExcludingRelic)
                });
                index++;
            }
            state["relics"] = relics;
        }

        state["can_proceed"] = treasureUI.ProceedButton?.IsEnabled ?? false;

        return state;
    }

    private static string GetRewardTypeName(Reward reward) => reward switch
    {
        GoldReward => "gold",
        PotionReward => "potion",
        RelicReward => "relic",
        CardReward => "card",
        SpecialCardReward => "special_card",
        CardRemovalReward => "card_removal",
        _ => reward.GetType().Name.ToLower()
    };

    private static List<Dictionary<string, object?>> BuildPowersState(Creature creature)
    {
        var powers = new List<Dictionary<string, object?>>();
        foreach (var power in creature.Powers)
        {
            if (!power.IsVisible) continue;

            // HoverTips resolves all dynamic vars (Amount, DynamicVars, etc.)
            // The first tip is the power's own description; the rest are extra keywords
            var allTips = power.HoverTips.ToList();
            string? resolvedDesc = null;
            var extraTips = new List<IHoverTip>();
            foreach (var tip in allTips)
            {
                if (tip.Id == power.Id.ToString())
                {
                    // This is the power's own hover tip — extract its resolved description
                    if (tip is HoverTip ht)
                        resolvedDesc = StripRichTextTags(ht.Description);
                }
                else
                {
                    extraTips.Add(tip);
                }
            }
            // Fallback to raw SmartDescription if HoverTips extraction failed
            resolvedDesc ??= SafeGetText(() => power.SmartDescription);

            powers.Add(new Dictionary<string, object?>
            {
                ["id"] = power.Id.Entry,
                ["name"] = SafeGetText(() => power.Title),
                ["amount"] = power.DisplayAmount,
                ["type"] = power.Type.ToString(),
                ["description"] = resolvedDesc,
                ["keywords"] = BuildHoverTips(extraTips)
            });
        }
        return powers;
    }
}
