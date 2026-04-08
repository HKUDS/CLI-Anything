using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;

namespace STS2_Bridge;

public static partial class BridgeMod
{
    private static string FormatAsMarkdown(Dictionary<string, object?> state)
    {
        var sb = new StringBuilder();
        string stateType = state.TryGetValue("state_type", out var st) ? st?.ToString() ?? "unknown" : "unknown";
        bool isMultiplayer = state.TryGetValue("game_mode", out var gm) && gm?.ToString() == "multiplayer";

        if (isMultiplayer)
            sb.AppendLine($"# Multiplayer Game State: {stateType}");
        else
            sb.AppendLine($"# Game State: {stateType}");
        sb.AppendLine();

        if (state.TryGetValue("run", out var runObj) && runObj is Dictionary<string, object?> run)
        {
            sb.AppendLine($"**Act {run["act"]}** | Floor {run["floor"]} | Ascension {run["ascension"]}");
            sb.AppendLine();
        }

        if (state.TryGetValue("message", out var msg) && msg != null)
        {
            sb.AppendLine(msg.ToString());
            return sb.ToString();
        }

        // Multiplayer players summary (top-level)
        if (isMultiplayer && state.TryGetValue("players", out var playersListObj)
            && playersListObj is List<Dictionary<string, object?>> playersList && playersList.Count > 0)
        {
            sb.AppendLine("## Party");
            foreach (var p in playersList)
            {
                string youTag = p["is_local"] is true ? " **(YOU)**" : "";
                string aliveTag = p["is_alive"] is false ? " [DEAD]" : "";
                sb.AppendLine($"- **{p["character"]}**{youTag}{aliveTag} — HP: {p["hp"]}/{p["max_hp"]} | Gold: {p["gold"]}");
            }
            sb.AppendLine();
        }

        if (state.TryGetValue("battle", out var battleObj) && battleObj is Dictionary<string, object?> battle)
        {
            if (isMultiplayer)
                FormatMultiplayerBattleMarkdown(sb, battle);
            else
                FormatBattleMarkdown(sb, battle);
        }

        if (state.TryGetValue("event", out var eventObj) && eventObj is Dictionary<string, object?> eventData)
        {
            FormatEventMarkdown(sb, eventData);
            if (isMultiplayer)
                FormatEventVotesMarkdown(sb, eventData);
        }

        if (state.TryGetValue("rest_site", out var restObj) && restObj is Dictionary<string, object?> restData)
        {
            FormatRestSiteMarkdown(sb, restData);
        }

        if (state.TryGetValue("shop", out var shopObj) && shopObj is Dictionary<string, object?> shopData)
        {
            FormatShopMarkdown(sb, shopData);
        }

        if (state.TryGetValue("map", out var mapObj) && mapObj is Dictionary<string, object?> mapData)
        {
            FormatMapMarkdown(sb, mapData);
            if (isMultiplayer)
                FormatMapVotesMarkdown(sb, mapData);
        }

        if (state.TryGetValue("rewards", out var rewardsObj) && rewardsObj is Dictionary<string, object?> rewards)
        {
            FormatRewardsMarkdown(sb, rewards);
        }

        if (state.TryGetValue("card_reward", out var cardRewardObj) && cardRewardObj is Dictionary<string, object?> cardReward)
        {
            FormatCardRewardMarkdown(sb, cardReward);
        }

        if (state.TryGetValue("hand_select", out var handSelectObj) && handSelectObj is Dictionary<string, object?> handSelect)
        {
            FormatHandSelectMarkdown(sb, handSelect);
        }

        if (state.TryGetValue("card_select", out var cardSelectObj) && cardSelectObj is Dictionary<string, object?> cardSelect)
        {
            FormatCardSelectMarkdown(sb, cardSelect);
        }

        if (state.TryGetValue("relic_select", out var relicSelectObj) && relicSelectObj is Dictionary<string, object?> relicSelect)
        {
            FormatRelicSelectMarkdown(sb, relicSelect);
        }

        if (state.TryGetValue("treasure", out var treasureObj) && treasureObj is Dictionary<string, object?> treasureData)
        {
            FormatTreasureMarkdown(sb, treasureData);
            if (isMultiplayer)
                FormatTreasureBidsMarkdown(sb, treasureData);
        }

        if (state.TryGetValue("overlay", out var overlayObj) && overlayObj is Dictionary<string, object?> overlayData)
        {
            sb.AppendLine($"## Overlay: {overlayData.GetValueOrDefault("screen_type")}");
            sb.AppendLine(overlayData.GetValueOrDefault("message")?.ToString());
            sb.AppendLine();
        }

        // Keyword glossary — collect all unique keyword definitions
        var glossary = new Dictionary<string, string>();
        CollectKeywordsFromState(state, glossary);
        if (glossary.Count > 0)
        {
            sb.AppendLine("## Keyword Glossary");
            foreach (var (name, description) in glossary.OrderBy(kv => kv.Key))
                sb.AppendLine($"- **{name}**: {description}");
            sb.AppendLine();
        }

        return sb.ToString();
    }

