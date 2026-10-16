import {
  Alert,
  Button,
  Card,
  Center,
  Group,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { IconAlertCircle } from '@tabler/icons-react'
import { useState } from 'react'
import { useTranslation } from 'react-i18next'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'
import { LanguageSelect } from '../components/LanguageSelect'

interface LocationState {
  from?: { pathname?: string }
}

export function LoginPage() {
  const { user, loading, signIn } = useAuth()
  const { t } = useTranslation()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm({
    initialValues: { email: '', password: '' },
    validate: {
      email: (value) =>
        /^\S+@\S+\.\S+$/.test(value.trim()) ? null : t('login.validation.email'),
      password: (value) => (value.length > 0 ? null : t('login.validation.password')),
    },
  })

  if (!loading && user) {
    return <Navigate to="/" replace />
  }

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    setError(null)
    try {
      await signIn(values.email.trim(), values.password)
      const state = location.state as LocationState | null
      navigate(state?.from?.pathname ?? '/', { replace: true })
    } catch {
      setError(t('login.failed'))
    } finally {
      setSubmitting(false)
    }
  })

  return (
    <Center h="100vh">
      <Card w={380} padding="lg" radius="md" withBorder>
        <Stack>
          <Stack gap={0}>
            <Group justify="space-between">
              <Title order={3}>BankCashOps</Title>
              <LanguageSelect />
            </Group>
            <Text size="sm" c="dimmed">
              {t('login.subtitle')}
            </Text>
          </Stack>

          {error && (
            <Alert color="red" icon={<IconAlertCircle size={16} />}>
              {error}
            </Alert>
          )}

          <form onSubmit={handleSubmit} autoComplete="on" noValidate>
            <Stack>
              <TextInput
                label={t('login.email')}
                name="email"
                id="login-email"
                type="email"
                placeholder="admin@example.com"
                autoComplete="username"
                {...form.getInputProps('email')}
              />
              <PasswordInput
                label={t('login.password')}
                name="password"
                id="login-password"
                autoComplete="current-password"
                {...form.getInputProps('password')}
              />
              <Button type="submit" loading={submitting} fullWidth>
                {t('login.submit')}
              </Button>
            </Stack>
          </form>
        </Stack>
      </Card>
    </Center>
  )
}
