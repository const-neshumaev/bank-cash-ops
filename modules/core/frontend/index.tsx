import { IconUsers } from '@tabler/icons-react'

import type { FrontendModule } from '@app/registry/contract'

import { UsersPage } from './pages/UsersPage'

/** Frontend contract of the `core` module (user administration). */
export const coreFrontend: FrontendModule = {
  id: 'core',
  title: 'Ядро',
  routes: [{ path: 'users', element: <UsersPage />, access: 'admin' }],
  nav: [
    { label: 'Пользователи', to: '/users', icon: <IconUsers size={18} />, adminOnly: true },
  ],
}