    private static void FormatBattleMarkdown(StringBuilder sb, Dictionary<string, object?> battle)
    {
        sb.AppendLine($"**Round {battle["round"]}** | Turn: {battle["turn"]} | Play Phase: {battle["is_play_phase"]}");
        sb.AppendLine();

        if (battle.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine("## Player (You)");
            string stars = player.TryGetValue("stars", out var s) && s != null ? $" | Stars: {s}" : "";
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Block: {player["block"]} | Energy: {player["energy"]}/{player["max_energy"]}{stars} | Gold: {player["gold"]}");
            sb.AppendLine();

            FormatListSection(sb, "Status", player, "status", p => $"- **{p["name"]}** ({FormatStatusAmount(p["amount"])}): {p["description"]}");
            FormatListSection(sb, "Relics", player, "relics", r =>
            {
                string counter = r.TryGetValue("counter", out var c) && c != null ? $" [{c}]" : "";
                return $"- **{r["name"]}**{counter}: {r["description"]}";
            });
            FormatListSection(sb, "Potions", player, "potions", p => $"- [{p["slot"]}] **{p["name"]}**: {p["description"]}");

            if (player.TryGetValue("hand", out var handObj) && handObj is List<Dictionary<string, object?>> hand && hand.Count > 0)
            {
                sb.AppendLine("### Hand");
                foreach (var card in hand)
                {
                    string playable = card["can_play"] is true ? "✓" : "✗";
                    string keywords = card.TryGetValue("keywords", out var kw) && kw is List<string> kwList && kwList.Count > 0
                        ? $" [{string.Join(", ", kwList)}]" : "";
                    string starCost = card.TryGetValue("star_cost", out var sc) && sc != null ? $" + {sc} star" : "";
                    sb.AppendLine($"- [{card["index"]}] **{card["name"]}** ({card["cost"]} energy{starCost}) [{card["type"]}] {playable}{keywords} — {card["description"]} (target: {card["target_type"]})");
                }
                sb.AppendLine();
            }

            FormatDeckPilesMarkdown(sb, player);

            if (player.TryGetValue("orbs", out var orbsObj) && orbsObj is List<Dictionary<string, object?>> orbs && orbs.Count > 0)
            {
                int slots = player.TryGetValue("orb_slots", out var osVal) && osVal is int sv ? sv : orbs.Count;
                int empty = player.TryGetValue("orb_empty_slots", out var esVal) && esVal is int ev ? ev : 0;
                sb.AppendLine($"### Orbs ({orbs.Count}/{slots} slots)");
                foreach (var orb in orbs)
                {
                    string desc = orb.TryGetValue("description", out var d) && d != null ? $" — {d}" : "";
                    sb.AppendLine($"- **{orb["name"]}** (passive: {orb["passive_val"]}, evoke: {orb["evoke_val"]}){desc}");
                }
                if (empty > 0)
                    sb.AppendLine($"- *{empty} empty slot(s)*");
                sb.AppendLine();
            }
        }

        if (battle.TryGetValue("enemies", out var enemiesObj) && enemiesObj is List<Dictionary<string, object?>> enemies && enemies.Count > 0)
        {
            sb.AppendLine("## Enemies");
            foreach (var enemy in enemies)
            {
                sb.AppendLine($"### {enemy["name"]} (`{enemy["entity_id"]}`)");
                sb.AppendLine($"HP: {enemy["hp"]}/{enemy["max_hp"]} | Block: {enemy["block"]}");

                if (enemy.TryGetValue("intents", out var intentsObj) && intentsObj is List<Dictionary<string, object?>> intents && intents.Count > 0)
                {
                    sb.Append("**Intent:** ");
                    sb.AppendLine(string.Join(", ", intents.Select(i =>
                    {
                        string title = i.TryGetValue("title", out var t) && t != null ? t.ToString()! : i["type"]!.ToString()!;
                        string typeTag = $" ({i["type"]})";
                        string label = i.TryGetValue("label", out var l) && l is string ls && ls.Length > 0 ? $" {ls}" : "";
                        string desc = i.TryGetValue("description", out var d) && d is string ds && ds.Length > 0 ? $" - {ds}" : "";
                        return $"{title}{typeTag}{label}{desc}";
                    })));
                }

                FormatListSection(sb, "Status", enemy, "status", p => $"  - **{p["name"]}** ({FormatStatusAmount(p["amount"])}): {p["description"]}");
                sb.AppendLine();
            }
        }
    }

