/** Greeting label for the header: given_name from Google, then sensible fallbacks. */
export function displayGreetingName(
  givenName: string | null | undefined,
  name: string | null | undefined,
): string {
  const fromGiven = givenName?.trim()
  if (fromGiven) return fromGiven

  if (!name?.trim()) return 'there'
  const trimmed = name.trim()

  if (trimmed.includes('@')) {
    const local = trimmed.split('@')[0]?.split('.')[0]
    if (local) return local.charAt(0).toUpperCase() + local.slice(1)
  }

  return trimmed.split(/\s+/)[0]
}
