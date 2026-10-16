import {
  IconBuildingBank,
  IconCashBanknote,
  IconClock,
  IconCoin,
  IconDeviceDesktop,
  IconShieldLock,
  IconUsers,
} from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import en from './locales/en.json'
import ru from './locales/ru.json'
import { BranchesPage } from './pages/BranchesPage'
import { CashDeskCurrenciesPage } from './pages/CashDeskCurrenciesPage'
import { CashDesksPage } from './pages/CashDesksPage'
import { RolesPage } from './pages/RolesPage'
import { ShiftsPage } from './pages/ShiftsPage'
import { UsersPage } from './pages/UsersPage'
import { WorkplacePage } from './pages/WorkplacePage'

const ADMIN_SECTION = 'admin'
const CURRENCIES_PERMISSIONS = [
  'core.currencies.config.manage',
  'core.currencies.config.manage.branch',
]

/** Frontend contract of the `core` module (administration and cash shifts). */
export const coreFrontend: FrontendModule = {
  id: 'core',
  titleKey: 'title',
  routes: [
    { path: 'users', element: <UsersPage />, permission: 'core.users.view' },
    { path: 'roles', element: <RolesPage />, permission: 'core.roles.view' },
    { path: 'branches', element: <BranchesPage />, permission: 'core.structure.view' },
    { path: 'cash-desks', element: <CashDesksPage />, permission: 'core.structure.view' },
    {
      path: 'cash-desk-currencies',
      element: <CashDeskCurrenciesPage />,
      permission: CURRENCIES_PERMISSIONS,
    },
    { path: 'shifts', element: <ShiftsPage />, permission: 'core.shifts.view' },
    { path: 'workplace', element: <WorkplacePage />, permission: 'core.shifts.open' },
  ],
  nav: [
    {
      labelKey: 'nav.users',
      to: '/users',
      icon: <IconUsers size={18} />,
      permission: 'core.users.view',
      section: ADMIN_SECTION,
    },
    {
      labelKey: 'nav.roles',
      to: '/roles',
      icon: <IconShieldLock size={18} />,
      permission: 'core.roles.view',
      section: ADMIN_SECTION,
    },
    {
      labelKey: 'nav.branches',
      to: '/branches',
      icon: <IconBuildingBank size={18} />,
      permission: 'core.structure.view',
      section: ADMIN_SECTION,
    },
    {
      labelKey: 'nav.cashDesks',
      to: '/cash-desks',
      icon: <IconDeviceDesktop size={18} />,
      permission: 'core.structure.view',
      section: ADMIN_SECTION,
    },
    {
      labelKey: 'nav.cashDeskCurrencies',
      to: '/cash-desk-currencies',
      icon: <IconCoin size={18} />,
      permission: CURRENCIES_PERMISSIONS,
      section: ADMIN_SECTION,
    },
    {
      labelKey: 'nav.shifts',
      to: '/shifts',
      icon: <IconClock size={18} />,
      permission: 'core.shifts.view',
    },
    {
      labelKey: 'nav.workplace',
      to: '/workplace',
      icon: <IconCashBanknote size={18} />,
      permission: 'core.shifts.open',
    },
  ],
  resources: { ru, en },
}
