import {
  AppShell,
  Burger,
  Button,
  Group,
  NavLink,
  Stack,
  Text,
  Title,
} from '@mantine/core'
import { useDisclosure } from '@mantine/hooks'
import {
  IconCashBanknote,
  IconLayoutDashboard,
  IconLogout,
  IconUser,
} from '@tabler/icons-react'
import { NavLink as RouterNavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { moduleNav } from '../registry'

export function AppLayout() {
  const [opened, { toggle, close }] = useDisclosure()
  const { user, isAdmin, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login', { replace: true })
  }

  return (
    <AppShell
      header={{ height: 60 }}
      navbar={{ width: 260, breakpoint: 'sm', collapsed: { mobile: !opened } }}
      padding="md"
    >
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="sm" size="sm" />
            <IconCashBanknote size={28} />
            <Title order={4}>BankCashOps</Title>
          </Group>
          <Group gap="sm" wrap="nowrap">
            <Text size="sm" c="dimmed" visibleFrom="sm">
              {user?.full_name || user?.email}
            </Text>
            <Button
              variant="subtle"
              leftSection={<IconLogout size={16} />}
              onClick={handleSignOut}
            >
              Выйти
            </Button>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="md">
        <Stack gap={4}>
          <NavLink
            component={RouterNavLink}
            to="/"
            label="Панель"
            leftSection={<IconLayoutDashboard size={18} />}
            active={location.pathname === '/'}
            onClick={close}
          />
          {moduleNav.map((item) =>
            item.adminOnly && !isAdmin ? null : (
              <NavLink
                key={item.to}
                component={RouterNavLink}
                to={item.to}
                label={item.label}
                leftSection={item.icon}
                active={location.pathname.startsWith(item.to)}
                onClick={close}
              />
            ),
          )}
          <NavLink
            component={RouterNavLink}
            to="/profile"
            label="Профиль"
            leftSection={<IconUser size={18} />}
            active={location.pathname.startsWith('/profile')}
            onClick={close}
          />
        </Stack>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
