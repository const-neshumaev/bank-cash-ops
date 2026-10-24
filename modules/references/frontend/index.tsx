import { IconArrowsExchange, IconCoin } from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import en from './locales/en.json'
import ru from './locales/ru.json'
import { CurrenciesPage } from './pages/CurrenciesPage'
import { RateTypesPage } from './pages/RateTypesPage'

const MANAGE_PERMISSION = 'references.manage'
const ADMIN_SECTION = 'admin'

/**
 * Frontend contract of the `references` module: the administration of the
 * system reference data (the ISO currency catalogue and the bank rate types).
 *
 * The pages are administrative: reading the dictionaries through other
 * modules does not require the ``references.view`` permission, so only users
 * allowed to change the data see the pages and their navigation entries.
 */
export const referencesFrontend: FrontendModule = {
  id: 'references',
  titleKey: 'title',
  routes: [
    {
      path: 'references/currencies',
      element: <CurrenciesPage />,
      permission: MANAGE_PERMISSION,
    },
    {
      path: 'references/rate-types',
      element: <RateTypesPage />,
      permission: MANAGE_PERMISSION,
    },
  ],
  nav: [
    {
      labelKey: 'nav.currencies',
      to: '/references/currencies',
      icon: <IconCoin size={18} />,
      permission: MANAGE_PERMISSION,
      section: ADMIN_SECTION,
    },
    {
      labelKey: 'nav.rateTypes',
      to: '/references/rate-types',
      icon: <IconArrowsExchange size={18} />,
      permission: MANAGE_PERMISSION,
      section: ADMIN_SECTION,
    },
  ],
  resources: { ru, en },
}
