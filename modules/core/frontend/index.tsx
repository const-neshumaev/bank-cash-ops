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

import { BranchesPage } from './pages/BranchesPage'
import { CashDeskCurrenciesPage } from './pages/CashDeskCurrenciesPage'
import { CashDesksPage } from './pages/CashDesksPage'
import { RolesPage } from './pages/RolesPage'
import { ShiftsPage } from './pages/ShiftsPage'
import { UsersPage } from './pages/UsersPage'
import { WorkplacePage } from './pages/WorkplacePage'

const ADMIN_SECTION = 'Администрирование'
const CURRENCIES_PERMISSIONS = [
  'core.currencies.config.manage',
  'core.currencies.config.manage.branch',
]

/** Frontend contract of the `core` module (administration and cash shifts). */
export const coreFrontend: FrontendModule = {
  id: 'core',
  title: 'Ядро',
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
      label: 'Пользователи',
      to: '/users',
      icon: <IconUsers size={18} />,
      permission: 'core.users.view',
      section: ADMIN_SECTION,
    },
    {
      label: 'Роли',
      to: '/roles',
      icon: <IconShieldLock size={18} />,
      permission: 'core.roles.view',
      section: ADMIN_SECTION,
    },
    {
      label: 'Отделения',
      to: '/branches',
      icon: <IconBuildingBank size={18} />,
      permission: 'core.structure.view',
      section: ADMIN_SECTION,
    },
    {
      label: 'Кассы',
      to: '/cash-desks',
      icon: <IconDeviceDesktop size={18} />,
      permission: 'core.structure.view',
      section: ADMIN_SECTION,
    },
    {
      label: 'Валюты касс',
      to: '/cash-desk-currencies',
      icon: <IconCoin size={18} />,
      permission: CURRENCIES_PERMISSIONS,
      section: ADMIN_SECTION,
    },
    {
      label: 'Смены',
      to: '/shifts',
      icon: <IconClock size={18} />,
      permission: 'core.shifts.view',
    },
    {
      label: 'Рабочее место',
      to: '/workplace',
      icon: <IconCashBanknote size={18} />,
      permission: 'core.shifts.open',
    },
  ],
}
