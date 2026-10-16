import {
  Badge,
  Button,
  Card,
  Divider,
  Group,
  PasswordInput,
  Stack,
  Text,
  TextInput,
  Title,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import * as authApi from '../api/auth'
import { extractErrorMessage } from '../api/errors'
import { useAuth } from '../auth/AuthContext'
import { roleColor } from '../roles'

export function ProfilePage() {
  const { user, refreshUser } = useAuth()
  const { t } = useTranslation()
  const [savingProfile, setSavingProfile] = useState(false)
  const [savingPassword, setSavingPassword] = useState(false)

  const profileForm = useForm({
    initialValues: {
      last_name: user?.last_name ?? '',
      first_name: user?.first_name ?? '',
      middle_name: user?.middle_name ?? '',
      phone: user?.phone ?? '',
    },
    validate: {
      last_name: (value) => (value.trim() ? null : t('profile.validation.lastName')),
      first_name: (value) => (value.trim() ? null : t('profile.validation.firstName')),
    },
  })

  const passwordForm = useForm({
    initialValues: { old_password: '', new_password: '', new_password_confirm: '' },
    validate: {
      old_password: (value) => (value ? null : t('profile.validation.currentPassword')),
      new_password: (value) =>
        value.length >= 8 ? null : t('profile.validation.newPassword'),
      new_password_confirm: (value, values) =>
        value === values.new_password ? null : t('profile.validation.confirmPassword'),
    },
  })

  useEffect(() => {
    if (user) {
      profileForm.setValues({
        last_name: user.last_name,
        first_name: user.first_name,
        middle_name: user.middle_name,
        phone: user.phone,
      })
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [user])

  const handleProfileSubmit = profileForm.onSubmit(async (values) => {
    setSavingProfile(true)
    try {
      await authApi.updateMe({
        last_name: values.last_name.trim(),
        first_name: values.first_name.trim(),
        middle_name: values.middle_name.trim(),
        phone: values.phone.trim(),
      })
      await refreshUser()
      notifications.show({ color: 'green', message: t('profile.saved') })
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setSavingProfile(false)
    }
  })

  const handlePasswordSubmit = passwordForm.onSubmit(async (values) => {
    setSavingPassword(true)
    try {
      await authApi.changePassword({
        old_password: values.old_password,
        new_password: values.new_password,
        new_password_confirm: values.new_password_confirm,
      })
      passwordForm.reset()
      notifications.show({ color: 'green', message: t('profile.passwordChanged') })
    } catch (error) {
      notifications.show({
        color: 'red',
        title: t('common.error'),
        message: extractErrorMessage(error),
      })
    } finally {
      setSavingPassword(false)
    }
  })

  return (
    <Stack maw={640}>
      <Title order={3}>{t('profile.title')}</Title>

      <Card withBorder padding="lg" radius="md">
        <Stack gap="xs">
          <Group justify="space-between">
            <Text fw={500}>{t('profile.account')}</Text>
            {user && (
              <Badge color={user.is_active ? 'green' : 'gray'} variant="light">
                {user.is_active ? t('profile.active') : t('profile.blocked')}
              </Badge>
            )}
          </Group>
          <Group>
            <Text size="sm" c="dimmed">
              {t('profile.email')}
            </Text>
            <Text size="sm">{user?.email}</Text>
          </Group>
          <Group>
            <Text size="sm" c="dimmed">
              {t('profile.roles')}
            </Text>
            <Group gap={6}>
              {user?.roles.length ? (
                user.roles.map((code, index) => (
                  <Badge key={code} color={roleColor(code)} variant="light">
                    {user.roles_display[index] ?? code}
                  </Badge>
                ))
              ) : (
                <Text size="sm">—</Text>
              )}
            </Group>
          </Group>
        </Stack>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <form onSubmit={handleProfileSubmit}>
          <Stack>
            <Text fw={500}>{t('profile.personal')}</Text>
            <Group grow align="flex-start">
              <TextInput
                label={t('profile.lastName')}
                required
                {...profileForm.getInputProps('last_name')}
              />
              <TextInput
                label={t('profile.firstName')}
                required
                {...profileForm.getInputProps('first_name')}
              />
            </Group>
            <Group grow align="flex-start">
              <TextInput
                label={t('profile.middleName')}
                {...profileForm.getInputProps('middle_name')}
              />
              <TextInput
                label={t('profile.phone')}
                placeholder="+7-900-000-00-00"
                {...profileForm.getInputProps('phone')}
              />
            </Group>
            <Group justify="flex-end">
              <Button type="submit" loading={savingProfile}>
                {t('common.save')}
              </Button>
            </Group>
          </Stack>
        </form>
      </Card>

      <Card withBorder padding="lg" radius="md">
        <form onSubmit={handlePasswordSubmit}>
          <Stack>
            <Text fw={500}>{t('profile.passwordSection')}</Text>
            <Divider />
            <PasswordInput
              label={t('profile.currentPassword')}
              autoComplete="current-password"
              {...passwordForm.getInputProps('old_password')}
            />
            <Group grow align="flex-start">
              <PasswordInput
                label={t('profile.newPassword')}
                autoComplete="new-password"
                {...passwordForm.getInputProps('new_password')}
              />
              <PasswordInput
                label={t('profile.confirmPassword')}
                autoComplete="new-password"
                {...passwordForm.getInputProps('new_password_confirm')}
              />
            </Group>
            <Group justify="flex-end">
              <Button type="submit" loading={savingPassword}>
                {t('profile.changePassword')}
              </Button>
            </Group>
          </Stack>
        </form>
      </Card>
    </Stack>
  )
}