    private static void FormatDeckPilesMarkdown(StringBuilder sb, Dictionary<string, object?> player)
    {
        sb.AppendLine("### Deck Information");
        sb.AppendLine();

        sb.AppendLine($"#### Draw Pile ({player["draw_pile_count"]} cards, in random order)");
        if (player.TryGetValue("draw_pile", out var drawObj) && drawObj is List<Dictionary<string, object?>> drawPile && drawPile.Count > 0)
        {
            foreach (var card in drawPile)
                sb.AppendLine($"- {card["name"]}: {card["description"]}");
        }
        else
            sb.AppendLine("- *(empty)*");
        sb.AppendLine();

        sb.AppendLine($"#### Discard Pile ({player["discard_pile_count"]} cards)");
        if (player.TryGetValue("discard_pile", out var discardObj) && discardObj is List<Dictionary<string, object?>> discardPile && discardPile.Count > 0)
        {
            foreach (var card in discardPile)
                sb.AppendLine($"- {card["name"]}: {card["description"]}");
        }
        else
            sb.AppendLine("- *(empty)*");
        sb.AppendLine();

        sb.AppendLine($"#### Exhaust Pile ({player["exhaust_pile_count"]} cards)");
        if (player.TryGetValue("exhaust_pile", out var exhaustObj) && exhaustObj is List<Dictionary<string, object?>> exhaustPile && exhaustPile.Count > 0)
        {
            foreach (var card in exhaustPile)
                sb.AppendLine($"- {card["name"]}: {card["description"]}");
        }
        else
            sb.AppendLine("- *(empty)*");
        sb.AppendLine();
    }

    private static void FormatEventMarkdown(StringBuilder sb, Dictionary<string, object?> evt)
    {
        string name = evt.TryGetValue("event_name", out var n) && n != null ? n.ToString()! : "Unknown Event";
        bool isAncient = evt.TryGetValue("is_ancient", out var a) && a is true;
        sb.AppendLine($"## {(isAncient ? "Ancient" : "Event")}: {name}");
        sb.AppendLine();

        if (evt.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Gold: {player["gold"]}");
            sb.AppendLine();
        }

        bool inDialogue = evt.TryGetValue("in_dialogue", out var d) && d is true;
        if (inDialogue)
        {
            sb.AppendLine("*Ancient dialogue in progress — use `advance_dialogue` to continue.*");
            sb.AppendLine();
            return;
        }

        if (evt.TryGetValue("options", out var optObj) && optObj is List<Dictionary<string, object?>> options && options.Count > 0)
        {
            sb.AppendLine("### Options");
            foreach (var opt in options)
            {
                bool locked = opt["is_locked"] is true;
                bool proceed = opt["is_proceed"] is true;
                bool chosen = opt["was_chosen"] is true;

                string tag = locked ? " (LOCKED)" : chosen ? " (CHOSEN)" : proceed ? " (PROCEED)" : "";
                string relic = opt.TryGetValue("relic_name", out var rn) && rn != null ? $" [Relic: {rn}]" : "";
                sb.AppendLine($"- [{opt["index"]}] **{opt["title"]}**{tag}{relic} — {opt["description"]}");
            }
            sb.AppendLine();
        }
        else
        {
            sb.AppendLine("No options available.");
            sb.AppendLine();
        }
    }

    private static void FormatRestSiteMarkdown(StringBuilder sb, Dictionary<string, object?> restSite)
    {
        if (restSite.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine("## Player (You)");
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Gold: {player["gold"]}");
            sb.AppendLine();
        }

        if (restSite.TryGetValue("options", out var optObj) && optObj is List<Dictionary<string, object?>> options && options.Count > 0)
        {
            sb.AppendLine("## Rest Site Options");
            foreach (var opt in options)
            {
                string enabled = opt["is_enabled"] is true ? "" : " (DISABLED)";
                sb.AppendLine($"- [{opt["index"]}] **{opt["name"]}**{enabled} — {opt["description"]}");
            }
            sb.AppendLine();
        }

        bool canProceed = restSite.TryGetValue("can_proceed", out var cp) && cp is true;
        sb.AppendLine($"**Can proceed:** {(canProceed ? "Yes" : "No")}");
        sb.AppendLine();
    }

