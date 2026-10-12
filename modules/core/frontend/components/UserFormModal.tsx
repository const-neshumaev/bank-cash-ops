import { Button, Group, Modal, MultiSelect, PasswordInput, Stack, Switch, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { Role, User } from '@app/api/types'

import * as rolesApi from '../api/roles'
import * as usersApi from '../api/users'

interface UserFormModalProps {
  opened: boolean
  user: User | null
  onClose: () => void
  onSaved: () => void
}

interface FormValues {
  email: string
  first_name: string
  last_name: string
  middle_name: string
  phone: string
  roles: string[]
  is_active: boolean
  password: string
  password_confirm: string
}

const EMPTY_VALUES: FormValues = {
  email: '',
  first_name: '',
  last_name: '',
  middle_name: '',
  phone: '',
  roles: [],
  is_active: true,
  password: '',
  password_confirm: '',
}

export function UserFormModal({ opened, user, onClose, onSaved }: UserFormModalProps) {
  const isEdit = Boolean(user)
  const [submitting, setSubmitting] = useState(false)
  const [roles, setRoles] = useState<Role[]>([])

  const form = useForm<FormValues>({
    initialValues: EMPTY_VALUES,
    validate: {
      email: (value) => (/^\S+@\S+\.\S+$/.test(value.trim()) ? null : 'Укажите корректный email'),
      last_name: (value) => (value.trim() ? null : 'Укажите фамилию'),
      first_name: (value) => (value.trim() ? null : 'Укажите имя'),
      password: (value) => {
        if (isEdit) return null
        return value.length >= 8 ? null : 'Пароль должен содержать не менее 8 символов'
      },
      password_confirm: (value, values) => {
        if (isEdit) return null
        return value === values.password ? null : 'Пароли не совпадают'
      },
    },
  })

  useEffect(() => {
    if (!opened) return
    void rolesApi
      .listAllRoles()
      .then(setRoles)
      .catch(() => setRoles([]))
  }, [opened])

  useEffect(() => {
    if (!opened) return
    if (user) {
      form.setValues({
        email: user.email,
        first_name: user.first_name,
        last_name: user.last_name,
        middle_name: user.middle_name,
        phone: user.phone,
        roles: user.roles,
        is_active: user.is_active,
        password: '',
        password_confirm: '',
      })
    } else {
      form.setValues(EMPTY_VALUES)
    }
    form.resetDirty()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, user])

  const roleOptions = roles.map((role) => ({ value: role.code, label: role.name }))

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    try {
      if (user) {
        await usersApi.updateUser(user.id, {
          email: values.email.trim(),
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          middle_name: values.middle_name.trim(),
          phone: values.phone.trim(),
          roles: values.roles,
          is_active: values.is_active,
        })
        notifications.show({ color: 'green', message: 'Пользователь обновлён' })
      } else {
        await usersApi.createUser({
          email: values.email.trim(),
          password: values.password,
          password_confirm: values.password_confirm,
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          middle_name: values.middle_name.trim(),
          phone: values.phone.trim(),
          roles: values.roles,
          is_active: values.is_active,
        })
        notifications.show({ color: 'green', message: 'Пользователь создан' })
      }
      onSaved()
      onClose()
    } catch (error) {
      notifications.show({ color: 'red', title: 'Ошибка', message: extractErrorMessage(error) })
    } finally {
      setSubmitting(false)
    }
  })

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={isEdit ? 'Редактирование пользователя' : 'Новый пользователь'}
      size="lg"
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput
            label="Email"
            placeholder="user@example.com"
            required
            {...form.getInputProps('email')}
          />
          <Group grow align="flex-start">
            <TextInput label="Фамилия" required {...form.getInputProps('last_name')} />
            <TextInput label="Имя" required {...form.getInputProps('first_name')} />
          </Group>
          <Group grow align="flex-start">
            <TextInput label="Отчество" {...form.getInputProps('middle_name')} />
            <TextInput label="Телефон" placeholder="+7-900-000-00-00" {...form.getInputProps('phone')} />
          </Group>
          <MultiSelect
            label="Роли"
            data={roleOptions}
            searchable
            placeholder="Выберите роли"
            {...form.getInputProps('roles')}
          />
          {!isEdit && (
            <Group grow align="flex-start">
              <PasswordInput label="Пароль" required {...form.getInputProps('password')} />
              <PasswordInput
                label="Подтверждение пароля"
                required
                {...form.getInputProps('password_confirm')}
              />
            </Group>
          )}
          <Switch label="Активен" {...form.getInputProps('is_active', { type: 'checkbox' })} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" loading={submitting}>
              Сохранить
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
