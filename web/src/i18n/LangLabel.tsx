import { useTranslation } from "react-i18next";
import type { Lang } from "../api/types";
import { useLang } from "./useLang";

/**
 * Names the language of fallback text (A6): nothing when the text is in the UI language (or has no
 * language), else the text's own language, e.g. "Hebrew" on an English screen.
 */
export function LangLabel({ lang }: { lang: Lang | null }) {
  const { t } = useTranslation();
  const uiLang = useLang();
  if (lang === null || lang === uiLang) return null;
  return (
    <span className="self-start text-xs font-semibold text-muted">
      {t(`lang.${lang}`)}
    </span>
  );
}
