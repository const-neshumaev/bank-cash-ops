import { Badge, Card, Group, List, Stack, Text, Title } from '@mantine/core'

import { useAuth } from '../auth/AuthContext'
import { ROLE_LABELS } from '../roles'

export function DashboardPage() {
  const { user, isAdmin } = useAuth()

  return (
    <Stack>
      <Title order={3}>Панель управления</Title>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Group>
            <Text fw={500}>Вы вошли как</Text>
            <Text>{user?.full_name || user?.email}</Text>
            {user && (
              <Badge color="blue" variant="light">
                {ROLE_LABELS[user.role]}
              </Badge>
            )}
          </Group>
          <Text size="sm" c="dimmed">
            Система учёта кассовых операций банка. Проект развивается модульно, и первый
            доступный модуль — администрирование пользователей.
          </Text>
        </Stack>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Title order={5}>Доступные модули</Title>
          <List spacing="xs" size="sm">
            <List.Item>
              <b>Администрирование пользователей</b> — добавление, редактирование,
              блокировка и удаление пользователей, назначение ролей.
              {isAdmin ? ' Доступно в разделе «Пользователи».' : ' Доступно администраторам.'}
            </List.Item>
          </List>
        </Stack>
      </Card>
    </Stack>
  )
}
