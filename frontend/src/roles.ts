/** Colour hints for the seeded role codes; unknown roles fall back to grey. */
export const ROLE_COLORS: Record<string, string> = {
  administrator: 'red',
  branch_manager: 'grape',
  specialist: 'orange',
  cashier: 'blue',
}

export function roleColor(code: string): string {
  return ROLE_COLORS[code] ?? 'gray'
}
