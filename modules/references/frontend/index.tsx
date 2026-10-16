import { IconArrowsExchange, IconCoin } from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import en from './locales/en.json'
import ru from './locales/ru.json'
import { CurrenciesPage } from './pages/CurrenciesPage'
import { RateTypesPage } from './pages/RateTypesPage'

const VIEW_PERMISSION = 'references.view'
const ADMIN_SECTION = 'admin'

/**
 * Frontend contract of the `references` module: the administration of the
 * system reference data (the ISO currency catalogue and the bank rate types).
 */
export const referencesFrontend: FrontendModule = {
  id: 'references',
  titleKey: 'title',
  routes: [
    {
      path: 'references/currencies',
      element: <CurrenciesPage />,
      permission: VIEW_PERMISSION,
    },
    {
      path: 'references/rate-types',
      element: <RateTypesPage />,
      permission: VIEW_PERMISSION,
    },
  ],
  nav: [
    {
      labelKey: 'nav.currencies',
      to: '/references/currencies',
      icon: <IconCoin size={18} />,
      permission: VIEW_PERMISSION,
      section: ADMIN_SECTION,
    },
    {
      labelKey: 'nav.rateTypes',
      to: '/references/rate-types',
      icon: <IconArrowsExchange size={18} />,
      permission: VIEW_PERMISSION,
      section: ADMIN_SECTION,
    },
  ],
  resources: { ru, en },
}
