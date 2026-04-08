using System;
using System.Collections.Generic;
using System.Linq;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Events;
using MegaCrit.Sts2.Core.Nodes.GodotExtensions;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Nodes.Screens;
using MegaCrit.Sts2.Core.Nodes.Screens.CardSelection;
using MegaCrit.Sts2.Core.Nodes.Screens.Map;
using MegaCrit.Sts2.Core.Nodes.Screens.Overlays;
using MegaCrit.Sts2.Core.Nodes.Screens.TreasureRoomRelic;
using MegaCrit.Sts2.Core.Rooms;
using MegaCrit.Sts2.Core.Runs;

namespace STS2_Bridge;

public static partial class BridgeMod
{
    private static Dictionary<string, object?> BuildMultiplayerGameState()
    {
        var result = new Dictionary<string, object?>();

        if (!RunManager.Instance.IsInProgress)
        {
            result["state_type"] = "menu";
            result["message"] = "No run in progress. Player is in the main menu.";
            return result;
        }

        var runState = RunManager.Instance.DebugOnlyGetState();
        if (runState == null)
        {
            result["state_type"] = "unknown";
            return result;
        }

        if (!RunManager.Instance.NetService.Type.IsMultiplayer())
        {
            result["state_type"] = "error";
            result["message"] = "Not in a multiplayer run. Use /api/v1/singleplayer instead.";
            return result;
        }

        // Multiplayer metadata
        result["game_mode"] = "multiplayer";
        result["net_type"] = RunManager.Instance.NetService.Type.ToString();
        result["player_count"] = runState.Players.Count;
        var localPlayer = LocalContext.GetMe(runState);
        if (localPlayer != null)
        {
            for (int i = 0; i < runState.Players.Count; i++)
            {
                if (runState.Players[i] == localPlayer)
                {
                    result["local_player_slot"] = i;
                    break;
                }
            }
        }

        // Same overlay-first detection logic as singleplayer
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
        else if (topOverlay is IOverlayScreen
                 && topOverlay is not NRewardsScreen
                 && topOverlay is not NCardRewardSelectionScreen)
        {
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
                var playerHand = NPlayerHand.Instance;
                if (playerHand != null && playerHand.IsInCardSelection)
                {
                    result["state_type"] = "hand_select";
                    result["hand_select"] = BuildHandSelectState(playerHand, runState);
                    result["battle"] = BuildMultiplayerBattleState(runState, combatRoom);
                }
                else
                {
                    result["state_type"] = combatRoom.RoomType.ToString().ToLower();
                    result["battle"] = BuildMultiplayerBattleState(runState, combatRoom);
                }
            }
            else
            {
                if (NMapScreen.Instance is { IsOpen: true })
                {
                    result["state_type"] = "map";
                    result["map"] = BuildMultiplayerMapState(runState);
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
                result["map"] = BuildMultiplayerMapState(runState);
            }
            else
            {
                result["state_type"] = "event";
                result["event"] = BuildMultiplayerEventState(eventRoom, runState);
            }
        }
        else if (currentRoom is MapRoom)
        {
            result["state_type"] = "map";
            result["map"] = BuildMultiplayerMapState(runState);
        }
        else if (currentRoom is MerchantRoom merchantRoom)
        {
            if (NMapScreen.Instance is { IsOpen: true })
            {
                result["state_type"] = "map";
                result["map"] = BuildMultiplayerMapState(runState);
            }
            else
            {
                var merchUI = NMerchantRoom.Instance;
                if (merchUI != null && !merchUI.Inventory.IsOpen)
                    merchUI.OpenInventory();

                result["state_type"] = "shop";
                result["shop"] = BuildShopState(merchantRoom, runState);
            }
        }
        else if (currentRoom is RestSiteRoom restSiteRoom)
        {
            if (NMapScreen.Instance is { IsOpen: true })
            {
                result["state_type"] = "map";
                result["map"] = BuildMultiplayerMapState(runState);
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
                result["map"] = BuildMultiplayerMapState(runState);
            }
            else
            {
                result["state_type"] = "treasure";
                result["treasure"] = BuildMultiplayerTreasureState(treasureRoom, runState);
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

        // All players summary (always included for multiplayer)
        result["players"] = BuildAllPlayersState(runState);

        return result;
    }

    private static Dictionary<string, object?> BuildMultiplayerBattleState(RunState runState, CombatRoom combatRoom)
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
        battle["all_players_ready"] = CombatManager.Instance.AllPlayersReadyToEndTurn();

        // All players in combat — full state for local player, summary for others
        var players = new List<Dictionary<string, object?>>();
        Dictionary<string, object?>? localPlayerState = null;
        foreach (var player in runState.Players)
        {
            bool isLocal = LocalContext.IsMe(player);
            // Full hand/piles/orbs only for local player; others get summary only
            var playerState = isLocal ? BuildPlayerState(player) : BuildPlayerStateSummary(player);
            playerState["is_local"] = isLocal;
            playerState["is_alive"] = player.Creature.IsAlive;
            playerState["is_ready_to_end_turn"] = CombatManager.Instance.IsPlayerReadyToEndTurn(player);
            players.Add(playerState);
            if (isLocal)
                localPlayerState = playerState;
        }
        battle["players"] = players;

        // Local player shortcut (same dict as the is_local=true entry in players)
        if (localPlayerState != null)
            battle["player"] = localPlayerState;

        // Enemies
        var enemies = new List<Dictionary<string, object?>>();
        var entityCounts = new Dictionary<string, int>();
        foreach (var creature in combatState.Enemies)
        {
            if (creature.IsAlive)
                enemies.Add(BuildEnemyState(creature, entityCounts));
        }
        battle["enemies"] = enemies;

        return battle;
    }

    private static Dictionary<string, object?> BuildMultiplayerMapState(RunState runState)
    {
        // Start with the standard map state
        var state = BuildMapState(runState);

        // Add per-player vote data
        try
        {
            var mapSync = RunManager.Instance.MapSelectionSynchronizer;
            var votes = new List<Dictionary<string, object?>>();

            foreach (var player in runState.Players)
            {
                var vote = mapSync.GetVote(player);
                votes.Add(new Dictionary<string, object?>
                {
                    ["player"] = SafeGetText(() => player.Character.Title),
                    ["is_local"] = LocalContext.IsMe(player),
                    ["voted"] = vote != null,
                    ["vote_col"] = vote?.coord.col,
                    ["vote_row"] = vote?.coord.row
                });
            }

            state["votes"] = votes;
            state["all_voted"] = votes.All(v => v["voted"] is true);
        }
        catch
        {
            // MapSelectionSynchronizer may not be available in all contexts
        }

        // All players summary
        state["players"] = BuildAllPlayersState(runState);

        return state;
    }

    private static Dictionary<string, object?> BuildMultiplayerEventState(EventRoom eventRoom, RunState runState)
    {
        // Start with the standard event state
        var state = BuildEventState(eventRoom, runState);

        // Add multiplayer-specific event data
        try
        {
            var eventSync = RunManager.Instance.EventSynchronizer;
            bool isShared = false;
            try { isShared = eventSync.IsShared; } catch { /* throws if no event in progress */ }
            state["is_shared"] = isShared;

            if (isShared)
            {
                var votes = new List<Dictionary<string, object?>>();
                foreach (var player in runState.Players)
                {
                    var vote = eventSync.GetPlayerVote(player);
                    votes.Add(new Dictionary<string, object?>
                    {
                        ["player"] = SafeGetText(() => player.Character.Title),
                        ["is_local"] = LocalContext.IsMe(player),
                        ["voted"] = vote != null,
                        ["vote_option"] = vote
                    });
                }
                state["votes"] = votes;
                state["all_voted"] = votes.All(v => v["voted"] is true);
            }
        }
        catch
        {
            // EventSynchronizer may not be available
        }

        // All players summary
        state["players"] = BuildAllPlayersState(runState);

        return state;
    }

    private static Dictionary<string, object?> BuildMultiplayerTreasureState(TreasureRoom treasureRoom, RunState runState)
    {
        // Auto-open chest same as singleplayer. BeginRelicPicking() runs during
        // TreasureRoom.Enter(), so relics are already generated. The chest click
        // just triggers the UI animation + gold via OneOffSynchronizer — same path
        // as a human click or the game's own AutoSlay handler.
        var state = BuildTreasureState(treasureRoom, runState);

        // Add per-player bid data
        try
        {
            var treasureSync = RunManager.Instance.TreasureRoomRelicSynchronizer;
            var currentRelics = treasureSync.CurrentRelics;

            state["is_bidding_phase"] = currentRelics != null;

            if (currentRelics != null)
            {
                var bids = new List<Dictionary<string, object?>>();
                foreach (var player in runState.Players)
                {
                    var vote = treasureSync.GetPlayerVote(player);
                    bids.Add(new Dictionary<string, object?>
                    {
                        ["player"] = SafeGetText(() => player.Character.Title),
                        ["is_local"] = LocalContext.IsMe(player),
                        ["voted"] = vote != null,
                        ["vote_relic_index"] = vote
                    });
                }
                state["bids"] = bids;
                state["all_bid"] = bids.All(b => b["voted"] is true);
            }
        }
        catch
        {
            // TreasureRoomRelicSynchronizer may not be available
        }

        // All players summary
        state["players"] = BuildAllPlayersState(runState);

        return state;
    }

    /// <summary>
    /// Builds player combat state without private info (hand, draw/discard/exhaust piles, orbs).
    /// Used for non-local players in multiplayer — shows HP, block, energy, powers, relics, potions.
    /// </summary>
    private static Dictionary<string, object?> BuildPlayerStateSummary(Player player)
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

            if (player.Character.ShouldAlwaysShowStarCounter || combatState.Stars > 0)
                state["stars"] = combatState.Stars;
        }

        state["gold"] = player.Gold;
        state["status"] = BuildPowersState(creature);

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
                    ["slot"] = slotIndex
                });
            }
            slotIndex++;
        }
        state["potions"] = potions;

        return state;
    }

    private static List<Dictionary<string, object?>> BuildAllPlayersState(RunState runState)
    {
        var players = new List<Dictionary<string, object?>>();
        foreach (var player in runState.Players)
        {
            players.Add(new Dictionary<string, object?>
            {
                ["character"] = SafeGetText(() => player.Character.Title),
                ["is_local"] = LocalContext.IsMe(player),
                ["hp"] = player.Creature.CurrentHp,
                ["max_hp"] = player.Creature.MaxHp,
                ["gold"] = player.Gold,
                ["is_alive"] = player.Creature.IsAlive
            });
        }
        return players;
    }
}