    private static void FormatShopMarkdown(StringBuilder sb, Dictionary<string, object?> shop)
    {
        if (shop.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine("## Player (You)");
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Gold: {player["gold"]} | Potion slots: {player["open_potion_slots"]}/{player["potion_slots"]} open");
            sb.AppendLine();
        }

        if (shop.TryGetValue("items", out var itemsObj) && itemsObj is List<Dictionary<string, object?>> items)
        {
            sb.AppendLine("## Shop Inventory");
            string? lastCategory = null;
            foreach (var item in items)
            {
                string category = item["category"]?.ToString() ?? "";
                if (category != lastCategory)
                {
                    string header = category switch { "card" => "Cards", "relic" => "Relics", "potion" => "Potions", "card_removal" => "Services", _ => category };
                    sb.AppendLine($"### {header}");
                    lastCategory = category;
                }

                bool stocked = item["is_stocked"] is true;
                bool afford = item["can_afford"] is true;
                string costTag = stocked ? $"{item["cost"]}g" : "SOLD";
                string affordTag = stocked && !afford ? " (can't afford)" : "";
                string saleTag = item.TryGetValue("on_sale", out var os) && os is true ? " **SALE**" : "";

                string desc = category switch
                {
                    "card" => $"**{item.GetValueOrDefault("card_name")}** [{item.GetValueOrDefault("card_type")}] {item.GetValueOrDefault("card_rarity")} — {item.GetValueOrDefault("card_description")}",
                    "relic" => $"**{item.GetValueOrDefault("relic_name")}** — {item.GetValueOrDefault("relic_description")}",
                    "potion" => $"**{item.GetValueOrDefault("potion_name")}** — {item.GetValueOrDefault("potion_description")}",
                    "card_removal" => "**Remove a card** from your deck",
                    _ => "Unknown item"
                };
                sb.AppendLine($"- [{item["index"]}] {desc} — {costTag}{saleTag}{affordTag}");
            }
            sb.AppendLine();
        }

        bool canProceed = shop.TryGetValue("can_proceed", out var cp) && cp is true;
        sb.AppendLine($"**Can proceed:** {(canProceed ? "Yes" : "No")}");
        sb.AppendLine();
    }

    private static void FormatMapMarkdown(StringBuilder sb, Dictionary<string, object?> map)
    {
        // Player summary
        if (map.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine("## Player (You)");
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Gold: {player["gold"]} | Potion slots: {player["open_potion_slots"]}/{player["potion_slots"]} open");
            sb.AppendLine();
        }

        // Path taken
        if (map.TryGetValue("visited", out var visitedObj) && visitedObj is List<Dictionary<string, object?>> visited && visited.Count > 0)
        {
            sb.AppendLine("## Path Taken");
            var parts = visited.Select((v, i) => $"{i + 1}. {v["type"]} ({v["col"]},{v["row"]})");
            sb.AppendLine(string.Join(" → ", parts) + " ← current");
            sb.AppendLine();
        }

        // Next options — the key decision section
        if (map.TryGetValue("next_options", out var optObj) && optObj is List<Dictionary<string, object?>> options && options.Count > 0)
        {
            sb.AppendLine("## Choose Next Node");
            foreach (var opt in options)
            {
                string lookahead = "";
                if (opt.TryGetValue("leads_to", out var leadsObj) && leadsObj is List<Dictionary<string, object?>> leads && leads.Count > 0)
                    lookahead = " → leads to: " + string.Join(", ", leads.Select(l => $"{l["type"]}({l["col"]},{l["row"]})"));
                sb.AppendLine($"- [{opt["index"]}] **{opt["type"]}** ({opt["col"]},{opt["row"]}){lookahead}");
            }
            sb.AppendLine();
        }
        else
        {
            sb.AppendLine("## Map");
            sb.AppendLine("No travelable nodes available.");
            sb.AppendLine();
        }

        // Full map overview — compact row-by-row
        if (map.TryGetValue("nodes", out var nodesObj) && nodesObj is List<Dictionary<string, object?>> nodes && nodes.Count > 0)
        {
            // Collect visited and travelable coords for markers
            var visitedSet = new HashSet<string>();
            if (map.TryGetValue("visited", out var v2) && v2 is List<Dictionary<string, object?>> vList)
                foreach (var vn in vList)
                    visitedSet.Add($"{vn["col"]},{vn["row"]}");

            var travelableSet = new HashSet<string>();
            if (map.TryGetValue("next_options", out var o2) && o2 is List<Dictionary<string, object?>> oList)
                foreach (var on in oList)
                    travelableSet.Add($"{on["col"]},{on["row"]}");

            string? currentKey = null;
            if (map.TryGetValue("current_position", out var cpObj) && cpObj is Dictionary<string, object?> cp)
                currentKey = $"{cp["col"]},{cp["row"]}";

            // Group nodes by row
            var byRow = new SortedDictionary<int, List<Dictionary<string, object?>>>();
            foreach (var node in nodes)
            {
                int row = node["row"] is int r ? r : Convert.ToInt32(node["row"]);
                if (!byRow.TryGetValue(row, out var rowList))
                    byRow[row] = rowList = new List<Dictionary<string, object?>>();
                rowList.Add(node);
            }

            sb.AppendLine("## Map Overview");
            sb.AppendLine("```");
            sb.AppendLine("Legend: · = visited, * = current, → = next option");
            sb.AppendLine();
            foreach (var (row, rowNodes) in byRow)
            {
                var sorted = rowNodes.OrderBy(n => n["col"] is int c ? c : Convert.ToInt32(n["col"])).ToList();
                var labels = new List<string>();
                foreach (var node in sorted)
                {
                    string type = node["type"]?.ToString() ?? "Unknown";
                    string key = $"{node["col"]},{node["row"]}";

                    string marker = "";
                    if (key == currentKey) marker = "*";
                    else if (travelableSet.Contains(key)) marker = "→";
                    else if (visitedSet.Contains(key)) marker = "·";

                    labels.Add($"{marker}{type}({node["col"]},{node["row"]})");
                }
                sb.AppendLine($"  Row {row,2}: {string.Join("  ", labels)}");
            }
            sb.AppendLine("```");
            sb.AppendLine();
        }
    }

