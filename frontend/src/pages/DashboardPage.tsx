import { Badge, Card, Group, Stack, Text } from '@mantine/core'
import { useTranslation } from 'react-i18next'

import { useAuth } from '../auth/AuthContext'
import { roleColor } from '../roles'

export function DashboardPage() {
  const { user } = useAuth()
  const { t } = useTranslation()

  return (
    <Stack>
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
    </Stack>
  )
}
