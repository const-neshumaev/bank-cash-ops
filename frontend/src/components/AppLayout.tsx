import { AppShell, Button, Group, Menu, Text, Title } from '@mantine/core'
import { IconCashBanknote, IconChevronDown, IconLogout, IconUser } from '@tabler/icons-react'
import { NavLink as RouterNavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { moduleNav } from '../registry'
import type { ModuleNavItem } from '../registry/contract'

export function AppLayout() {
  const { user, hasAnyPermission, signOut } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()

  const handleSignOut = async () => {
    await signOut()
    navigate('/login', { replace: true })
  }

  const visibleItems = moduleNav.filter(
    (item) => !item.permission || hasAnyPermission(item.permission),
  )
  const plainItems = visibleItems.filter((item) => !item.section)
  const sections = visibleItems.reduce<Record<string, ModuleNavItem[]>>((acc, item) => {
    if (item.section) {
      acc[item.section] = [...(acc[item.section] ?? []), item]
    }
    return acc
  }, {})

  const isActive = (to: string) => location.pathname.startsWith(to)

  return (
    <AppShell header={{ height: 60 }} padding="md">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <IconCashBanknote size={28} />
            <Title order={4}>BankCashOps</Title>

            <Button
              component={RouterNavLink}
              to="/"
              variant={isActive('/') && location.pathname === '/' ? 'light' : 'subtle'}
              size="compact-md"
            >
              Панель
            </Button>

            {plainItems.map((item) => (
              <Button
                key={item.to}
                component={RouterNavLink}
                to={item.to}
                leftSection={item.icon}
                variant={isActive(item.to) ? 'light' : 'subtle'}
                size="compact-md"
              >
                {item.label}
              </Button>
            ))}

            {Object.entries(sections).map(([section, items]) => (
              <Menu key={section} withinPortal>
                <Menu.Target>
                  <Button
                    variant={items.some((item) => isActive(item.to)) ? 'light' : 'subtle'}
                    size="compact-md"
                    rightSection={<IconChevronDown size={16} />}
                  >
                    {section}
                  </Button>
                </Menu.Target>
                <Menu.Dropdown>
                  {items.map((item) => (
                    <Menu.Item
                      key={item.to}
                      component={RouterNavLink}
                      to={item.to}
                      leftSection={item.icon}
                    >
                      {item.label}
                    </Menu.Item>
                  ))}
                </Menu.Dropdown>
              </Menu>
            ))}
          </Group>

          <Group gap="sm" wrap="nowrap">
            <Text size="sm" c="dimmed" visibleFrom="sm">
              {user?.full_name || user?.email}
            </Text>
            <Button
              component={RouterNavLink}
              to="/profile"
              variant="subtle"
              leftSection={<IconUser size={16} />}
            >
              Профиль
            </Button>
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

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>
    </AppShell>
  )
}
