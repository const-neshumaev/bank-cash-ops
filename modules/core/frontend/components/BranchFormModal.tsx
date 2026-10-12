import { Button, Group, Modal, Select, Stack, Switch, TextInput } from '@mantine/core'
import { useForm } from '@mantine/form'
import { notifications } from '@mantine/notifications'
import { useEffect, useState } from 'react'

import { extractErrorMessage } from '@app/api/errors'
import type { Branch } from '@app/api/types'

import * as branchesApi from '../api/branches'

interface BranchFormModalProps {
  opened: boolean
  branch: Branch | null
  onClose: () => void
  onSaved: () => void
}

interface FormValues {
  name: string
  code: string
  parent: string | null
  address: string
  phone: string
  is_head_office: boolean
  is_active: boolean
}

const EMPTY_VALUES: FormValues = {
  name: '',
  code: '',
  parent: null,
  address: '',
  phone: '',
  is_head_office: false,
  is_active: true,
}

export function BranchFormModal({ opened, branch, onClose, onSaved }: BranchFormModalProps) {
  const isEdit = Boolean(branch)
  const [submitting, setSubmitting] = useState(false)
  const [branches, setBranches] = useState<Branch[]>([])

  const form = useForm<FormValues>({
    initialValues: EMPTY_VALUES,
    validate: {
      name: (value) => (value.trim() ? null : 'Укажите название'),
      code: (value) => (value.trim() ? null : 'Укажите код'),
      parent: (value, values) =>
        values.is_head_office || value ? null : 'Выберите вышестоящее отделение',
    },
  })

  useEffect(() => {
    if (!opened) return
    void branchesApi
      .listAllBranches()
      .then(setBranches)
      .catch(() => setBranches([]))
  }, [opened])

  useEffect(() => {
    if (!opened) return
    if (branch) {
      form.setValues({
        name: branch.name,
        code: branch.code,
        parent: branch.parent ? String(branch.parent) : null,
        address: branch.address,
        phone: branch.phone,
        is_head_office: branch.is_head_office,
        is_active: branch.is_active,
      })
    } else {
      form.setValues(EMPTY_VALUES)
    }
    form.resetDirty()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, branch])

  const isHeadOffice = form.values.is_head_office
  const parentOptions = branches
    .filter((item) => item.id !== branch?.id)
    .map((item) => ({ value: String(item.id), label: `${item.name} (${item.code})` }))

  const handleSubmit = form.onSubmit(async (values) => {
    setSubmitting(true)
    try {
      const payload = {
        name: values.name.trim(),
        code: values.code.trim(),
        parent: values.is_head_office ? null : Number(values.parent),
        address: values.address.trim(),
        phone: values.phone.trim(),
        is_head_office: values.is_head_office,
        is_active: values.is_active,
      }
      if (branch) {
        await branchesApi.updateBranch(branch.id, payload)
        notifications.show({ color: 'green', message: 'Отделение обновлено' })
      } else {
        await branchesApi.createBranch(payload)
        notifications.show({ color: 'green', message: 'Отделение создано' })
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
      title={isEdit ? 'Редактирование отделения' : 'Новое отделение'}
      size="lg"
    >
      <form onSubmit={handleSubmit}>
        <Stack>
          <Group grow align="flex-start">
            <TextInput label="Название" required {...form.getInputProps('name')} />
            <TextInput label="Код" required {...form.getInputProps('code')} />
          </Group>
          <Switch
            label="Головной офис"
            {...form.getInputProps('is_head_office', { type: 'checkbox' })}
          />
          <Select
            label="Вышестоящее отделение"
            data={parentOptions}
            searchable
            clearable
            disabled={isHeadOffice}
            required={!isHeadOffice}
            {...form.getInputProps('parent')}
          />
          <Group grow align="flex-start">
            <TextInput label="Адрес" {...form.getInputProps('address')} />
            <TextInput label="Телефон" {...form.getInputProps('phone')} />
          </Group>
          <Switch label="Активно" {...form.getInputProps('is_active', { type: 'checkbox' })} />
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
