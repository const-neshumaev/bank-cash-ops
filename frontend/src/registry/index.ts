import i18n from '@app/i18n'
import { coreFrontend } from '@modules/core/frontend'
import { operationsFrontend } from '@modules/operations/frontend'
import { referencesFrontend } from '@modules/references/frontend'

import type { FrontendModule, ModuleNavItem } from './contract'

/**
 * Composition point of the frontend: the modules enabled for this build.
 *
 * It mirrors the backend composition (`INSTALLED_APPS` / customer profile).
 * Add a module here to plug its routes, navigation and translations into the shell.
 */
export const enabledModules: FrontendModule[] = [
  referencesFrontend,
  coreFrontend,
  operationsFrontend,
]

// Register each module's translation bundle under its own i18next namespace, so a
// module owns its strings while the host provides the runtime and the switcher.
for (const module of enabledModules) {
  for (const [language, bundle] of Object.entries(module.resources)) {
    i18n.addResourceBundle(language, module.id, bundle, true, true)
  }
}

/** Routes contributed by every enabled module. */
export const moduleRoutes = enabledModules.flatMap((module) => module.routes)

/** A navigation entry tagged with the module that owns it (for its namespace). */
export interface ResolvedNavItem extends ModuleNavItem {
  moduleId: string
}

/** Navigation entries contributed by every enabled module. */
export const moduleNav: ResolvedNavItem[] = enabledModules.flatMap((module) =>
  (module.nav ?? []).map((item) => ({ ...item, moduleId: module.id })),
)

export type { FrontendModule, ModuleNavItem, ModuleRoute } from './contract'
