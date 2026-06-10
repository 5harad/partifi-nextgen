const COMPOSERS_URL = '/data/composers.json'
const DEFAULT_LIMIT = 12

export type ComposerData = {
  names: string[]
  popular: string[]
}

let composerDataPromise: Promise<ComposerData> | null = null

export function loadComposerData(): Promise<ComposerData> {
  if (!composerDataPromise) {
    composerDataPromise = fetch(COMPOSERS_URL)
      .then(async (res) => {
        if (!res.ok) throw new Error('Failed to load composer list')
        const data = (await res.json()) as ComposerData | string[]
        if (Array.isArray(data)) {
          return { names: data, popular: [] }
        }
        return {
          names: data.names ?? [],
          popular: data.popular ?? [],
        }
      })
      .catch((err) => {
        composerDataPromise = null
        throw err
      })
  }
  return composerDataPromise
}

/** @deprecated use loadComposerData */
export function loadComposerNames(): Promise<string[]> {
  return loadComposerData().then((d) => d.names)
}

function tokenize(name: string): string[] {
  return name
    .toLowerCase()
    .split(/[\s,.-]+/)
    .filter(Boolean)
}

export function scoreComposerMatch(name: string, term: string, popularRank: Map<string, number>): number {
  const q = term.trim().toLowerCase()
  if (q.length < 2) return -1

  const lower = name.toLowerCase()
  if (!lower.includes(q)) return -1

  const tokens = tokenize(name)
  const lastToken = tokens[tokens.length - 1] ?? ''
  const tokenStarts = tokens.some((t) => t.startsWith(q))
  const tokenExact = tokens.some((t) => t === q)
  const lastExact = lastToken === q
  const lastStarts = lastToken.startsWith(q)
  const nameStarts = lower.startsWith(q)

  let score = 0
  if (lastExact) score += 100
  else if (lastStarts) score += 80
  else if (tokenExact) score += 60
  else if (tokenStarts) score += 40
  else if (nameStarts) score += 30
  else score += 10

  if (q.length <= 5 && !lastStarts && !tokenStarts && !nameStarts) {
    score -= 25
  }

  const pop = popularRank.get(name)
  if (pop !== undefined) {
    score += 500 - pop
  }

  return score
}

export function filterComposerNames(
  names: string[],
  term: string,
  popular: string[] = [],
  limit = DEFAULT_LIMIT,
): string[] {
  const q = term.trim()
  if (q.length < 2) return []

  const popularRank = new Map(popular.map((name, index) => [name, index]))
  const ranked: Array<{ name: string; score: number }> = []

  for (const name of names) {
    const score = scoreComposerMatch(name, q, popularRank)
    if (score >= 0) ranked.push({ name, score })
  }

  ranked.sort((a, b) => {
    if (b.score !== a.score) return b.score - a.score
    return a.name.localeCompare(b.name)
  })

  return ranked.slice(0, limit).map((row) => row.name)
}
