import type { ReactNode } from 'react'

/**
 * A permission requirement: either a single code or any of several codes
 * (the user needs at least one).
 */
export type PermissionRequirement = string | string[]

/** A route contributed by a module to the host router. */
export interface ModuleRoute {
  path: string
  element: ReactNode
  /**
   * Permission required to open the route. When omitted, any authenticated user
   * may open it.
   */
  permission?: PermissionRequirement
}

/** A navigation entry contributed by a module to the app shell. */
export interface ModuleNavItem {
  /**
   * i18n key of the entry label inside the module's own namespace, resolved by
   * the host as ``t(labelKey, { ns: moduleId })``.
   */
  labelKey: string
  to: string
  icon?: ReactNode
  /** Permission required to see the entry. */
  permission?: PermissionRequirement
  /**
   * Host navigation section the entry belongs to (e.g. ``admin``). The host owns
   * the shell, so it labels the section (`sections.<id>`); omitted means a
   * top-level entry.
   */
  section?: string
}

/**
 * Translation resources a module owns, keyed by language code
 * (``{ ru: {...}, en: {...} }``). The host registers them under the module's
 * ``id`` as an i18next namespace.
 */
export type ModuleResources = Record<string, Record<string, unknown>>

/**
 * Frontend contract a module implements to plug into the host.
 *
 * A module owns its pages, API clients and translations; the host only knows
 * about this manifest and provides the i18n runtime. Modules never import each
 * other — shared building blocks come from the host SDK (`@app/...`).
 */
export interface FrontendModule {
  id: string
  /** i18n key of the module title inside its own namespace. */
  titleKey: string
  routes: ModuleRoute[]
  nav?: ModuleNavItem[]
  /** Translation resources contributed by the module. */
  resources: ModuleResources
}
