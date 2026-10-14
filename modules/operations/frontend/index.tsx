import { IconCashRegister } from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import { OperationsWorkplacePage } from './pages/OperationsWorkplacePage'

/**
 * Frontend contract of the `operations` module: the cashier workplace.
 *
 * The page needs an open shift (opened on the `core` workplace page) and the
 * `operations.view` permission.
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
  ],
  nav: [
    {
      label: 'Касса',
      to: '/operations',
      icon: <IconCashRegister size={18} />,
      permission: 'operations.view',
    },
  ],
}