    private static void FormatRewardsMarkdown(StringBuilder sb, Dictionary<string, object?> rewards)
    {
        if (rewards.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine("## Player (You)");
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Gold: {player["gold"]} | Potion slots: {player["open_potion_slots"]}/{player["potion_slots"]} open");
            sb.AppendLine();
        }

        if (rewards.TryGetValue("items", out var itemsObj) && itemsObj is List<Dictionary<string, object?>> items && items.Count > 0)
        {
            sb.AppendLine("## Rewards");
            foreach (var item in items)
            {
                string extra = "";
                if (item.TryGetValue("gold_amount", out var gold) && gold != null)
                    extra = $" ({gold} gold)";
                else if (item.TryGetValue("potion_name", out var pName) && pName != null)
                    extra = $" ({pName})";
                sb.AppendLine($"- [{item["index"]}] **{item["type"]}**: {item["description"]}{extra}");
            }
            sb.AppendLine();
        }
        else
        {
            sb.AppendLine("## Rewards");
            sb.AppendLine("No rewards available.");
            sb.AppendLine();
        }

        bool canProceed = rewards.TryGetValue("can_proceed", out var cp) && cp is true;
        sb.AppendLine($"**Can proceed:** {(canProceed ? "Yes" : "No")}");
        sb.AppendLine();
    }

    private static void FormatCardRewardMarkdown(StringBuilder sb, Dictionary<string, object?> cardReward)
    {
        sb.AppendLine("## Card Reward Selection");
        sb.AppendLine("Choose a card to add to your deck:");
        sb.AppendLine();

        if (cardReward.TryGetValue("cards", out var cardsObj) && cardsObj is List<Dictionary<string, object?>> cards)
        {
            foreach (var card in cards)
            {
                string starCost = card.TryGetValue("star_cost", out var sc) && sc != null ? $" + {sc} star" : "";
                string keywords = card.TryGetValue("keywords", out var kw) && kw is List<string> kwList && kwList.Count > 0
                    ? $" [{string.Join(", ", kwList)}]" : "";
                sb.AppendLine($"- [{card["index"]}] **{card["name"]}** ({card["cost"]} energy{starCost}) [{card["type"]}] {card["rarity"]}{keywords} — {card["description"]}");
            }
            sb.AppendLine();
        }

        bool canSkip = cardReward.TryGetValue("can_skip", out var cs) && cs is true;
        sb.AppendLine($"**Can skip:** {(canSkip ? "Yes" : "No")}");
        sb.AppendLine();
    }

    private static void FormatRelicSelectMarkdown(StringBuilder sb, Dictionary<string, object?> relicSelect)
    {
        sb.AppendLine("## Relic Selection");
        if (relicSelect.TryGetValue("prompt", out var p) && p != null)
            sb.AppendLine($"*{p}*");
        sb.AppendLine();

        if (relicSelect.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Gold: {player["gold"]}");
            sb.AppendLine();
        }

        if (relicSelect.TryGetValue("relics", out var relicsObj) && relicsObj is List<Dictionary<string, object?>> relics)
        {
            foreach (var relic in relics)
                sb.AppendLine($"- [{relic["index"]}] **{relic["name"]}** — {relic["description"]}");
            sb.AppendLine();
        }

        bool canSkip = relicSelect.TryGetValue("can_skip", out var cs) && cs is true;
        sb.AppendLine($"Use `select_relic(index)` to choose. Can skip: {(canSkip ? "Yes" : "No")}");
        sb.AppendLine();
    }

