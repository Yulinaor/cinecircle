/**
 * Finds Tailwind utilities that hard-code left/right. CineCircle supports Hebrew (RTL),
 * so layout must use logical utilities (ms/me, ps/pe, start/end, rounded-s/e, border-s/e,
 * text-start/end) that mirror automatically.
 */
const PHYSICAL = [
  /^(m[lr]|p[lr]|scroll-[mp][lr]|left|right)-(\d|\[|auto|px|full)/,
  /^(rounded|border)-[lr](-|$)/,
  /^rounded-[tb][lr](-|$)/,
  /^(float|text|clear)-(left|right)$/,
]

export function findPhysicalUtilities(source: string): string[] {
  return source
    .split(/[\s"'`{}()<>,;=]+/)
    .filter((token) => {
      const utility = token.split(':').pop()?.replace(/^[!-]+/, '') ?? ''
      return PHYSICAL.some((pattern) => pattern.test(utility))
    })
}
