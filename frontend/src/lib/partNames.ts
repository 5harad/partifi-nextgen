export function displayPartName(value: string): string {
  const first = value[0]
  if (!first || !/^\p{Script=Latin}$/u.test(first) || first !== first.toLowerCase()) {
    return value
  }
  return first.toUpperCase() + value.slice(first.length)
}
