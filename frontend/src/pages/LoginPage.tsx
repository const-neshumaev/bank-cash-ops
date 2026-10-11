import {
  Alert,
  Button,
  Card,
  Center,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { IconAlertCircle } from '@tabler/icons-react'
import { useState } from 'react'
import { Navigate, useLocation, useNavigate } from 'react-router-dom'

import { useAuth } from '../auth/AuthContext'

interface LocationState {
  from?: { pathname?: string }
}

export function LoginPage() {
  const { user, loading, signIn } = useAuth()
  const navigate = useNavigate()
  const location = useLocation()
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)

  const form = useForm({
    initialValues: { email: '', password: '' },
    validate: {
      email: (value) => (/^\S+@\S+\.\S+$/.test(value.trim()) ? null : 'Укажите корректный email'),
      password: (value) => (value.length > 0 ? null : 'Укажите пароль'),
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
      setError('Не удалось войти. Проверьте email и пароль.')
    } finally {
      setSubmitting(false)
    }
  })

  return (
    <Center h="100vh">
      <Card w={380} padding="lg" radius="md" withBorder>
        <Stack>
          <Stack gap={0}>
            <Title order={3}>BankCashOps</Title>
            <Text size="sm" c="dimmed">
              Вход в систему
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
                label="Email"
                name="email"
                id="login-email"
                type="email"
                placeholder="admin@example.com"
                autoComplete="username"
                {...form.getInputProps('email')}
              />
              <PasswordInput
                label="Пароль"
                name="password"
                id="login-password"
                autoComplete="current-password"
                {...form.getInputProps('password')}
              />
              <Button type="submit" loading={submitting} fullWidth>
                Войти
              </Button>
            </Stack>
          </form>
        </Stack>
      </Card>
    </Center>
  )
}
