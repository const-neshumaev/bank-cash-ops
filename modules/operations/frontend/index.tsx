import { IconCashRegister, IconSettings } from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import { OperationsConfigPage } from './pages/OperationsConfigPage'
import { OperationsWorkplacePage } from './pages/OperationsWorkplacePage'

const ADMIN_SECTION = 'Администрирование'
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
  title: 'Кассовые операции',
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
  ],
  nav: [
    {
      label: 'Касса',
      to: '/operations',
      icon: <IconCashRegister size={18} />,
      permission: 'operations.view',
    },
    {
      label: 'Операции касс',
      to: '/operations-config',
      icon: <IconSettings size={18} />,
      permission: CONFIG_PERMISSIONS,
      section: ADMIN_SECTION,
    },
  ],
}
