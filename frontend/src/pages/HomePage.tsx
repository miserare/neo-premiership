import { Link } from "react-router-dom";

import ExternalLink from "../components/ExternalLink";
import { useHome } from "../hooks/useHome";
import type { HomeLink } from "../types";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

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

export default function HomePage() {
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
            <Link to={`/seasons/${season.id}`}>{season.name}</Link>
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

          {season && (
            <section className="home-page__roster" aria-labelledby="roster-heading">
              <h2 id="roster-heading">{season.name} roster</h2>
              {season.roster.length > 0 ? (
                <ul className="home-page__roster-list">
                  {season.roster.map((player) => (
                    <li key={player.id}>
                      <Link to={`/players/${player.id}`}>{player.username}</Link>
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
                    <p>{announcement.body}</p>
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
