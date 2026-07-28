import { type FormEvent, useEffect, useState } from "react";
import { useLocation, useNavigate, useSearchParams } from "react-router-dom";

/** The league's single search box, in the top bar. What it searches follows the
 * current route - seasons while browsing seasons, players everywhere else - and
 * it drives the same ?q= param the list pages already read. */
export default function NavSearch() {
  const location = useLocation();
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();

  const scope: "players" | "seasons" = location.pathname.startsWith("/seasons") ? "seasons" : "players";
  const activeQuery = searchParams.get("q") ?? "";
  const [value, setValue] = useState(activeQuery);

  // Follow the URL when it changes underneath us - back/forward navigation, or
  // moving between the players and seasons lists.
  useEffect(() => {
    setValue(activeQuery);
  }, [activeQuery, scope]);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const trimmed = value.trim();
    navigate(`/${scope}${trimmed ? `?q=${encodeURIComponent(trimmed)}` : ""}`);
  }

  return (
    <form className="nav-search" role="search" onSubmit={handleSubmit}>
      <label className="nav-search__label" htmlFor="nav-search-input">
        Search {scope}
      </label>
      <input
        id="nav-search-input"
        type="search"
        className="nav-search__input"
        placeholder={scope === "seasons" ? "Search seasons..." : "Search players..."}
        value={value}
        onChange={(event) => setValue(event.target.value)}
      />
      <button type="submit" className="nav-search__button">
        Search
      </button>
    </form>
  );
}
