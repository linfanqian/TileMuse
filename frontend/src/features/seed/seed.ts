// The largest seed the editor picks or takes. The backend takes any whole number.
export const MAX_SEED = 2 ** 31 - 1

// Math.random only picks the seed; the backend generator is deterministic given it.
export const randomSeed = () => Math.floor(Math.random() * (MAX_SEED + 1))

/** The seed typed in, or null if it isn't a whole number from 0 to MAX_SEED. */
export function parseSeed(text: string): number | null {
  const trimmed = text.trim()
  if (!/^\d+$/.test(trimmed)) return null
  const seed = Number(trimmed)
  return seed <= MAX_SEED ? seed : null
}
