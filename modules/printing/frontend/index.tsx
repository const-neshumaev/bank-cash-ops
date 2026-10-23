import { IconPrinter } from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import en from './locales/en.json'
import ru from './locales/ru.json'
import { PrintTemplatesPage } from './pages/PrintTemplatesPage'

const VIEW_PERMISSION = 'printing.templates.view'

/**
 * Frontend contract of the `printing` module: administration of the Word print
 * forms stored in the database. Editing (uploading) requires the manage
 * permission; the page itself opens with the view permission.
 */
export const printingFrontend: FrontendModule = {
  id: 'printing',
  titleKey: 'title',
  routes: [
    {
      path: 'print-templates',
      element: <PrintTemplatesPage />,
      permission: VIEW_PERMISSION,
    },
  ],
  nav: [
    {
      labelKey: 'nav.printTemplates',
      to: '/print-templates',
      icon: <IconPrinter size={18} />,
      permission: VIEW_PERMISSION,
      section: 'admin',
    },
  ],
  resources: { ru, en },
}
