import { AppShell, Button, Group, Menu, Text, Title } from '@mantine/core'
import { IconCashBanknote, IconChevronDown, IconLogout, IconUser } from '@tabler/icons-react'
import { useTranslation } from 'react-i18next'
import { NavLink as RouterNavLink, Outlet, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { LanguageSelect } from '../components/LanguageSelect'
import { moduleNav, type ResolvedNavItem } from '../registry'

export function AppLayout() {
  const { user, hasAnyPermission, signOut } = useAuth()
  const { t } = useTranslation()
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
  const sections = visibleItems.reduce<Record<string, ResolvedNavItem[]>>((acc, item) => {
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

            {plainItems.map((item) => (
              <Button
                key={item.to}
                component={RouterNavLink}
                to={item.to}
                leftSection={item.icon}
                variant={isActive(item.to) ? 'light' : 'subtle'}
                size="compact-md"
              >
                {t(item.labelKey, { ns: item.moduleId })}
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
                    {t(`sections.${section}`, { defaultValue: section })}
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
                      {t(item.labelKey, { ns: item.moduleId })}
                    </Menu.Item>
                  ))}
                </Menu.Dropdown>
              </Menu>
            ))}
          </Group>

          <Group gap="sm" wrap="nowrap">
            <LanguageSelect />
            <Text size="sm" c="dimmed" visibleFrom="sm">
              {user?.full_name || user?.email}
            </Text>
            <Button
              component={RouterNavLink}
              to="/profile"
              variant="subtle"
              leftSection={<IconUser size={16} />}
            >
              {t('nav.profile')}
            </Button>
            <Button
              variant="subtle"
              leftSection={<IconLogout size={16} />}
              onClick={handleSignOut}
            >
              {t('nav.logout')}
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