    private static void FormatHandSelectMarkdown(StringBuilder sb, Dictionary<string, object?> handSelect)
    {
        sb.AppendLine("## In-Combat Card Selection");

        if (handSelect.TryGetValue("prompt", out var promptObj) && promptObj != null)
            sb.AppendLine($"*{promptObj}*");
        sb.AppendLine();

        string mode = handSelect.TryGetValue("mode", out var m) ? m?.ToString() ?? "simple_select" : "simple_select";
        if (mode == "upgrade_select")
            sb.AppendLine("**Mode:** Upgrade selection");
        sb.AppendLine();

        if (handSelect.TryGetValue("cards", out var cardsObj) && cardsObj is List<Dictionary<string, object?>> cards && cards.Count > 0)
        {
            sb.AppendLine("### Selectable Cards");
            foreach (var card in cards)
            {
                sb.AppendLine($"- [{card["index"]}] **{card["name"]}** ({card["cost"]} energy) [{card["type"]}] — {card["description"]}");
            }
            sb.AppendLine();
        }

        if (handSelect.TryGetValue("selected_cards", out var selObj) && selObj is List<Dictionary<string, object?>> selected && selected.Count > 0)
        {
            sb.AppendLine("### Already Selected");
            foreach (var card in selected)
                sb.AppendLine($"- {card["name"]}");
            sb.AppendLine();
        }

        bool canConfirm = handSelect.TryGetValue("can_confirm", out var cc) && cc is true;
        sb.AppendLine($"Use `combat_select_card(card_index)` to select. Can confirm: {(canConfirm ? "Yes — use `combat_confirm_selection`" : "No — select more cards")}");
        sb.AppendLine();
    }

    private static void FormatCardSelectMarkdown(StringBuilder sb, Dictionary<string, object?> cardSelect)
    {
        string screenType = cardSelect.TryGetValue("screen_type", out var st) ? st?.ToString() ?? "select" : "select";
        string screenLabel = screenType switch
        {
            "transform" => "Transform",
            "upgrade" => "Upgrade",
            "select" => "Select",
            "simple_select" => "Select",
            _ => screenType
        };
        sb.AppendLine($"## Card Selection: {screenLabel}");

        if (cardSelect.TryGetValue("prompt", out var promptObj) && promptObj != null)
        {
            sb.AppendLine($"*{promptObj}*");
        }
        sb.AppendLine();

        if (cardSelect.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Gold: {player["gold"]}");
            sb.AppendLine();
        }

        if (cardSelect.TryGetValue("cards", out var cardsObj) && cardsObj is List<Dictionary<string, object?>> cards)
        {
            sb.AppendLine("### Cards");
            foreach (var card in cards)
            {
                sb.AppendLine($"- [{card["index"]}] **{card["name"]}** ({card["cost"]} energy) [{card["type"]}] {card["rarity"]} — {card["description"]}");
            }
            sb.AppendLine();
        }

        bool preview = cardSelect.TryGetValue("preview_showing", out var pv) && pv is true;
        bool canConfirm = cardSelect.TryGetValue("can_confirm", out var cc) && cc is true;
        bool canCancel = cardSelect.TryGetValue("can_cancel", out var cn) && cn is true;

        if (preview)
            sb.AppendLine("**Preview is showing** — use `confirm_selection` to confirm or `cancel_selection` to go back.");
        else
            sb.AppendLine($"**Select cards** using `select_card(index)`. Can confirm: {(canConfirm ? "Yes" : "No")} | Can cancel: {(canCancel ? "Yes" : "No")}");
        sb.AppendLine();
    }

    private static void FormatTreasureMarkdown(StringBuilder sb, Dictionary<string, object?> treasure)
    {
        if (treasure.TryGetValue("player", out var playerObj) && playerObj is Dictionary<string, object?> player)
        {
            sb.AppendLine("## Player (You)");
            sb.AppendLine($"**{player["character"]}** — HP: {player["hp"]}/{player["max_hp"]} | Gold: {player["gold"]}");
            sb.AppendLine();
        }

        if (treasure.TryGetValue("relics", out var relicsObj) && relicsObj is List<Dictionary<string, object?>> relics && relics.Count > 0)
        {
            sb.AppendLine("## Treasure Relics");
            foreach (var relic in relics)
            {
                string rarity = relic.TryGetValue("rarity", out var r) && r != null ? $" ({r})" : "";
                sb.AppendLine($"- [{relic["index"]}] **{relic["name"]}**{rarity} — {relic["description"]}");
            }
            sb.AppendLine();
            sb.AppendLine("Use `treasure_claim_relic(relic_index)` to claim a relic.");
        }
        else
        {
            sb.AppendLine("Chest is opening...");
        }
        sb.AppendLine();

        bool canProceed = treasure.TryGetValue("can_proceed", out var cp) && cp is true;
        if (canProceed)
            sb.AppendLine("**Can proceed:** Yes");
        sb.AppendLine();
    }

    private static string FormatStatusAmount(object? amount)
    {
        if (amount is int i && i == -1) return "indefinite";
        return amount?.ToString() ?? "0";
    }

    private static void FormatListSection(StringBuilder sb, string title, Dictionary<string, object?> parent, string key,
        Func<Dictionary<string, object?>, string> formatter)
    {
        if (parent.TryGetValue(key, out var listObj) && listObj is List<Dictionary<string, object?>> list && list.Count > 0)
        {
            sb.AppendLine($"### {title}");
            foreach (var item in list)
                sb.AppendLine(formatter(item));
            sb.AppendLine();
        }
    }

