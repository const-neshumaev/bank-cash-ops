import type { ReactNode } from 'react'

/** A route contributed by a module to the host router. */
export interface ModuleRoute {
  path: string
  element: ReactNode
  /**
   * Permission required to open the route. When omitted, any authenticated user
   * may open it.
   */
  permission?: string
}

/** A navigation entry contributed by a module to the app shell. */
export interface ModuleNavItem {
  label: string
  to: string
  icon?: ReactNode
  /** Permission required to see the entry. */
  permission?: string
  /** Navigation section the entry belongs to (e.g. «Администрирование»). */
  section?: string
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
