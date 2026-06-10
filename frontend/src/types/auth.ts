export type AuthUser = {
  id: string
  name: string | null
}

export type AuthMeResponse = {
  user: AuthUser | null
}
