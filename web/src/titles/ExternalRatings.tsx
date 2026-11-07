import { useTranslation } from "react-i18next";
import type { TitleDetail } from "../api/types";
import { useLang } from "../i18n/useLang";

const CHIP = "rounded-full border border-line bg-bg px-3 py-1 text-sm text-ink";

/**
 * The ratings other services gave the title, one chip per source that has one, each naming its
 * source inline (R4.2): never styled or worded like a CineCircle user's own rating.
 */
export function ExternalRatings({
  ratings,
}: {
  ratings: TitleDetail["ratings"];
}) {
  const { t } = useTranslation();
  const lang = useLang();
  const chips = [
    ratings.imdb && {
      source: "IMDb",
      value: ratings.imdb.rating.toFixed(1),
      votes: ratings.imdb.votes,
    },
    ratings.rotten_tomatoes !== null && {
      source: "Rotten Tomatoes",
      value: `${ratings.rotten_tomatoes}%`,
      votes: null,
    },
    ratings.metacritic !== null && {
      source: "Metacritic",
      value: String(ratings.metacritic),
      votes: null,
    },
    ratings.tmdb !== null && {
      source: "TMDB",
      value: ratings.tmdb.toFixed(1),
      votes: null,
    },
  ].filter((chip) => chip !== false && chip !== null);
  if (chips.length === 0) return null;
  return (
    <ul className="flex flex-wrap gap-2">
      {chips.map((chip) => (
        <li key={chip.source} className={CHIP}>
          <span className="text-muted">{chip.source}</span>{" "}
          <bdi className="font-bold">{chip.value}</bdi>
          {chip.votes !== null && (
            <span className="text-muted">
              {" "}
              ·{" "}
              <bdi>
                {t("title.votes", {
                  n: new Intl.NumberFormat(lang).format(chip.votes),
                })}
              </bdi>
            </span>
          )}
        </li>
      ))}
    </ul>
  );
}
