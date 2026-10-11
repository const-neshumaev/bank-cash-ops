import { Button, Center, Stack, Text, Title } from '@mantine/core'
import { useNavigate } from 'react-router-dom'

export function NotFoundPage() {
  const navigate = useNavigate()

  return (
    <Center h="60vh">
      <Stack align="center">
        <Title order={2}>404</Title>
        <Text c="dimmed">Страница не найдена</Text>
        <Button onClick={() => navigate('/')}>На главную</Button>
      </Stack>
    </Center>
  )
}
