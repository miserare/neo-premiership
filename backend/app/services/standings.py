import uuid
from collections import defaultdict

from app.models.match import Match, MatchStatus
from app.models.season_entry import SeasonEntry
from app.schemas.player import PlayerSummary
from app.schemas.season import BracketRound, StandingsEntry, StandingsGroup
from app.services.matches import to_match_read


def build_standings(season_entries: list[SeasonEntry], group_matches: list[Match]) -> list[StandingsGroup]:
    wins: dict[uuid.UUID, int] = defaultdict(int)
    losses: dict[uuid.UUID, int] = defaultdict(int)
    for match in group_matches:
        if match.status != MatchStatus.COMPLETED or match.winner_id is None:
            continue
        loser_id = match.away_player_id if match.winner_id == match.home_player_id else match.home_player_id
        wins[match.winner_id] += 1
        losses[loser_id] += 1

    groups: dict[str | None, list[SeasonEntry]] = defaultdict(list)
    for entry in season_entries:
        groups[entry.group_label].append(entry)

    def sort_key(entry: SeasonEntry) -> tuple:
        return (-wins[entry.player_id], losses[entry.player_id], -(entry.tiebreaker_value or 0), entry.player.username)

    result = [
        StandingsGroup(
            group_label=group_label,
            standings=[
                StandingsEntry(
                    player=PlayerSummary.model_validate(entry.player),
                    wins=wins[entry.player_id],
                    losses=losses[entry.player_id],
                    tiebreaker_value=entry.tiebreaker_value,
                )
                for entry in sorted(entries, key=sort_key)
            ],
        )
        for group_label, entries in groups.items()
    ]
    # Ungrouped roster (group_label is None) sorts first, then alphabetically by label.
    result.sort(key=lambda g: (g.group_label is not None, g.group_label or ""))
    return result


def build_bracket(playoff_matches: list[Match]) -> list[BracketRound]:
    rounds: dict[tuple[int, str], list[Match]] = defaultdict(list)
    for match in playoff_matches:
        label = match.round_label or "Playoffs"
        order = match.round_order if match.round_order is not None else 0
        rounds[(order, label)].append(match)

    return [
        BracketRound(
            round_label=label,
            round_order=order,
            matches=[
                to_match_read(m) for m in sorted(matches, key=lambda m: (m.bracket_order is None, m.bracket_order or 0))
            ],
        )
        for (order, label), matches in sorted(rounds.items(), key=lambda item: item[0])
    ]
