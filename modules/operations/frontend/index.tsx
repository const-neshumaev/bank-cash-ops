import { IconAdjustments, IconCashRegister, IconSettings } from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import en from './locales/en.json'
import ru from './locales/ru.json'
import { OperationsConfigPage } from './pages/OperationsConfigPage'
import { OperationsWorkplacePage } from './pages/OperationsWorkplacePage'
import { OperationTypesPage } from './pages/OperationTypesPage'

const CONFIG_PERMISSIONS = ['operations.config.manage', 'operations.config.manage.branch']

/**
 * Frontend contract of the `operations` module: the cashier workplace and the
 * administration of the per-cash-desk operation configuration.
 *
 * The workplace needs an open shift (opened on the `core` workplace page) and the
 * `operations.view` permission; the configuration pages need the configuration
 * permissions (bank-wide or branch-scoped).
 */
export const operationsFrontend: FrontendModule = {
  id: 'operations',
  titleKey: 'title',
  routes: [
    {
      path: 'operations',
      element: <OperationsWorkplacePage />,
      permission: 'operations.view',
    },
    {
      path: 'operations-config',
      element: <OperationsConfigPage />,
      permission: CONFIG_PERMISSIONS,
    },
    {
      path: 'operation-types',
      element: <OperationTypesPage />,
      permission: 'operations.view',
    },
  ],
  nav: [
    {
      labelKey: 'nav.workplace',
      to: '/operations',
      icon: <IconCashRegister size={18} />,
      permission: 'operations.view',
    },
    {
      labelKey: 'nav.config',
      to: '/operations-config',
      icon: <IconSettings size={18} />,
      permission: CONFIG_PERMISSIONS,
      section: 'admin',
    },
    {
      labelKey: 'nav.operationTypes',
      to: '/operation-types',
      icon: <IconAdjustments size={18} />,
      permission: 'operations.types.manage',
      section: 'admin',
    },
  ],
  resources: { ru, en },
}
