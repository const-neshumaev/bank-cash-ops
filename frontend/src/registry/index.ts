import { coreFrontend } from '@modules/core/frontend'

import type { FrontendModule } from './contract'

/**
 * Composition point of the frontend: the modules enabled for this build.
 *
 * It mirrors the backend composition (`INSTALLED_APPS` / customer profile).
 * Add a module here to plug its routes and navigation into the shell.
 */
export const enabledModules: FrontendModule[] = [coreFrontend]

/** Routes contributed by every enabled module. */
export const moduleRoutes = enabledModules.flatMap((module) => module.routes)

/** Navigation entries contributed by every enabled module. */
export const moduleNav = enabledModules.flatMap((module) => module.nav ?? [])

export type { FrontendModule, ModuleNavItem, ModuleRoute } from './contract'
