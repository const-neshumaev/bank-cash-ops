import { Button, Checkbox, Group, Modal, Stack, Textarea, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { Permission, Role } from '@app/api/types'

import * as rolesApi from '../api/roles'

interface RoleFormModalProps {
  opened: boolean
  role: Role | null
  onClose: () => void
  onSaved: () => void
}

interface FormValues {
  name: string
  description: string
  permissions: string[]
}

const EMPTY_VALUES: FormValues = { name: '', description: '', permissions: [] }

export function RoleFormModal({ opened, role, onClose, onSaved }: RoleFormModalProps) {
  const isEdit = Boolean(role)
  const [submitting, setSubmitting] = useState(false)
  const [permissions, setPermissions] = useState<Permission[]>([])

  const form = useForm<FormValues>({
    initialValues: EMPTY_VALUES,
    validate: {
      name: (value) => (value.trim() ? null : 'Укажите название роли'),
    },
  })

  useEffect(() => {
    if (!opened) return
    void rolesApi
      .listPermissions()
      .then(setPermissions)
      .catch(() => setPermissions([]))
  }, [opened])

  useEffect(() => {
    if (!opened) return
    if (role) {
      form.setValues({
        name: role.name,
        description: role.description,
        permissions: role.permissions,
      })
    } else {
      form.setValues(EMPTY_VALUES)
    }
    form.resetDirty()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, role])

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    try {
      const payload = {
        name: values.name.trim(),
        description: values.description.trim(),
        permissions: values.permissions,
      }
      if (role) {
        await rolesApi.updateRole(role.id, payload)
        notifications.show({ color: 'green', message: 'Роль обновлена' })
      } else {
        await rolesApi.createRole(payload)
        notifications.show({ color: 'green', message: 'Роль создана' })
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
      title={isEdit ? 'Редактирование роли' : 'Новая роль'}
      size="lg"
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput label="Название" required {...form.getInputProps('name')} />
          <Textarea label="Описание" autosize minRows={2} {...form.getInputProps('description')} />
          <Checkbox.Group label="Права" {...form.getInputProps('permissions')}>
            <Stack gap="xs" mt="xs">
              {permissions.map((permission) => (
                <Checkbox
                  key={permission.code}
                  value={permission.code}
                  label={permission.name}
                  description={permission.code}
                />
              ))}
            </Stack>
          </Checkbox.Group>
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
