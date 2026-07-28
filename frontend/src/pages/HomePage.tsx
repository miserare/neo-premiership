import { Link } from "react-router-dom";

import ExternalLink from "../components/ExternalLink";
import { useHome } from "../hooks/useHome";

function formatDate(iso: string): string {
  return new Date(iso).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
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
            <div className="home-page__link-card">
              <h2>Latest stream</h2>
              {data.latest_stream ? (
                <ExternalLink href={data.latest_stream.url}>{data.latest_stream.label}</ExternalLink>
              ) : (
                <p>No streams yet.</p>
              )}
            </div>
            <div className="home-page__link-card">
              <h2>Season sheet</h2>
              {season?.sheet_url ? (
                <ExternalLink href={season.sheet_url}>{season.name} Google Sheet</ExternalLink>
              ) : (
                <p>No sheet linked yet.</p>
              )}
            </div>
            <div className="home-page__link-card">
              <h2>Standings</h2>
              {season ? (
                <Link to={`/seasons/${season.id}`}>View {season.name} table</Link>
              ) : (
                <p>Not available yet.</p>
              )}
            </div>
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
