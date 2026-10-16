import { Badge, Card, Group, List, Stack, Text, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../auth/AuthContext'
import { roleColor } from '../roles'

export function DashboardPage() {
  const { user, hasPermission } = useAuth()
  const { t } = useTranslation()

  return (
    <Stack>
      <Title order={3}>{t('dashboard.title')}</Title>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Group>
            <Text fw={500}>{t('dashboard.signedInAs')}</Text>
            <Text>{user?.full_name || user?.email}</Text>
            {user?.roles.map((code, index) => (
              <Badge key={code} color={roleColor(code)} variant="light">
                {user.roles_display[index] ?? code}
              </Badge>
            ))}
          </Group>
          <Text size="sm" c="dimmed">
            {t('dashboard.description')}
          </Text>
        </Stack>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Title order={5}>{t('dashboard.sections')}</Title>
          <List spacing="xs" size="sm">
            <List.Item>
              <b>{t('dashboard.admin.name')}</b> {t('dashboard.admin.text')}{' '}
              {hasPermission('core.structure.view')
                ? t('dashboard.available')
                : t('dashboard.admin.restricted')}
            </List.Item>
            <List.Item>
              <b>{t('dashboard.shifts.name')}</b> {t('dashboard.shifts.text')}{' '}
              {hasPermission('core.shifts.view')
                ? t('dashboard.available')
                : t('dashboard.shifts.restricted')}
            </List.Item>
          </List>
        </Stack>
      </Card>
    </Stack>
  )
}