    private static void FormatMultiplayerBattleMarkdown(StringBuilder sb, Dictionary<string, object?> battle)
    {
        if (battle.TryGetValue("error", out var err) && err != null)
        {
            sb.AppendLine($"**Combat Error:** {err}");
            sb.AppendLine();
            return;
        }

        bool allReady = battle.TryGetValue("all_players_ready", out var ar) && ar is true;
        sb.AppendLine($"**Round {battle["round"]}** | Turn: {battle["turn"]} | Play Phase: {battle["is_play_phase"]} | All Ready: {allReady}");
        sb.AppendLine();

        // All players
        if (battle.TryGetValue("players", out var playersObj) && playersObj is List<Dictionary<string, object?>> players)
        {
            foreach (var player in players)
            {
                string youTag = player["is_local"] is true ? " **(YOU)**" : "";
                string aliveTag = player["is_alive"] is false ? " [DEAD]" : "";
                string readyTag = player["is_ready_to_end_turn"] is true ? " [READY]" : "";
                string stars = player.TryGetValue("stars", out var s) && s != null ? $" | Stars: {s}" : "";

                sb.AppendLine($"## Player: {player["character"]}{youTag}{aliveTag}{readyTag}");
                string energyStr = player.TryGetValue("energy", out var en) && player.TryGetValue("max_energy", out var men)
                    ? $" | Energy: {en}/{men}" : "";
                sb.AppendLine($"HP: {player["hp"]}/{player["max_hp"]} | Block: {player["block"]}{energyStr}{stars} | Gold: {player["gold"]}");
                sb.AppendLine();

                FormatListSection(sb, "Status", player, "status", p => $"- **{p["name"]}** ({FormatStatusAmount(p["amount"])}): {p["description"]}");
                FormatListSection(sb, "Relics", player, "relics", r =>
                {
                    string counter = r.TryGetValue("counter", out var c) && c != null ? $" [{c}]" : "";
                    return $"- **{r["name"]}**{counter}: {r["description"]}";
                });
                FormatListSection(sb, "Potions", player, "potions", p =>
                {
                    string desc = p.TryGetValue("description", out var d) && d != null ? $": {d}" : "";
                    return $"- [{p["slot"]}] **{p["name"]}**{desc}";
                });

                if (player["is_local"] is true)
                {
                    if (player.TryGetValue("hand", out var handObj) && handObj is List<Dictionary<string, object?>> hand && hand.Count > 0)
                    {
                        sb.AppendLine("### Hand");
                        foreach (var card in hand)
                        {
                            string playable = card["can_play"] is true ? "\u2713" : "\u2717";
                            string keywords = card.TryGetValue("keywords", out var kw) && kw is List<string> kwList && kwList.Count > 0
                                ? $" [{string.Join(", ", kwList)}]" : "";
                            string starCost = card.TryGetValue("star_cost", out var sc) && sc != null ? $" + {sc} star" : "";
                            sb.AppendLine($"- [{card["index"]}] **{card["name"]}** ({card["cost"]} energy{starCost}) [{card["type"]}] {playable}{keywords} — {card["description"]} (target: {card["target_type"]})");
                        }
                        sb.AppendLine();
                    }

                    FormatDeckPilesMarkdown(sb, player);

                    if (player.TryGetValue("orbs", out var orbsObj) && orbsObj is List<Dictionary<string, object?>> orbs && orbs.Count > 0)
                    {
                        int slots = player.TryGetValue("orb_slots", out var osVal) && osVal is int sv ? sv : orbs.Count;
                        int empty = player.TryGetValue("orb_empty_slots", out var esVal) && esVal is int ev ? ev : 0;
                        sb.AppendLine($"### Orbs ({orbs.Count}/{slots} slots)");
                        foreach (var orb in orbs)
                        {
                            string desc = orb.TryGetValue("description", out var d) && d != null ? $" — {d}" : "";
                            sb.AppendLine($"- **{orb["name"]}** (passive: {orb["passive_val"]}, evoke: {orb["evoke_val"]}){desc}");
                        }
                        if (empty > 0)
                            sb.AppendLine($"- *{empty} empty slot(s)*");
                        sb.AppendLine();
                    }
                }
            }
        }

        if (battle.TryGetValue("enemies", out var enemiesObj) && enemiesObj is List<Dictionary<string, object?>> enemies && enemies.Count > 0)
        {
            sb.AppendLine("## Enemies");
            foreach (var enemy in enemies)
            {
                sb.AppendLine($"### {enemy["name"]} (`{enemy["entity_id"]}`)");
                sb.AppendLine($"HP: {enemy["hp"]}/{enemy["max_hp"]} | Block: {enemy["block"]}");

                if (enemy.TryGetValue("intents", out var intentsObj) && intentsObj is List<Dictionary<string, object?>> intents && intents.Count > 0)
                {
                    sb.Append("**Intent:** ");
                    sb.AppendLine(string.Join(", ", intents.Select(i =>
                    {
                        string title = i.TryGetValue("title", out var t) && t != null ? t.ToString()! : i["type"]!.ToString()!;
                        string typeTag = $" ({i["type"]})";
                        string label = i.TryGetValue("label", out var l) && l is string ls && ls.Length > 0 ? $" {ls}" : "";
                        string desc = i.TryGetValue("description", out var d) && d is string ds && ds.Length > 0 ? $" - {ds}" : "";
                        return $"{title}{typeTag}{label}{desc}";
                    })));
                }

                FormatListSection(sb, "Status", enemy, "status", p => $"  - **{p["name"]}** ({FormatStatusAmount(p["amount"])}): {p["description"]}");
                sb.AppendLine();
            }
        }
    }

