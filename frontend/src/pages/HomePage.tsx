import { Link } from "react-router-dom";

import ExternalLink from "../components/ExternalLink";
import MatchList from "../components/MatchList";
import PlainText from "../components/PlainText";
import { useDocumentTitle } from "../hooks/useDocumentTitle";
import { useHome } from "../hooks/useHome";
import { formatDate } from "../lib/format";
import { playerPath, seasonPath } from "../lib/routes";
import type { HomeFixtures, HomeLink } from "../types";

/** The standings link points inside the site by default, but an admin can pin
 * an outbound URL - so the element depends on the link, not the card. */
function LinkCard({ heading, link, empty }: { heading: string; link: HomeLink | null; empty: string }) {
  return (
    <div className="home-page__link-card">
      <h2>{heading}</h2>
      {link ? (
        link.external ? (
          <ExternalLink href={link.url}>{link.label}</ExternalLink>
        ) : (
          <Link to={link.url}>{link.label}</Link>
        )
      ) : (
        <p>{empty}</p>
      )}
    </div>
  );
}

/**
 * This week's matches, and whatever an administrator has pinned.
 *
 * Two lists because they are two different claims - one about the calendar, one
 * editorial - and because that is what stops a featured match in the current
 * week appearing twice. The week is decided server-side in the league's own
 * time zone, so this only renders the answer.
 */
function Fixtures({ fixtures, seasonName }: { fixtures: HomeFixtures; seasonName: string | null }) {
  const weekLabel = `${formatDate(fixtures.week_start)} - ${formatDate(fixtures.week_end)}`;

  return (
    <section className="home-page__fixtures" aria-labelledby="fixtures-heading">
      <h2 id="fixtures-heading">Matchday</h2>

      {fixtures.featured.length > 0 && (
        <div className="home-page__fixture-group">
          <h3>Featured</h3>
          <MatchList
            matches={fixtures.featured}
            labelFor={(match) => match.round_label}
            featuredFor={() => true}
            empty="Nothing featured."
          />
        </div>
      )}

      <div className="home-page__fixture-group">
        <h3>This week</h3>
        <p className="home-page__fixture-week">{weekLabel}</p>
        <MatchList
          matches={fixtures.this_week}
          labelFor={(match) => match.round_label}
          empty={
            seasonName
              ? `No ${seasonName} matches are scheduled this week.`
              : "No matches are scheduled this week."
          }
        />
      </div>
    </section>
  );
}

export default function HomePage() {
  useDocumentTitle();
  const { data, isLoading, error } = useHome();
  const season = data?.current_season ?? null;

  return (
    <div className="home-page">
      <section className="home-page__hero">
        <p className="home-page__eyebrow">Pokémon draft league</p>
        <h1>Pokémon Premiership</h1>
        {/* The hero doubles as the league's status board - which season is
            running, and whether it's live - rather than pure decoration. */}
        {season ? (
          <div className="home-page__hero-season">
            <span className={season.is_active ? "badge badge--active" : "badge badge--inactive"}>
              {season.is_active ? "In season" : "Off-season"}
            </span>
            <Link to={seasonPath(season.slug)}>{season.name}</Link>
          </div>
        ) : (
          <p>No seasons have been scheduled yet.</p>
        )}
      </section>

      {isLoading && <p role="status">Loading league info...</p>}
      {error && (
        <p role="alert" className="home-page__error">
          {error}
        </p>
      )}

      {!isLoading && !error && data && (
        <>
          <section className="home-page__links">
            <LinkCard heading="Latest stream" link={data.latest_stream} empty="No streams yet." />
            <LinkCard heading="League document" link={data.document} empty="No document linked yet." />
            <LinkCard heading="Table" link={data.table} empty="Not available yet." />
          </section>

          <Fixtures fixtures={data.fixtures} seasonName={season?.name ?? null} />

          {season && (
            <section className="home-page__roster" aria-labelledby="roster-heading">
              <h2 id="roster-heading">{season.name} roster</h2>
              {season.roster.length > 0 ? (
                <ul className="home-page__roster-list">
                  {season.roster.map((player) => (
                    <li key={player.id}>
                      <Link to={playerPath(player.slug)}>{player.username}</Link>
                    </li>
                  ))}
                </ul>
              ) : (
                <p>No players are on this season&apos;s roster yet.</p>
              )}
            </section>
          )}

          <section className="home-page__announcements" aria-labelledby="announcements-heading">
            <h2 id="announcements-heading">Announcements</h2>
            {data.announcements.length > 0 ? (
              <ul className="home-page__announcement-list">
                {data.announcements.map((announcement) => (
                  <li key={announcement.id} className="announcement-card">
                    <h3>{announcement.title}</h3>
                    <p className="announcement-card__date">{formatDate(announcement.published_at)}</p>
                    {/* Plain text with its newlines kept: a fixture list loses
                        its shape if they are collapsed. */}
                    <PlainText>{announcement.body}</PlainText>
                    {announcement.link_url && <ExternalLink href={announcement.link_url}>Learn more</ExternalLink>}
                  </li>
                ))}
              </ul>
            ) : (
              <p>No announcements yet.</p>
            )}
          </section>
        </>
      )}
    </div>
  );
}
