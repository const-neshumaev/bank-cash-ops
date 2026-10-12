import { Badge, Card, Group, List, Stack, Text, Title } from '@mantine/core'

import { useAuth } from '../auth/AuthContext'
import { roleColor } from '../roles'

export function DashboardPage() {
  const { user, hasPermission } = useAuth()

  return (
    <Stack>
      <Title order={3}>Панель управления</Title>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Group>
            <Text fw={500}>Вы вошли как</Text>
            <Text>{user?.full_name || user?.email}</Text>
            {user?.roles.map((code, index) => (
              <Badge key={code} color={roleColor(code)} variant="light">
                {user.roles_display[index] ?? code}
              </Badge>
            ))}
          </Group>
          <Text size="sm" c="dimmed">
            Система учёта кассовых операций банка. Доступные разделы меню зависят от
            ролей и прав вашей учётной записи.
          </Text>
        </Stack>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Title order={5}>Доступные разделы</Title>
          <List spacing="xs" size="sm">
            <List.Item>
              <b>Администрирование</b> — пользователи, роли, отделения банка и кассы.
              {hasPermission('core.structure.view') ? ' Доступно.' : ' Доступно администраторам.'}
            </List.Item>
            <List.Item>
              <b>Кассовые смены</b> — открытие и закрытие смен, привязка к кассе.
              {hasPermission('core.shifts.view') ? ' Доступно.' : ' Доступно кассирам и руководителям.'}
            </List.Item>
          </List>
        </Stack>
      </Card>
    </Stack>
  )
}
