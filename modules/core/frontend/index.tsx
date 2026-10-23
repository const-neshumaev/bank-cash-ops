import {
  IconArrowsExchange,
  IconBuildingBank,
  IconCashBanknote,
  IconClock,
  IconCoin,
  IconDeviceDesktop,
  IconHistory,
  IconListDetails,
  IconRuler2,
  IconSettings,
  IconShieldLock,
  IconUsers,
} from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import en from './locales/en.json'
import ru from './locales/ru.json'
import { BankSettingsPage } from './pages/BankSettingsPage'
import { BaseValuesPage } from './pages/BaseValuesPage'
import { BranchesPage } from './pages/BranchesPage'
import { CashDeskCurrenciesPage } from './pages/CashDeskCurrenciesPage'
import { CashDesksPage } from './pages/CashDesksPage'
import { CurrentRatesPage } from './pages/CurrentRatesPage'
import { RatesEntryPage } from './pages/RatesEntryPage'
import { RatesJournalPage } from './pages/RatesJournalPage'
import { RolesPage } from './pages/RolesPage'
import { ShiftsPage } from './pages/ShiftsPage'
import { UsersPage } from './pages/UsersPage'
import { WorkplacePage } from './pages/WorkplacePage'

const ADMIN_SECTION = 'admin'
const RATES_SECTION = 'rates'
const CATALOGS_SECTION = 'catalogs'
const CURRENCIES_PERMISSIONS = [
  'core.currencies.config.manage',
  'core.currencies.config.manage.branch',
]
const RATE_MANAGE_PERMISSIONS = [
  'core.currency_rates.manage',
  'core.currency_rates.manage.branch',
  'core.currency_rates.manage.cash_desk',
  'core.currency_rates.manage.official',
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
    {
      path: 'rates/entry',
      element: <RatesEntryPage />,
      permission: RATE_MANAGE_PERMISSIONS,
    },
    {
      path: 'rates/journal',
      element: <RatesJournalPage />,
      permission: 'core.currency_rates.view',
    },
    {
      path: 'rates/current',
      element: <CurrentRatesPage />,
      permission: 'core.currency_rates.view',
    },
    {
      path: 'bank-settings',
      element: <BankSettingsPage />,
      permission: 'core.bank_settings.manage',
    },
    {
      path: 'base-values',
      element: <BaseValuesPage />,
      permission: 'core.base_values.view',
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
      labelKey: 'nav.ratesEntry',
      to: '/rates/entry',
      icon: <IconArrowsExchange size={18} />,
      permission: RATE_MANAGE_PERMISSIONS,
      section: RATES_SECTION,
    },
    {
      labelKey: 'nav.ratesJournal',
      to: '/rates/journal',
      icon: <IconHistory size={18} />,
      permission: 'core.currency_rates.view',
      section: RATES_SECTION,
    },
    {
      labelKey: 'nav.currentRates',
      to: '/rates/current',
      icon: <IconListDetails size={18} />,
      permission: 'core.currency_rates.view',
      section: RATES_SECTION,
    },
    {
      labelKey: 'nav.bankSettings',
      to: '/bank-settings',
      icon: <IconSettings size={18} />,
      permission: 'core.bank_settings.manage',
      section: ADMIN_SECTION,
    },
    {
      labelKey: 'nav.baseValues',
      to: '/base-values',
      icon: <IconRuler2 size={18} />,
      permission: 'core.base_values.view',
      section: CATALOGS_SECTION,
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
