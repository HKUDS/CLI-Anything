using System.Collections.Generic;
using System.Text.Json;
using MegaCrit.Sts2.Core.Combat;
using MegaCrit.Sts2.Core.Context;
using MegaCrit.Sts2.Core.Entities.Players;
using MegaCrit.Sts2.Core.GameActions;
using MegaCrit.Sts2.Core.Multiplayer.Game;
using MegaCrit.Sts2.Core.Nodes.Combat;
using MegaCrit.Sts2.Core.Nodes.Rooms;
using MegaCrit.Sts2.Core.Runs;

namespace STS2_Bridge;

public static partial class BridgeMod
{
    private static Dictionary<string, object?> ExecuteMultiplayerAction(string action, Dictionary<string, JsonElement> data)
    {
        if (!RunManager.Instance.IsInProgress)
            return Error("No run in progress");

        if (!RunManager.Instance.NetService.Type.IsMultiplayer())
            return Error("Not in a multiplayer run. Use /api/v1/singleplayer instead.");

        var runState = RunManager.Instance.DebugOnlyGetState()!;
        var player = LocalContext.GetMe(runState);
        if (player == null)
            return Error("Could not find local player");

        return action switch
        {
            // Delegated to existing sync-safe handlers
            "play_card" => ExecutePlayCard(player, data),
            "use_potion" => ExecuteUsePotion(player, data),
            "choose_map_node" => ExecuteChooseMapNode(data),
            "choose_event_option" => ExecuteChooseEventOption(data),
            "advance_dialogue" => ExecuteAdvanceDialogue(),
            "choose_rest_option" => ExecuteChooseRestOption(data),
            "shop_purchase" => ExecuteShopPurchase(player, data),
            "claim_reward" => ExecuteClaimReward(data),
            "select_card_reward" => ExecuteSelectCardReward(data),
            "skip_card_reward" => ExecuteSkipCardReward(),
            "proceed" => ExecuteProceed(),
            "select_card" => ExecuteSelectCard(data),
            "confirm_selection" => ExecuteConfirmSelection(),
            "cancel_selection" => ExecuteCancelSelection(),
            "combat_select_card" => ExecuteCombatSelectCard(data),
            "combat_confirm_selection" => ExecuteCombatConfirmSelection(),
            "select_relic" => ExecuteSelectRelic(data),
            "skip_relic_selection" => ExecuteSkipRelicSelection(),
            "claim_treasure_relic" => ExecuteClaimTreasureRelic(data),

            // Multiplayer-specific actions
            "end_turn" => ExecuteMultiplayerEndTurn(player),
            "undo_end_turn" => ExecuteUndoEndTurn(player),

            _ => Error($"Unknown multiplayer action: {action}")
        };
    }

    private static Dictionary<string, object?> ExecuteMultiplayerEndTurn(Player player)
    {
        if (!CombatManager.Instance.IsInProgress)
            return Error("Not in combat");
        if (!CombatManager.Instance.IsPlayPhase)
            return Error("Not in play phase — cannot act during enemy turn");
        if (CombatManager.Instance.PlayerActionsDisabled)
            return Error("Player actions are currently disabled");
        if (!player.Creature.IsAlive)
            return Error("Player creature is dead — cannot end turn");
        if (CombatManager.Instance.IsPlayerReadyToEndTurn(player))
            return Error("Already submitted end turn — use 'undo_end_turn' to retract");

        // Match the game's own CanTurnBeEnded guard (NEndTurnButton.cs:114-123)
        var hand = NCombatRoom.Instance?.Ui?.Hand;
        if (hand != null && (hand.InCardPlay || hand.CurrentMode != NPlayerHand.Mode.Play))
            return Error("Cannot end turn while a card is being played or hand is in selection mode");

        var combatState = player.Creature.CombatState;
        if (combatState == null)
            return Error("No combat state");

        int roundNumber = combatState.RoundNumber;
        RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(
            new EndPlayerTurnAction(player, roundNumber));

        return new Dictionary<string, object?>
        {
            ["status"] = "ok",
            ["message"] = "Submitted end turn (waiting for other players)"
        };
    }

    private static Dictionary<string, object?> ExecuteUndoEndTurn(Player player)
    {
        if (!CombatManager.Instance.IsInProgress)
            return Error("Not in combat");
        if (!CombatManager.Instance.IsPlayPhase)
            return Error("Not in play phase — cannot act during enemy turn");
        if (CombatManager.Instance.PlayerActionsDisabled)
            return Error("Player actions are currently disabled");
        if (!player.Creature.IsAlive)
            return Error("Player creature is dead");
        if (!CombatManager.Instance.IsPlayerReadyToEndTurn(player))
            return Error("Not ready to end turn — nothing to undo");

        var combatState = player.Creature.CombatState;
        if (combatState == null)
            return Error("No combat state");

        int roundNumber = combatState.RoundNumber;
        RunManager.Instance.ActionQueueSynchronizer.RequestEnqueue(
            new UndoEndPlayerTurnAction(player, roundNumber));

        return new Dictionary<string, object?>
        {
            ["status"] = "ok",
            ["message"] = "Undid end turn — continue playing cards"
        };
    }
}
