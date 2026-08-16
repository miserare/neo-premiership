import uuid
from collections import defaultdict

from app.models.match import Match, MatchStatus
from app.models.playoff_round import PlayoffRound
from app.models.season_entry import SeasonEntry
from app.schemas.player import PlayerSummary
from app.schemas.season import BracketRound, StandingsEntry, StandingsGroup
from app.services.matches import to_match_read


def build_standings(season_entries: list[SeasonEntry], group_matches: list[Match]) -> list[StandingsGroup]:
    wins: dict[uuid.UUID, int] = defaultdict(int)
    losses: dict[uuid.UUID, int] = defaultdict(int)
    differential: dict[uuid.UUID, int] = defaultdict(int)
    incomplete: set[uuid.UUID] = set()
    for match in group_matches:
        if match.status != MatchStatus.COMPLETED or match.winner_id is None:
            continue
        loser_id = match.away_player_id if match.winner_id == match.home_player_id else match.home_player_id
        wins[match.winner_id] += 1
        losses[loser_id] += 1
        if not match.games:
            incomplete.update((match.home_player_id, match.away_player_id))
            continue
        for game in match.games:
            if game.winner_id is None:
                continue
            if game.home_pokemon_score is None or game.away_pokemon_score is None:
                incomplete.update((match.home_player_id, match.away_player_id))
                continue
            game_diff = game.home_pokemon_score - game.away_pokemon_score
            differential[match.home_player_id] += game_diff
            differential[match.away_player_id] -= game_diff

    groups: dict[str | None, list[SeasonEntry]] = defaultdict(list)
    for entry in season_entries:
        groups[entry.group_label].append(entry)

    def sort_key(entry: SeasonEntry) -> tuple:
        player_id = entry.player_id
        return (
            -wins[player_id],
            losses[player_id],
            player_id in incomplete,
            -differential[player_id],
            -(entry.tiebreaker_value or 0),
            entry.player.username.casefold(),
            str(player_id),
        )

    result = [
        StandingsGroup(
            group_label=group_label,
            standings=[
                StandingsEntry(
                    player=PlayerSummary.model_validate(entry.player),
                    wins=wins[entry.player_id],
                    losses=losses[entry.player_id],
                    pokemon_differential=(
                        None if entry.player_id in incomplete else differential[entry.player_id]
                    ),
                    pokemon_differential_complete=entry.player_id not in incomplete,
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


def _bracket_position(match: Match) -> tuple[int, int, str]:
    """Sort key for a match inside its round: bracket position first, then id
    purely as a deterministic tie-breaker. Matches with no position yet sort
    after the placed ones rather than jumping to the front."""
    return (1 if match.bracket_order is None else 0, match.bracket_order or 0, str(match.id))


def build_bracket(rounds: list[PlayoffRound], playoff_matches: list[Match]) -> list[BracketRound]:
    """The public bracket, one entry per round, in display_order.

    Driven by the round rows, not by the matches: a round that has been planned
    but not yet drawn still gets its column, in its proper place. Labels and
    dates play no part in the ordering.
    """
    by_round: dict[uuid.UUID, list[Match]] = defaultdict(list)
    for match in playoff_matches:
        if match.playoff_round_id is not None:
            by_round[match.playoff_round_id].append(match)

    return [
        BracketRound(
            id=playoff_round.id,
            label=playoff_round.label,
            display_order=playoff_round.display_order,
            round_label=playoff_round.label,
            round_order=playoff_round.display_order,
            matches=[to_match_read(m) for m in sorted(by_round.get(playoff_round.id, []), key=_bracket_position)],
        )
        for playoff_round in rounds
    ]
