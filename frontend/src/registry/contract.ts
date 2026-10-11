import type { ReactNode } from 'react'

/** Access level required to open a module route. */
export type ModuleAccess = 'protected' | 'admin'

/** A route contributed by a module to the host router. */
export interface ModuleRoute {
  path: string
  element: ReactNode
  /** Defaults to `protected` (available to any authenticated user). */
  access?: ModuleAccess
}

/** A navigation entry contributed by a module to the app shell. */
export interface ModuleNavItem {
  label: string
  to: string
  icon?: ReactNode
  adminOnly?: boolean
}

/**
 * Frontend contract a module implements to plug into the host.
 *
 * A module owns its pages and API clients; the host only knows about this
 * manifest. Modules never import each other — shared building blocks come from
 * the host SDK (`@app/...`).
 */
export interface FrontendModule {
  id: string
  title: string
  routes: ModuleRoute[]
  nav?: ModuleNavItem[]
}
