import {
  ActionIcon,
  Button,
  Group,
  Modal,
  MultiSelect,
  PasswordInput,
  Select,
  Stack,
  Switch,
  Text,
  TextInput,
} from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { IconPlus, IconTrash } from '@tabler/icons-react'
import { useEffect, useState } from 'react'
import { useTranslation } from 'react-i18next'

import { extractErrorMessage } from '@app/api/errors'
import type { Branch, Role, User } from '@app/api/types'

import * as branchesApi from '../api/branches'
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

interface BranchAccessRow {
  branch: number | null
  include_descendants: boolean
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

function branchLabel(branch: Branch): string {
  return branch.code ? `${branch.name} (${branch.code})` : branch.name
}

export function UserFormModal({ opened, user, onClose, onSaved }: UserFormModalProps) {
  const { t } = useTranslation('core')
  const isEdit = Boolean(user)
  const [submitting, setSubmitting] = useState(false)
  const [roles, setRoles] = useState<Role[]>([])
  const [branches, setBranches] = useState<Branch[]>([])
  const [branchAccess, setBranchAccess] = useState<BranchAccessRow[]>([])

  const form = useForm<FormValues>({
    initialValues: EMPTY_VALUES,
    validate: {
      email: (value) => (/^\S+@\S+\.\S+$/.test(value.trim()) ? null : t('validation.email')),
      last_name: (value) => (value.trim() ? null : t('validation.lastName')),
      first_name: (value) => (value.trim() ? null : t('validation.firstName')),
      password: (value) => {
        if (isEdit) return null
        return value.length >= 8 ? null : t('validation.password')
      },
      password_confirm: (value, values) => {
        if (isEdit) return null
        return value === values.password ? null : t('validation.passwordConfirm')
      },
    },
  })

  useEffect(() => {
    if (!opened) return
    void rolesApi
      .listAllRoles()
      .then(setRoles)
      .catch(() => setRoles([]))
    void branchesApi
      .listBranchCatalog()
      .then(setBranches)
      .catch(() => setBranches([]))
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
      setBranchAccess(
        user.branch_access.map((entry) => ({
          branch: entry.branch,
          include_descendants: entry.include_descendants,
        })),
      )
    } else {
      form.setValues(EMPTY_VALUES)
      setBranchAccess([])
    }
    form.resetDirty()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, user])

  const roleOptions = roles.map((role) => ({ value: role.code, label: role.name }))
  const branchOptions = branches.map((branch) => ({
    value: String(branch.id),
    label: branchLabel(branch),
  }))

  const addBranchRow = () => {
    setBranchAccess((rows) => [...rows, { branch: null, include_descendants: false }])
  }

  const updateBranchRow = (index: number, patch: Partial<BranchAccessRow>) => {
    setBranchAccess((rows) => rows.map((row, i) => (i === index ? { ...row, ...patch } : row)))
  }

  const removeBranchRow = (index: number) => {
    setBranchAccess((rows) => rows.filter((_, i) => i !== index))
  }

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    try {
      const access = branchAccess
        .filter((row) => row.branch !== null)
        .map((row) => ({
          branch: row.branch as number,
          include_descendants: row.include_descendants,
        }))

      if (user) {
        await usersApi.updateUser(user.id, {
          email: values.email.trim(),
          first_name: values.first_name.trim(),
          last_name: values.last_name.trim(),
          middle_name: values.middle_name.trim(),
          phone: values.phone.trim(),
          roles: values.roles,
          branch_access: access,
          is_active: values.is_active,
        })
        notifications.show({ color: 'green', message: t('users.updated') })
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
          branch_access: access,
          is_active: values.is_active,
        })
        notifications.show({ color: 'green', message: t('users.created') })
      }
      onSaved()
      onClose()
    } catch (error) {
      notifications.show({ color: 'red', title: t('common.error'), message: extractErrorMessage(error) })
    } finally {
      setSubmitting(false)
    }
  })

  return (
    <Modal
      opened={opened}
      onClose={onClose}
      title={isEdit ? t('users.editTitle') : t('users.createTitle')}
      size="lg"
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <TextInput
            label={t('users.form.email')}
            placeholder="user@example.com"
            required
            {...form.getInputProps('email')}
          />
          <Group grow align="flex-start">
            <TextInput label={t('users.form.lastName')} required {...form.getInputProps('last_name')} />
            <TextInput label={t('users.form.firstName')} required {...form.getInputProps('first_name')} />
          </Group>
          <Group grow align="flex-start">
            <TextInput label={t('users.form.middleName')} {...form.getInputProps('middle_name')} />
            <TextInput
              label={t('users.form.phone')}
              placeholder="+7-900-000-00-00"
              {...form.getInputProps('phone')}
            />
          </Group>
          <MultiSelect
            label={t('users.form.roles')}
            data={roleOptions}
            searchable
            placeholder={t('users.form.rolesPlaceholder')}
            {...form.getInputProps('roles')}
          />
          {!isEdit && (
            <Group grow align="flex-start">
              <PasswordInput label={t('users.form.password')} required {...form.getInputProps('password')} />
              <PasswordInput
                label={t('users.form.passwordConfirm')}
                required
                {...form.getInputProps('password_confirm')}
              />
            </Group>
          )}

          <Stack gap="xs">
            <Group justify="space-between">
              <Text fw={500} size="sm">
                {t('users.form.branchAccess')}
              </Text>
              <Button
                size="compact-sm"
                variant="light"
                leftSection={<IconPlus size={14} />}
                onClick={addBranchRow}
              >
                {t('common.add')}
              </Button>
            </Group>
            <Text size="xs" c="dimmed">
              {t('users.form.branchAccessHint')}
            </Text>
            {branchAccess.length === 0 ? (
              <Text size="sm" c="dimmed">
                {t('users.form.noBranches')}
              </Text>
            ) : (
              branchAccess.map((row, index) => (
                <Group key={index} gap="xs" wrap="nowrap">
                  <Select
                    placeholder={t('users.form.branch')}
                    data={branchOptions}
                    value={row.branch === null ? null : String(row.branch)}
                    onChange={(value) =>
                      updateBranchRow(index, { branch: value ? Number(value) : null })
                    }
                    searchable
                    style={{ flex: 1 }}
                  />
                  <Switch
                    label={t('users.form.includeDescendants')}
                    checked={row.include_descendants}
                    onChange={(event) =>
                      updateBranchRow(index, { include_descendants: event.currentTarget.checked })
                    }
                    style={{ flexShrink: 0 }}
                  />
                  <ActionIcon color="red" variant="subtle" onClick={() => removeBranchRow(index)}>
                    <IconTrash size={16} />
                  </ActionIcon>
                </Group>
              ))
            )}
          </Stack>

          <Switch label={t('users.form.active')} {...form.getInputProps('is_active', { type: 'checkbox' })} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              {t('common.cancel')}
            </Button>
            <Button type="submit" loading={submitting}>
              {t('common.save')}
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  )
}
