import { Button, Center, Stack, Text, Title } from '@mantine/core'
import { useTranslation } from 'react-i18next'
import { useNavigate } from 'react-router-dom'

export function NotFoundPage() {
  const { t } = useTranslation()
  const navigate = useNavigate()

  return (
    <Center h="60vh">
      <Stack align="center">
        <Title order={2}>404</Title>
        <Text c="dimmed">{t('notFound.message')}</Text>
        <Button onClick={() => navigate('/')}>{t('notFound.home')}</Button>
      </Stack>
    </Center>
  )
}