    private static void FormatMapVotesMarkdown(StringBuilder sb, Dictionary<string, object?> mapData)
    {
        if (!mapData.TryGetValue("votes", out var votesObj) || votesObj is not List<Dictionary<string, object?>> votes || votes.Count == 0)
            return;

        sb.AppendLine("## Map Votes");
        foreach (var vote in votes)
        {
            string youTag = vote["is_local"] is true ? " (YOU)" : "";
            if (vote["voted"] is true)
                sb.AppendLine($"- **{vote["player"]}**{youTag}: voted for ({vote["vote_col"]},{vote["vote_row"]})");
            else
                sb.AppendLine($"- **{vote["player"]}**{youTag}: *waiting...*");
        }
        bool allVoted = mapData.TryGetValue("all_voted", out var av) && av is true;
        if (allVoted)
            sb.AppendLine("**All players have voted!**");
        sb.AppendLine();
    }

    private static void FormatEventVotesMarkdown(StringBuilder sb, Dictionary<string, object?> eventData)
    {
        bool isShared = eventData.TryGetValue("is_shared", out var sh) && sh is true;
        if (!isShared) return;

        if (!eventData.TryGetValue("votes", out var votesObj) || votesObj is not List<Dictionary<string, object?>> votes || votes.Count == 0)
            return;

        sb.AppendLine("## Event Votes (Shared Event)");
        foreach (var vote in votes)
        {
            string youTag = vote["is_local"] is true ? " (YOU)" : "";
            if (vote["voted"] is true)
                sb.AppendLine($"- **{vote["player"]}**{youTag}: voted for option {vote["vote_option"]}");
            else
                sb.AppendLine($"- **{vote["player"]}**{youTag}: *waiting...*");
        }
        bool allVoted = eventData.TryGetValue("all_voted", out var av) && av is true;
        if (allVoted)
            sb.AppendLine("**All players have voted!**");
        sb.AppendLine();
    }

    private static void FormatTreasureBidsMarkdown(StringBuilder sb, Dictionary<string, object?> treasureData)
    {
        if (treasureData.TryGetValue("is_bidding_phase", out var bp) && bp is not true)
            return;

        if (!treasureData.TryGetValue("bids", out var bidsObj) || bidsObj is not List<Dictionary<string, object?>> bids || bids.Count == 0)
            return;

        sb.AppendLine("## Treasure Bids");
        foreach (var bid in bids)
        {
            string youTag = bid["is_local"] is true ? " (YOU)" : "";
            if (bid["voted"] is true)
                sb.AppendLine($"- **{bid["player"]}**{youTag}: bid on relic #{bid["vote_relic_index"]}");
            else
                sb.AppendLine($"- **{bid["player"]}**{youTag}: *waiting...*");
        }
        bool allBid = treasureData.TryGetValue("all_bid", out var ab) && ab is true;
        if (allBid)
            sb.AppendLine("**All players have bid!**");
        sb.AppendLine();
    }

    private static void CollectKeywordsFromState(object? obj, Dictionary<string, string> glossary)
    {
        if (obj is Dictionary<string, object?> dict)
        {
            if (dict.TryGetValue("keywords", out var kw) && kw is List<Dictionary<string, object?>> keywords)
            {
                foreach (var keyword in keywords)
                {
                    string? name = keyword.GetValueOrDefault("name")?.ToString();
                    string? desc = keyword.GetValueOrDefault("description")?.ToString();
                    if (name != null && desc != null)
                        glossary.TryAdd(name, desc);
                }
            }
            foreach (var (key, value) in dict)
            {
                if (key != "keywords")
                    CollectKeywordsFromState(value, glossary);
            }
        }
        else if (obj is List<Dictionary<string, object?>> list)
        {
            foreach (var item in list)
                CollectKeywordsFromState(item, glossary);
        }
    }
}
